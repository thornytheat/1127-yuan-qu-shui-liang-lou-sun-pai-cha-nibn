from fractions import Fraction

import pytest

from meterloss.field_rounds.contracts import Work
from meterloss.loss_screen.contracts import Track
from meterloss.night_windows.contracts import NightFlow
from meterloss.water_balance.contracts import RepairReceipt
from meterloss.water_balance.handoff import build_handoff, latest_recheck_night, pressure_mismatch, verdict_for
from meterloss.water_balance.handoff.contracts import HandoffDecision

ZONE = "南区"
CUTOFF = 1000
MIN_RATE = 1.1


def finding(meter="M1", status="疑似持续漏损", sector=ZONE, excess=4.0):
    return Track(meter, sector, status, 2, 2, excess, 0.2, 2, "C1", "测值依据", None)


def receipt(ticket="R1", meter="M1", zone=ZONE, closed=900, fault=True,
            before=10.0, after=2.0, pressure=400.0, night_minutes=90):
    return RepairReceipt(
        ticket=ticket, meter=meter, zone=zone, closed=closed, fault=fault,
        before_rate=before, after_rate=after, night_minutes=night_minutes,
        pressure=pressure, reviewer="班长",
    )


def work(meter="M1", sector=ZONE, state="已派单", crew="甲组"):
    if state != "已派单":
        return Work(meter, sector, "夜间听漏", None, 35, None, None, state, "")
    return Work(meter, sector, "夜间听漏", crew, 35, 850, 885, state, "")


def night(might="N8", meter="M1", sector=ZONE, start=930, rate=1.0, pressure=400.0,
          target=True, excluded=None, full=90, minutes=90):
    total = Fraction(round(rate * minutes * 1000), 1000)
    return NightFlow(meter, sector, might, start, target, total, Fraction(0),
                     minutes, full, 0, pressure, excluded)


def decision(meter="M1", **edits):
    base = dict(meter=meter, sector=ZONE, grade="疑似持续漏损", ticket=None,
                handoff_state="继续进入下一班名单", next_round=True,
                receipt_rate=None, recheck_rate=None, recheck_night=None,
                recheck_pressure=None, receipt_pressure=None, pressure_delta=None,
                reason="x")
    base.update(edits)
    return HandoffDecision(**base)


# ---------- 供压口径 ----------

@pytest.mark.parametrize(("receipt_p", "window_p", "mismatch"), [
    (440, 400, True),    # +10% 边界外侧
    (360, 400, True),    # -10% 边界外侧
    (440.0 - 0.01, 400, False),
    (400, 400, False),
    (430, 400, False),   # 7.5% 在容差内
])
def test_pressure_mismatch_uses_relative_tolerance(receipt_p, window_p, mismatch):
    flagged, delta = pressure_mismatch(receipt_p, window_p)
    assert flagged is mismatch
    assert delta == pytest.approx((receipt_p - window_p) / window_p)


def test_pressure_mismatch_guards_against_non_finite_and_zero():
    assert pressure_mismatch(float("nan"), 400) == (False, None)
    assert pressure_mismatch(400, 0) == (False, None)


# ---------- 复测夜窗选择 ----------

def test_latest_recheck_skips_excluded_and_pretarget_windows():
    flows = [
        night("N1", start=100, rate=9.0),
        night("N2", start=500, rate=8.0, excluded="覆盖不足"),
        night("N3", start=930, rate=1.0),
    ]
    picked = latest_recheck_night(flows, "M1", not_before=900)
    assert picked.night == "N3"
    # 修复完成前开启的目标夜窗不能作为修后复测
    assert latest_recheck_night(flows, "M1", not_before=950) is None
    # 不带时点约束时仍只取可比目标窗，排除被隔离的窗口
    assert latest_recheck_night(flows, "M1").night == "N3"


def test_latest_recheck_returns_none_when_all_windows_missing():
    missing = night(rate=0.0, minutes=0, excluded="覆盖不足")
    assert latest_recheck_night([missing], "M1", 900) is None


# ---------- 修复释放（正向路径） ----------

def test_confirmed_repair_with_quiet_post_repair_window_releases_slot():
    flows = [night(start=930, rate=0.8, pressure=400.0)]
    out, trace = verdict_for(finding(), [work()], [receipt()], flows, MIN_RATE)
    assert out.handoff_state == "已确认修复释放名额" and out.next_round is False
    assert out.ticket == "R1" and out.recheck_night == "N8"
    assert trace == []


def test_release_requires_post_repair_window_not_pre_repair_baseline():
    # 夜窗在修复完成之前结束，属修复前基线，缺修后复测，必须留巡
    flows = [night(start=800, rate=0.5)]
    out, _ = verdict_for(finding(), [work()], [receipt(closed=900)], flows, MIN_RATE)
    assert out.next_round is True and "修后复测夜窗缺测" in out.reason


def test_recheck_pressure_difference_blocks_release_even_when_rate_dropped():
    flows = [night(start=930, rate=0.9, pressure=300.0)]
    out, _ = verdict_for(finding(), [work()], [receipt(pressure=400.0)], flows, MIN_RATE)
    assert out.next_round is True and "供压口径明显不同" in out.reason
    assert out.pressure_delta == pytest.approx((400 - 300) / 300)


def test_missing_recheck_window_blocks_release_despite_receipt_drop():
    out, _ = verdict_for(finding(), [work()], [receipt()], [], MIN_RATE)
    assert out.next_round is True and "修后复测夜窗缺测" in out.reason


def test_unconfirmed_fault_receipt_never_releases():
    flows = [night(start=930, rate=0.5)]
    out, _ = verdict_for(finding(), [work()], [receipt(fault=False)], flows, MIN_RATE)
    assert out.next_round is True and "未确认漏点" in out.reason


@pytest.mark.parametrize(("before", "after"), [(10.0, 10.0), (2.0, 5.0)])
def test_flow_not_reduced_after_repair_keeps_meter_on_roster(before, after):
    flows = [night(start=930, rate=0.4)]
    out, _ = verdict_for(finding(), [work()], [receipt(before=before, after=after)], flows, MIN_RATE)
    assert out.next_round is True and "未见净回落" in out.reason


def test_residual_flow_above_minimum_rate_keeps_meter_on_roster():
    flows = [night(start=930, rate=1.5)]
    out, _ = verdict_for(finding(), [work()], [receipt(after=1.4)], flows, MIN_RATE)
    assert out.next_round is True and "漏点未止" in out.reason


def test_scaled_after_flow_above_window_observation_keeps_meter():
    # 供压口径差异先拦截：回执 360 vs 夜窗 300，偏差 20% 超出 10% 容差
    flows = [night(start=930, rate=0.9, pressure=300.0)]
    out, _ = verdict_for(
        finding(), [work()], [receipt(after=1.0, pressure=360.0)], flows, MIN_RATE
    )
    assert out.next_round is True and "供压口径明显不同" in out.reason
    # 口径一致时，是否留巡由夜窗余流是否仍达异常量级裁决，不被单次回执读数替代
    flows2 = [night(start=930, rate=1.5, pressure=400.0)]
    out2, _ = verdict_for(
        finding(), [work()], [receipt(after=1.0, pressure=400.0)], flows2, MIN_RATE
    )
    assert out2.next_round is True and "漏点未止" in out2.reason


# ---------- 派单与回执配对 ----------

def test_receipt_without_matching_dispatch_does_not_count_as_repair():
    flows = [night(start=930, rate=0.4)]
    out, trace = verdict_for(
        finding(), [work(state="下一轮")], [receipt()], flows, MIN_RATE
    )
    assert out.next_round is True and out.ticket == "R1"
    assert trace == [{"ticket": "R1", "meter": "M1", "reason": "无对应派单，回执不计修复"}]


def test_zone_mismatch_receipt_is_rejected_and_grade_holds():
    out, trace = verdict_for(
        finding(sector=ZONE), [work(sector=ZONE)], [receipt(zone="北片区")], [], MIN_RATE
    )
    assert out.next_round is True and out.ticket is None
    assert trace == [{"ticket": "R1", "meter": "M1", "reason": "回执分区与巡检分区不同"}]


def test_latest_receipt_wins_while_older_one_is_traced():
    rows = [receipt(ticket="R1", closed=900, after=2.0),
            receipt(ticket="R2", closed=920, after=0.5)]
    flows = [night(start=930, rate=0.4)]
    out, trace = verdict_for(finding(), [work()], rows, flows, MIN_RATE)
    assert out.ticket == "R2" and out.handoff_state == "已确认修复释放名额"
    assert {"ticket": "R1", "meter": "M1", "reason": "同表已有更新回执"} in trace


def test_equal_timestamp_tie_resolved_by_ticket_identifier():
    rows = [receipt(ticket="R9", closed=900, after=0.6),
            receipt(ticket="R8", closed=900, after=0.6)]
    flows = [night(start=930, rate=0.4)]
    out, _ = verdict_for(finding(), [work()], rows, flows, MIN_RATE)
    assert out.ticket == "R9"


def test_no_receipt_keeps_active_grade_without_rewriting_it():
    out, _ = verdict_for(finding(status="关阀仍过水"), [work()], [], [], MIN_RATE)
    assert out.grade == "关阀仍过水" and out.next_round is True
    assert "回执未到" in out.reason


def test_observation_grade_without_dispatch_stays_routine():
    out, _ = verdict_for(finding(status="观察"), [work(state="归档")], [], [], MIN_RATE)
    assert out.next_round is True and "常态巡检" in out.reason


# ---------- 批次构建：晚到回执与不新增派工 ----------

def test_late_receipt_is_deferred_and_does_not_change_current_grading():
    late = receipt(ticket="LATE", closed=CUTOFF + 15)
    packet = build_handoff(
        [finding()], [work()], [late], [], MIN_RATE, CUTOFF
    )
    assert packet["deferred"] == [{
        "ticket": "LATE", "meter": "M1", "zone": ZONE, "closed": CUTOFF + 15,
        "cutoff": CUTOFF,
        "reason": "回执晚到，留到下一批复核，不改写本期分级",
    }]
    decision_row = packet["decisions"][0]
    assert decision_row["ticket"] is None
    assert decision_row["next_round"] is True
    assert "回执未到" in decision_row["reason"]
    assert packet["summary"]["deferred_receipts"] == 1
    assert packet["summary"]["timely_receipts"] == 0


def test_build_handoff_is_read_only_and_creates_no_new_dispatch():
    jobs = [work()]
    before = tuple(jobs)
    packet = build_handoff(
        [finding()], jobs, [receipt()], [night(start=930, rate=0.4)], MIN_RATE, CUTOFF
    )
    # 重试同批复盘不新增任何派工：配次对象原样保留，输出只含裁决证据
    assert tuple(jobs) == before
    assert all("crew" not in row for row in packet["decisions"])
    assert packet["summary"]["released_meters"] == 1
    assert packet["roster"] == []


def test_build_handoff_roster_lists_every_kept_meter_once_and_sorted():
    findings = [finding("M2"), finding("M1", status="关阀仍过水")]
    jobs = [work("M2"), work("M1")]
    packets = [
        receipt("R1", "M1", after=0.5),
        receipt("R2", "M2", fault=False),
    ]
    flows = [night(meter="M1", start=930, rate=0.4),
             night(meter="M2", start=930, rate=0.4)]
    packet = build_handoff(findings, jobs, packets, flows, MIN_RATE, CUTOFF)
    roster = [row["meter"] for row in packet["roster"]]
    assert roster == ["M2"]  # M1 释放，M2 未确认漏点留巡
    assert [row["meter"] for row in packet["decisions"]] == ["M1", "M2"]
    assert packet["summary"] == {
        "graded_meters": 2, "next_round_meters": 1, "released_meters": 1,
        "timely_receipts": 2, "deferred_receipts": 0, "unmatched_receipt_notes": 0,
    }


def test_raw_receipt_dicts_are_parsed_inside_build_handoff():
    packet = build_handoff(
        [finding()], [work()], [receipt().as_record()],
        [night(start=930, rate=0.4)], MIN_RATE, CUTOFF
    )
    assert packet["summary"]["timely_receipts"] == 1
    assert packet["summary"]["released_meters"] == 1


def test_decision_record_rounds_floating_fields():
    flows = [night(start=930, rate=0.4, pressure=430.0)]
    out, _ = verdict_for(finding(), [work()], [receipt(pressure=400.0)], flows, MIN_RATE)
    record = out.as_record()
    assert record["recheck_pressure"] == 430.0
    assert isinstance(record["pressure_delta"], float)
