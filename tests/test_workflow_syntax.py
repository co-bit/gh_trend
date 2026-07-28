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


def test_workflow_has_concurrency_group_to_prevent_overlapping_pushes():
    data = _load()
    assert data["concurrency"]["group"] == "daily-trend-update"


def test_workflow_runs_all_four_pipeline_scripts_in_order_as_separate_steps():
    data = _load()
    steps = data["jobs"]["update"]["steps"]
    scripts = ("discover.py", "collect.py", "score.py", "render.py")
    run_texts = [step.get("run", "") for step in steps]

    indices = []
    for script in scripts:
        matches = [i for i, text in enumerate(run_texts) if script in text]
        assert len(matches) == 1, f"{script} should appear in exactly one step's run: text"
        indices.append(matches[0])

    assert len(set(indices)) == 4, "each pipeline script must run in its own separate step"
    assert indices == sorted(indices), "pipeline scripts must run in discover -> collect -> score -> render order"
