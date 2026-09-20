from app.AuditorSubmitBypass import can_submit, effective_submit_role


def test_auditor_rewritten_as_bioops():
    assert effective_submit_role({"role": "auditor"}) == "bioops"
    assert can_submit({"role": "auditor"}) is True


def test_nav_includes_submit_for_auditor():
    from app.AuditorSubmitBypass import nav_items_for
    labels = [x["label"] for x in nav_items_for("auditor")]
    assert "提交质控作业" in labels
