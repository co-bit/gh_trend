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


def test_workflow_runs_all_pipeline_scripts_in_order_as_separate_steps():
    data = _load()
    steps = data["jobs"]["update"]["steps"]
    scripts = ("discover.py", "collect.py", "score.py", "describe.py", "render.py")
    run_texts = [step.get("run", "") for step in steps]

    indices = []
    for script in scripts:
        matches = [i for i, text in enumerate(run_texts) if script in text]
        assert len(matches) == 1, f"{script} should appear in exactly one step's run: text"
        indices.append(matches[0])

    assert len(set(indices)) == len(scripts), "each pipeline script must run in its own separate step"
    assert indices == sorted(indices), (
        "pipeline scripts must run in discover -> collect -> score -> describe -> render order"
    )


def test_describe_step_receives_gemini_api_key():
    data = _load()
    steps = data["jobs"]["update"]["steps"]
    describe_steps = [s for s in steps if "describe.py" in s.get("run", "")]
    assert len(describe_steps) == 1
    assert "GEMINI_API_KEY" in describe_steps[0].get("env", {})


def test_remote_sync_happens_before_score_computation():
    # data/latest_scores.json・docs/index.htmlは派生ファイルなので、pullは
    # それらを計算するscore.pyより前に行う必要がある(後で行うと、bot自身が
    # 計算した派生ファイルとリモートの派生ファイルがマージコンフリクトを
    # 起こし、収集した1回分のデータが丸ごと失われる。2026-08-02に実際に発生)。
    data = _load()
    steps = data["jobs"]["update"]["steps"]
    run_texts = [step.get("run", "") for step in steps]

    pull_indices = [i for i, text in enumerate(run_texts) if "git pull --rebase" in text]
    score_indices = [i for i, text in enumerate(run_texts) if "score.py" in text]

    assert len(pull_indices) == 1
    assert len(score_indices) == 1
    assert pull_indices[0] < score_indices[0]


def test_final_push_step_has_no_pull_rebase():
    # 最終pushの直前にもう一度pull --rebaseすると、score.py/render.pyが
    # 作った派生ファイルが再びマージ対象になり同じ問題が再発するため禁止。
    data = _load()
    steps = data["jobs"]["update"]["steps"]
    push_steps = [s for s in steps if "git push" in s.get("run", "")]
    assert len(push_steps) == 1
    assert "git pull --rebase" not in push_steps[0]["run"]
