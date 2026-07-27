from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "daily.yml"


def _load():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_yaml_is_valid():
    assert _load() is not None


def test_workflow_has_daily_cron_schedule():
    data = _load()
    triggers = data.get("on") or data.get(True)
    assert triggers["schedule"][0]["cron"] == "0 0 * * *"


def test_workflow_supports_manual_dispatch():
    data = _load()
    triggers = data.get("on") or data.get(True)
    assert "workflow_dispatch" in triggers


def test_workflow_grants_contents_write_permission():
    data = _load()
    assert data["permissions"]["contents"] == "write"


def test_workflow_runs_all_four_pipeline_scripts():
    data = _load()
    steps = data["jobs"]["update"]["steps"]
    run_commands = " ".join(step.get("run", "") for step in steps)
    for script in ("discover.py", "collect.py", "score.py", "render.py"):
        assert script in run_commands
