from math import isfinite

from ..contracts import RepairReceipt
from .contracts import HandoffDecision

# 复测夜窗供压与回执供压的相对偏差达到该比例即视为口径明显不同，
# 此时单凭读数回落不直接采信为漏损缓解。
PRESSURE_TOLERANCE = 0.10

# 交班裁决状态。
RELEASED = "已确认修复释放名额"
KEEP = "继续进入下一班名单"

# 本期分级中需要持续占用听漏/核查名额的类别。
ACTIVE_GRADES = ("关阀仍过水", "疑似持续漏损", "人工复核", "需补采")


def pressure_mismatch(receipt_pressure, recheck_pressure, tolerance=PRESSURE_TOLERANCE):
    """供压口径明显不同：相对偏差绝对值超过容差（默认 10%）。"""
    if not isfinite(receipt_pressure) or not isfinite(recheck_pressure):
        return False, None
    if recheck_pressure <= 0:
        return False, None
    delta = (receipt_pressure - recheck_pressure) / recheck_pressure
    return abs(delta) >= tolerance, delta


def latest_recheck_night(night_flows, meter, not_before=None):
    """取该表最后一个有可比读数的目标（复测）夜窗；缺测返回 None。

    被隔离标记（计划冲洗、生产夜班、覆盖不足等）的夜窗不可比，不能作为复测依据。
    not_before 给出修复完成分钟时，只采用起点不早于该分钟的夜窗，
    避免把修复前的基线夜窗误当成修后复测证据。
    """
    candidates = [
        row for row in night_flows
        if row.meter == meter and row.target and not row.excluded and row.rate is not None
        and (not_before is None or row.start >= not_before)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: (row.start, row.night))[-1]


def _active_dispatch(work, meter):
    for row in work:
        if row.meter == meter and row.state == "已派单":
            return row
    return None


def _select_receipt(receipts, meter, sector):
    """同一表只取在本次巡检单内、同分区的最新回执；其余回执标记原因。

    返回 (选中的回执或 None, 未采用回执清单)。未采用清单中的字典携带
    ticket/meter/reason，供工作台留痕。
    """
    same_meter = sorted(
        (row for row in receipts if row.meter == meter),
        key=lambda row: (row.closed, row.ticket),
    )
    rejected = []
    chosen = None
    for row in same_meter:
        if row.zone != sector:
            rejected.append({"ticket": row.ticket, "meter": meter,
                             "reason": "回执分区与巡检分区不同"})
            continue
        if chosen is not None:
            rejected.append({"ticket": chosen.ticket, "meter": meter,
                             "reason": "同表已有更新回执"})
        chosen = row
    return chosen, rejected


def verdict_for(finding, work, receipts, night_flows, minimum_rate):
    """对单个水表执行交班裁决，返回 (HandoffDecision, 留痕列表)。"""
    meter = finding.meter
    sector = finding.sector
    grade = finding.status
    trace = []

    dispatch = _active_dispatch(work, meter)
    receipt, rejected = _select_receipt(receipts, meter, sector)
    trace.extend(rejected)

    # 只有不早于修复完成时点的目标夜窗才是修后复测；修复前的夜窗只能作基线。
    recheck = latest_recheck_night(
        night_flows, meter, not_before=receipt.closed if receipt is not None else None
    )

    ticket = receipt.ticket if receipt is not None else None
    receipt_rate = receipt.after_rate if receipt is not None else None
    receipt_pressure = receipt.pressure if receipt is not None else None
    recheck_rate = recheck.rate if recheck is not None else None
    recheck_night = recheck.night if recheck is not None else None
    recheck_pressure = recheck.pressure if recheck is not None else None
    delta = None
    if receipt is not None and recheck is not None:
        _, delta = pressure_mismatch(receipt.pressure, recheck.pressure)

    def keep(reason):
        return HandoffDecision(
            meter, sector, grade, ticket, KEEP, True,
            receipt_rate, recheck_rate, recheck_night, recheck_pressure,
            receipt_pressure, delta, reason,
        ), trace

    def release(reason):
        return HandoffDecision(
            meter, sector, grade, ticket, RELEASED, False,
            receipt_rate, recheck_rate, recheck_night, recheck_pressure,
            receipt_pressure, delta, reason,
        ), trace

    # 没有对应派单的同表记录不计修复：回执不能替代巡检单本身的处置证据。
    if dispatch is None:
        if receipt is not None:
            trace.append({"ticket": receipt.ticket, "meter": meter,
                          "reason": "无对应派单，回执不计修复"})
        if grade in ACTIVE_GRADES:
            return keep("本期无有效派单，沿用原分级继续跟进")
        return keep("观察类表位本期无需派单，保留常态巡检")

    # 有派单但没有可比回执（含晚到已在批次外被剔除的情形）：分级不动。
    if receipt is None:
        if grade in ACTIVE_GRADES:
            return keep("回执未到，不改写本期分级")
        return keep("观察类表位无回执，保留常态巡检")

    # 到达这里的回执都在本次巡检单内且同分区，但仍须通过修复判定。
    if not receipt.fault:
        return keep("回执未确认漏点，不能按修复释放")

    # 修后流量未降：继续占用名额，避免单晚回落造成提前结案。
    if receipt.after_rate <= 0 or receipt.after_rate >= receipt.before_rate:
        return keep("修后流量未见净回落，继续核查")

    # 没有不早于修复时点的复测夜窗：夜窗证据仍停留在修复前，
    # 读数下降只能凭回执自身的修前/修后对照，缺独立夜窗佐证时从严留巡。
    if recheck is None:
        return keep("修后复测夜窗缺测，读数回落暂不采信")

    mismatch, delta = pressure_mismatch(receipt.pressure, recheck.pressure)
    if mismatch:
        return keep("复测供压口径明显不同，读数回落暂不采信")

    # 残余流量仍高于策略最小异常流量，漏点未止；夜窗读数是修后独立证据。
    if recheck.rate is not None and recheck.rate >= minimum_rate:
        return keep("复测夜窗余流仍达异常量级，漏点未止")

    return release("回执确认漏点且复测夜窗余流回落，释放听漏名额")


def build_handoff(findings, work, receipts, night_flows, minimum_rate, recheck_cutoff):
    """形成下一班巡检名单。

    findings: 本期漏损分级（Track 序列，分级不被回执改写）。
    work: 本期巡检配次（Work 序列），只有 state == 已派单 才是有效派单。
    receipts: 全部回执（含可能晚到的记录）；closed > recheck_cutoff 的晚到
              回执不参与本期裁决，留到下一批复核。
    night_flows: 夜窗观测（NightFlow 序列），用于复测夜窗缺测与供压口径判断。
    minimum_rate: 策略最小异常流量 L/min。
    recheck_cutoff: 本班复核截止分钟。

    返回 {"decisions": [...], "deferred": [...], "roster": [...], "summary": {...}}。
    """
    timely = []
    deferred = []
    for row in receipts:
        parsed = row if isinstance(row, RepairReceipt) else RepairReceipt.parse(row)
        if parsed.closed > recheck_cutoff:
            deferred.append({
                "ticket": parsed.ticket, "meter": parsed.meter, "zone": parsed.zone,
                "closed": parsed.closed, "cutoff": recheck_cutoff,
                "reason": "回执晚到，留到下一批复核，不改写本期分级",
            })
        else:
            timely.append(parsed)

    decisions = []
    trace = []
    for finding in sorted(findings, key=lambda item: item.meter):
        decision, notes = verdict_for(finding, work, timely, night_flows, minimum_rate)
        decisions.append(decision)
        trace.extend(notes)

    roster = [row.as_record() for row in decisions if row.next_round]
    released = [row.as_record() for row in decisions
                if row.handoff_state == RELEASED]
    summary = {
        "graded_meters": len(decisions),
        "next_round_meters": len(roster),
        "released_meters": len(released),
        "timely_receipts": len(timely),
        "deferred_receipts": len(deferred),
        "unmatched_receipt_notes": len(trace),
    }
    return {
        "decisions": [row.as_record() for row in decisions],
        "deferred": deferred,
        "roster": roster,
        "released": released,
        "trace": trace,
        "summary": summary,
    }
