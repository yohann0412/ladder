"""F5 acceptance: a recorded real resolver run is audited and ingested; bad runs are refused."""

import json
import shutil
from pathlib import Path

from conftest import LADDER, REPO_ROOT, Experiment, git, read_json, run

RECORDED = REPO_ROOT / "fixtures" / "recorded" / "fx03-llm-raw"


def _install_recorded_run(task: dict[str, str], transcript: Path, extra_read: str | None) -> None:
    out = Path(task["output_dir"])
    shutil.copytree(RECORDED / "output", out, dirs_exist_ok=True)
    text = (RECORDED / "transcript.jsonl").read_text()
    text = text.replace("$TASK_DIR", task["task_dir"]).replace("$OUTPUT_DIR", task["output_dir"])
    lines = text.splitlines()
    if extra_read is not None:
        call = {
            "type": "assistant",
            "message": {
                "id": "msg_extra",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Read",
                        "input": {"file_path": extra_read},
                    }
                ],
            },
        }
        lines.insert(2, json.dumps(call))
    transcript.write_text("\n".join(lines) + "\n")


def test_resolver_protocol(fx_resolved: Experiment, fixture_dir: Path, tmp_path: Path) -> None:
    fx = fx_resolved
    fx.ladder("workspace", "build", "fx03")
    fx.ladder("rung", "git", "fx03")
    fx.ladder("rung", "structural", "fx03", "--tool", "weave")
    fx.ladder("resolve", "plan", "fx03")
    plan = fx.result("fx03", "resolver-plan")
    assert [(r["rung"], r["run"]) for r in plan["runs"]] == [("llm-raw", 1), ("llm-post-weave", 1)]

    fx.ladder("resolve", "prepare", "fx03", "--rung", "llm-raw", "--run", "1")
    task = fx.result("fx03", "resolver-llm-raw-run-1-task")
    assert task["status"] == "pending" and task["files"] == ["textkit/core.py"]
    task_dir = Path(task["task_dir"])
    assert task["spawn_line"] == f"Read {task_dir}/PROMPT.md and follow it exactly."
    prompt = (task_dir / "PROMPT.md").read_text()
    assert "$" not in prompt.split("```json")[0]
    for name in ("base", "a", "b", "conflicted"):
        assert (task_dir / "files" / "1" / name).is_file(), name
    snapshot = Path(task["snapshot_dir"])
    assert snapshot.is_relative_to(task_dir)
    assert len(git(snapshot, "rev-list", "--all").splitlines()) == 3
    assert git(snapshot, "diff", "--name-only", "--diff-filter=U") == "textkit/core.py"
    pending = fx.ladder("resolve", "pending").stdout
    assert task["spawn_line"] in pending

    transcript = tmp_path / "run-1.jsonl"
    _install_recorded_run(task, transcript, extra_read=None)
    fx.ladder(
        "resolve",
        "finalize",
        "fx03",
        "--rung",
        "llm-raw",
        "--run",
        "1",
        "--transcript",
        str(transcript),
    )
    record = fx.result("fx03", "resolver-llm-raw-run-1")
    assert record["status"] == "ok" and record["failure"] is None and record["violations"] == []
    assert [(f["path"], f["action"]) for f in record["files"]] == [("textkit/core.py", "keep")]
    assert record["tool_calls"] >= 2 and record["duration_ms"] is not None
    assert record["tokens"]["output_tokens"] > 0
    assert "model" not in json.dumps(record)

    resolved3 = next(
        s for s in read_json(fixture_dir / "manifest.json")["scenarios"] if s["pair_id"] == "fx03"
    )["resolved"]
    human = tmp_path / "human.py"
    human.write_text(git(fixture_dir / "repo", "show", f"{resolved3}:textkit/core.py") + "\n")
    produced = Path(task["output_dir"]) / "files" / "textkit" / "core.py"
    verdict = json.loads(run([LADDER, "compare", str(produced), str(human)]).stdout)
    assert verdict["equivalent"] is True

    fx.ladder("resolve", "prepare", "fx03", "--rung", "llm-raw", "--run", "2")
    task2 = fx.result("fx03", "resolver-llm-raw-run-2-task")
    transcript2 = tmp_path / "run-2.jsonl"
    _install_recorded_run(task2, transcript2, extra_read=str(fx.work / "truth" / "fx03"))
    fx.ladder(
        "resolve",
        "finalize",
        "fx03",
        "--rung",
        "llm-raw",
        "--run",
        "2",
        "--transcript",
        str(transcript2),
    )
    violated = fx.result("fx03", "resolver-llm-raw-run-2")
    assert violated["status"] == "failed" and violated["failure"] == "protocol_violation"
    assert any("Read" in v for v in violated["violations"])

    workspace = Path(fx.result("fx03", "workspace-replay")["path"])
    git(workspace, "update-ref", "refs/heads/extra", git(workspace, "rev-parse", "a"))
    refused = fx.ladder(
        "resolve", "prepare", "fx03", "--rung", "llm-raw", "--run", "3", check=False
    )
    assert refused.returncode != 0 and "refs/heads/extra" in refused.stdout + refused.stderr
    git(workspace, "update-ref", "-d", "refs/heads/extra")

    (fx.work / "truth" / "fx03").mkdir(parents=True)
    refused = fx.ladder(
        "resolve", "prepare", "fx03", "--rung", "llm-raw", "--run", "3", check=False
    )
    assert refused.returncode != 0 and "truth" in (refused.stdout + refused.stderr).lower()
