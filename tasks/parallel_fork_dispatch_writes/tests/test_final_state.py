import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
RUN_TS = os.path.join(PROJECT_DIR, "run.ts")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _source_bucket():
    import re
    name = f"harbor-source-{_read_trial_id()}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _fork_bucket(i):
    name = f"harbor-fork-{_read_trial_id()}-{i}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


VERIFY_SCRIPT = r"""
import { get, removeBucket } from "@tigrisdata/storage";

const sourceBucket = process.argv[2];
const forkBuckets = process.argv.slice(3);

async function main() {
  const result = { forks: {}, source: {}, cleanup: {}, errors: [] };

  for (let i = 0; i < forkBuckets.length; i++) {
    const bucket = forkBuckets[i];
    const entry = { bucket };

    const workerRes = await get("worker/output.txt", "string", { config: { bucket } });
    if (workerRes.error) {
      entry.worker_error = String(workerRes.error.message || workerRes.error);
    } else {
      entry.worker_body = workerRes.data;
    }

    const seedRes = await get("seed/dataset.txt", "string", { config: { bucket } });
    if (seedRes.error) {
      entry.seed_error = String(seedRes.error.message || seedRes.error);
    } else {
      entry.seed_body = seedRes.data;
    }

    result.forks[String(i)] = entry;
  }

  // Cleanup all 4 buckets, best-effort.
  for (const bucket of forkBuckets) {
    const rm = await removeBucket(bucket, { force: true });
    result.cleanup[bucket] = rm.error
      ? { error: String(rm.error.message || rm.error) }
      : { ok: true };
  }
  const rmSource = await removeBucket(sourceBucket, { force: true });
  result.cleanup[sourceBucket] = rmSource.error
    ? { error: String(rmSource.error.message || rmSource.error) }
    : { ok: true };

  process.stdout.write(JSON.stringify(result));
}

main().catch((err) => {
  process.stdout.write(
    JSON.stringify({ fatal: String(err && err.message ? err.message : err) }),
  );
  process.exit(2);
});
"""


@pytest.fixture(scope="module")
def verify_payload():
    """Run the Node verifier once and return parsed JSON payload."""
    script_path = os.path.join(PROJECT_DIR, "_verify.mjs")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(VERIFY_SCRIPT)

    source_bucket = _source_bucket()
    fork_buckets = [_fork_bucket(i) for i in range(3)]

    env = os.environ.copy()

    try:
        result = subprocess.run(
            ["node", script_path, source_bucket, *fork_buckets],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            env=env,
            timeout=240,
        )
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass

    assert result.returncode == 0, (
        f"Verifier Node script failed (code={result.returncode}).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        pytest.fail(
            f"Could not parse verifier output as JSON: {exc}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    assert "fatal" not in payload, (
        f"Verifier reported fatal error: {payload.get('fatal')}"
    )
    return payload


def test_run_ts_exists_and_uses_required_apis():
    assert os.path.isfile(RUN_TS), f"Expected {RUN_TS} to exist."
    with open(RUN_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    for needle in (
        "@tigrisdata/agent-kit",
        "createForks",
        "@tigrisdata/storage",
        "put",
        "Promise.all",
    ):
        assert needle in content, (
            f"run.ts must reference {needle!r}. Without it the parallel fork "
            f"dispatch contract is not satisfied."
        )


@pytest.mark.parametrize("index", [0, 1, 2])
def test_each_fork_has_correct_worker_output(verify_payload, index):
    entry = verify_payload["forks"].get(str(index))
    assert entry is not None, (
        f"Verifier did not inspect fork index {index}. Payload: {verify_payload}"
    )
    assert "worker_error" not in entry, (
        f"Failed to GET worker/output.txt from {entry.get('bucket')}: "
        f"{entry.get('worker_error')}"
    )
    body = entry.get("worker_body")
    expected = f"worker-{index}"
    assert body == expected, (
        f"worker/output.txt in fork {entry.get('bucket')} should equal "
        f"{expected!r}, got {body!r}"
    )


@pytest.mark.parametrize("index", [0, 1, 2])
def test_each_fork_inherits_seed_dataset(verify_payload, index):
    entry = verify_payload["forks"].get(str(index))
    assert entry is not None, (
        f"Verifier did not inspect fork index {index}. Payload: {verify_payload}"
    )
    assert "seed_error" not in entry, (
        f"Failed to GET seed/dataset.txt from {entry.get('bucket')}: "
        f"{entry.get('seed_error')} — the copy-on-write fork did not inherit "
        f"the source's seeded state."
    )
    body = entry.get("seed_body")
    assert body == "initial", (
        f"seed/dataset.txt in fork {entry.get('bucket')} should equal 'initial' "
        f"(inherited from the source via copy-on-write), got {body!r}"
    )
