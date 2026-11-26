import json

from meterloss.pipeline import run


def test_handoff_section_is_complete_and_json_safe():
    packet = run()["handoff"]
    assert set(packet) == {"decisions", "deferred", "roster", "released", "trace", "summary"}
    json.dumps(packet, ensure_ascii=False, allow_nan=False)
    summary = packet["summary"]
    assert summary["graded_meters"] == len(packet["decisions"])
    assert summary["next_round_meters"] == len(packet["roster"])
    assert summary["released_meters"] == len(packet["released"])
    # 名单中的每块表都标记继续巡检，释放的表均不在名单
    assert all(row["next_round"] for row in packet["roster"])
    released_meters = {row["meter"] for row in packet["released"]}
    assert not (released_meters & {row["meter"] for row in packet["roster"]})


def test_sample_grading_is_never_rewritten_by_receipts():
    outcome = run()
    grades = {row["meter"]: row["state"] for row in outcome["rows"]}
    for decision in outcome["handoff"]["decisions"]:
        assert decision["grade"] == grades[decision["meter"]]


def test_sample_late_receipt_is_deferred_without_touching_current_round():
    packet = run()["handoff"]
    deferred = packet["deferred"]
    assert len(deferred) == 1
    late = deferred[0]
    assert late["ticket"] == "XH-121" and late["meter"] == "ZF-808"
    assert late["closed"] > late["cutoff"]
    # 晚到回执对应的表本期仍按原分级留巡，且没有被派到该回执
    decision = next(row for row in packet["decisions"] if row["meter"] == "ZF-808")
    assert decision["next_round"] is True and decision["ticket"] is None


def test_sample_receipt_without_dispatch_does_not_count_as_repair():
    packet = run()["handoff"]
    notes = {(row["ticket"], row["reason"]) for row in packet["trace"]}
    # ZF-802/807/812/806 本期是观察类表位、没有派单，回执一律不计修复
    assert ("XH-115", "无对应派单，回执不计修复") in notes
    assert ("XH-119", "无对应派单，回执不计修复") in notes
    assert ("XH-118", "无对应派单，回执不计修复") in notes
    assert ("XH-120", "无对应派单，回执不计修复") in notes
    # 这些表全部留在下一班名单
    kept = {row["meter"] for row in packet["roster"]}
    assert {"ZF-802", "ZF-807", "ZF-812", "ZF-806"} <= kept


def test_confirmed_repairs_still_rostered_when_post_repair_window_missing():
    # 样例中所有目标夜窗都早于修复完成时点，因此即便回执确认漏点且读数回落，
    # 缺修后复测夜窗仍不能提前结案。
    packet = run()["handoff"]
    decisions = {row["meter"]: row for row in packet["decisions"]}
    for meter in ("ZF-801", "ZF-804", "ZF-810"):
        row = decisions[meter]
        assert row["next_round"] is True
        assert "修后复测夜窗缺测" in row["reason"]
        assert row["recheck_night"] is None


def test_handoff_metrics_exposed_in_overview():
    metrics = run()["metrics"]
    handoff = run()["handoff"]["summary"]
    assert metrics["下班留巡"] == handoff["next_round_meters"]
    assert metrics["修复释放"] == handoff["released_meters"]


def test_handoff_evidence_attached_to_field_rounds_stage():
    stages = run()["stages"]
    records = stages[4]["records"]
    assert any("交班汇总" in row for row in records)
    assert sum(1 for row in records if "交班裁决" in row) == 15
    assert any("晚到回执" in row for row in records)
    assert any("回执未采用" in row for row in records)


def test_handoff_is_deterministic():
    assert run(6)["handoff"] == run(6)["handoff"]
