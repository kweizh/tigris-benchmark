import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/orchestrator"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
AGGREGATED_JSON = os.path.join(PROJECT_DIR, "aggregated.json")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
SETUP_SH = os.path.join(PROJECT_DIR, "setup.sh")
SEED_DIR = "/opt/harbor-seed/prompts"

SOURCE_BUCKET = "gold-eval-dataset"
FORK_PREFIX = "eval-attempt"
WRITER_PREFIX = "eval-writer"
EXPECTED_FORK_NAMES = [f"{FORK_PREFIX}-{i}" for i in range(3)]
EXPECTED_WRITER_NAMES = [f"{WRITER_PREFIX}-{i}" for i in range(3)]
EXPECTED_PROMPT_KEYS = ("p1", "p2", "p3")
EXPECTED_PROMPT_OBJECT_KEYS = (
    "prompts/p1.json",
    "prompts/p2.json",
    "prompts/p3.json",
)


def _tigris_cmd():
    """Return the command list for invoking the Tigris CLI."""
    if shutil.which("tigris") is not None:
        return ["tigris"]
    local = os.path.join(PROJECT_DIR, "node_modules", ".bin", "tigris")
    if os.path.isfile(local):
        return [local]
    pytest.fail(
        "Tigris CLI binary is not available on PATH or in node_modules/.bin."
    )


def _read_seed(name):
    path = os.path.join(SEED_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _expected_reversed_answer(prompt_id):
    """Compute the expected reversed answer for the given prompt id."""
    filename = f"{prompt_id}.json"
    content = _read_seed(filename)
    return content[::-1]


def test_index_ts_created():
    assert os.path.isfile(INDEX_TS), (
        f"User must create the TypeScript orchestrator at {INDEX_TS}."
    )


@pytest.fixture(scope="module")
def run_user_script():
    """Priority 1: Execute the user's orchestrator end-to-end against real
    Tigris. The fixture defensively re-runs setup.sh first so the gold dataset
    bucket is guaranteed to exist with the canonical prompts."""

    # Best-effort cleanup of any prior outputs.
    for path in (AGGREGATED_JSON, OUTPUT_LOG):
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    # Defensive: ensure the gold-eval-dataset bucket exists and is freshly
    # seeded before invoking the user's orchestrator.
    setup_result = subprocess.run(
        ["bash", SETUP_SH],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=300,
    )
    if setup_result.returncode != 0:
        pytest.fail(
            f"setup.sh failed before running the orchestrator. "
            f"stdout={setup_result.stdout!r} stderr={setup_result.stderr!r}"
        )

    with open(OUTPUT_LOG, "w") as logf:
        result = subprocess.run(
            ["npx", "tsx", "index.ts"],
            cwd=PROJECT_DIR,
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            timeout=600,
        )

    with open(OUTPUT_LOG) as f:
        log_contents = f.read()

    return result, log_contents


def test_orchestrator_exits_zero(run_user_script):
    result, log_contents = run_user_script
    assert result.returncode == 0, (
        f"'npx tsx index.ts' exited with {result.returncode}. "
        f"Output:\n{log_contents}"
    )


def test_aggregated_json_top_level_shape(run_user_script):
    run_user_script  # ensure script ran
    assert os.path.isfile(AGGREGATED_JSON), (
        f"Expected aggregate output at {AGGREGATED_JSON} after running "
        f"index.ts."
    )
    with open(AGGREGATED_JSON) as f:
        data = json.load(f)
    assert isinstance(data, dict), (
        f"{AGGREGATED_JSON} must be a JSON object, got "
        f"{type(data).__name__}."
    )
    actual_keys = set(data.keys())
    expected_keys = set(EXPECTED_FORK_NAMES)
    assert actual_keys == expected_keys, (
        f"Top-level keys in {AGGREGATED_JSON} must be exactly "
        f"{sorted(expected_keys)}, got {sorted(actual_keys)}."
    )


def test_aggregated_inner_shape_and_answers(run_user_script):
    run_user_script  # ensure script ran
    with open(AGGREGATED_JSON) as f:
        data = json.load(f)

    for fork_name in EXPECTED_FORK_NAMES:
        inner = data.get(fork_name)
        assert isinstance(inner, dict), (
            f"aggregated['{fork_name}'] must be a JSON object, got "
            f"{type(inner).__name__}."
        )
        inner_keys = set(inner.keys())
        expected_inner = set(EXPECTED_PROMPT_KEYS)
        assert inner_keys == expected_inner, (
            f"aggregated['{fork_name}'] must have exactly keys "
            f"{sorted(expected_inner)}, got {sorted(inner_keys)}."
        )
        for prompt_id in EXPECTED_PROMPT_KEYS:
            actual_answer = inner[prompt_id]
            assert isinstance(actual_answer, str), (
                f"aggregated['{fork_name}']['{prompt_id}'] must be a string, "
                f"got {type(actual_answer).__name__}."
            )
            expected = _expected_reversed_answer(prompt_id)
            assert actual_answer == expected, (
                f"aggregated['{fork_name}']['{prompt_id}'] does not match "
                f"the expected reversed prompt content.\n"
                f"  expected: {expected!r}\n"
                f"  got:      {actual_answer!r}"
            )


def test_fork_and_writer_buckets_torn_down(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm none of the per-attempt
    fork or writer workspace buckets remain after the orchestrator exits."""
    run_user_script  # ensure script ran
    cmd = _tigris_cmd() + ["buckets", "list"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris buckets list' failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    listed_tokens = set()
    for line in combined.splitlines():
        for tok in line.strip().split():
            listed_tokens.add(tok)

    leaked = []
    for name in EXPECTED_FORK_NAMES + EXPECTED_WRITER_NAMES:
        if name in listed_tokens:
            leaked.append(name)
    assert not leaked, (
        f"The following per-attempt buckets were not torn down: "
        f"{sorted(leaked)}. teardownForks and teardownWorkspace must remove "
        f"every fork and writer bucket. Full output:\n{combined}"
    )


def test_gold_dataset_still_has_prompts(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm the source gold dataset is
    untouched (still listed and still contains the three prompt objects)."""
    run_user_script  # ensure script ran
    list_cmd = _tigris_cmd() + ["objects", "list", SOURCE_BUCKET]
    result = subprocess.run(
        list_cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris objects list {SOURCE_BUCKET}' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    missing = []
    for key in EXPECTED_PROMPT_OBJECT_KEYS:
        if key not in combined:
            missing.append(key)
    assert not missing, (
        f"Expected prompt object keys {list(EXPECTED_PROMPT_OBJECT_KEYS)} in "
        f"bucket '{SOURCE_BUCKET}', missing: {missing}. CLI output:\n"
        f"{combined}"
    )


def test_cleanup_residual_buckets(run_user_script):
    """Verifier cleanup: best-effort remove every per-attempt bucket and the
    source gold dataset so the task leaves no residue. Failures here do not
    fail the test suite as long as the bucket either no longer exists or is
    successfully deleted."""
    run_user_script  # ensure script ran first

    targets = EXPECTED_FORK_NAMES + EXPECTED_WRITER_NAMES + [SOURCE_BUCKET]
    errors = []
    for name in targets:
        cmd = _tigris_cmd() + ["buckets", "delete", name, "--force"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            combined = (result.stdout + result.stderr).lower()
            if "not found" in combined or "no such bucket" in combined:
                continue
            fallback = subprocess.run(
                _tigris_cmd() + ["buckets", "delete", name],
                capture_output=True,
                text=True,
                timeout=120,
                env=os.environ.copy(),
            )
            if fallback.returncode != 0:
                fb_combined = (fallback.stdout + fallback.stderr).lower()
                if "not found" in fb_combined or "no such bucket" in fb_combined:
                    continue
                errors.append(
                    f"failed to delete '{name}': "
                    f"primary stdout={result.stdout!r} stderr={result.stderr!r}; "
                    f"fallback stdout={fallback.stdout!r} stderr={fallback.stderr!r}"
                )
    assert not errors, (
        "Verifier cleanup encountered errors:\n  " + "\n  ".join(errors)
    )
