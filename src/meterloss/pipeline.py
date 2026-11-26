from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean
from .night_windows.calendar_replay import estimate_baseline,counter_pressure
from .water_balance.district_mass import reconcile_districts
from .water_balance.repair_effect import aggregate_repairs
from .loss_screen.isolation_graph import localize
from .field_rounds.emergency_replay import stress_assign
from .meter_ingress.service import validate_readings,meter_evidence
from .night_windows.service import build_baseline,summarize_rates
from .consumption_clusters.service import segment_profiles,best_overlap
from .loss_screen.service import assess,evidence
from .field_rounds.service import route_work,details,crew_summary
from .water_balance.service import finalize,receipt_index
from .water_balance.handoff import build_handoff

SAMPLE=Path(__file__).resolve().parents[2]/"sample_data"

def load(name):
    return json.loads((SAMPLE/name).read_text(encoding="utf-8"))

def handoff_evidence(packet):
    """把交班裁决整理成巡检配次环节可展开的证据记录。"""
    summary=[{"交班汇总":packet["summary"]}]
    decisions=[{"交班裁决":row} for row in packet["decisions"]]
    deferred=[{"晚到回执":row} for row in packet["deferred"]]
    trace=[{"回执未采用":row} for row in packet["trace"]]
    return summary+decisions+deferred+trace

def run(capacity:int|None=None)->dict:
    cap=6 if capacity is None else capacity
    if type(cap) is not int or not 1<=cap<=100:
        raise ValueError("巡检容量须在 1 至 100")
    rules=load("round_controls.json")
    loaded=load("flow_register.json")
    spans,issues=validate_readings(loaded,rules["at"])
    baseline,current,excluded=build_baseline(spans,load("quiet_hour_rules.json"))
    readings=load("district_supply_totals.json")
    district_balance=reconcile_districts(current,readings,rules["recheck"])
    branching=load("isolation_measurements.json")
    localization=localize(branching["pipes"],branching["trials"],rules["recheck"])
    prior=estimate_baseline(baseline+tuple(item for item in excluded if not item.target),rules["policy"]["pressure_anchor"],4)
    prior_notes=counter_pressure(prior,rules["policy"]["pressure_anchor"])
    profiles=load("historical_meter_profiles.json")
    operation,classes=segment_profiles(profiles,load("district_profiles.json"),rules["at"])
    policy,findings=assess(baseline,current,classes,rules["policy"])
    assigned=route_work(findings,rules,cap)
    contingencies=stress_assign(findings,assigned,rules["crews"],rules["walks"],load("crew_contingencies.json"))
    source_fingerprint=hashlib.sha256(json.dumps([loaded,profiles,policy.version],sort_keys=True).encode()).hexdigest()
    returned=load("repairs_returned.json")
    checked,verified,audit=finalize(findings,assigned,returned,rules["recheck"],
        {"capacity":cap,"revision":source_fingerprint,"policy":rules["policy"]})
    handoff=build_handoff(findings,assigned,returned,baseline+current,
                          rules["policy"]["minimum_rate"],rules["recheck"])
    pressure_restoration=aggregate_repairs(receipt_index(returned,rules["recheck"]),findings,policy.pressure_anchor)
    labels=load("cohort_labels.json")
    cluster_score=best_overlap([item["usage"] for item in labels],[classes[item["meter"]]["cohort"] for item in labels])
    assignments={row.meter:row for row in assigned}
    result=[]
    for finding in findings:
        row=assignments[finding.meter]
        result.append({"meter":finding.meter,"sector":finding.sector,"cluster":finding.cohort,"peak":finding.excess,
                       "score":finding.probability,"nights":finding.persistence,"state":finding.status,"crew":row.crew,
                       "dispatch":row.state,"detail":finding.reason+" · "+row.notes})
    by_night=defaultdict(list)
    for row in baseline+current:
        if row.rate is not None and not row.excluded:
            by_night[row.night].append(row.rate)
    graph=[{"label":key,"value":round(mean(samples),3)} for key,samples in sorted(by_night.items())]
    suspicious={"关阀仍过水","疑似持续漏损"}
    return {
        "metrics":{"巡检水表":len(findings),"待排查漏损":sum(row.status in suspicious for row in findings),
                   "已派单":sum(bool(row.crew) for row in assigned),"复测回收升":verified.recovered_liters,
                   "下班留巡":handoff["summary"]["next_round_meters"],
                   "修复释放":handoff["summary"]["released_meters"]},
        "columns":{"meter":"水表","sector":"分区","cluster":"用水簇","peak":"余流 L/min","score":"经验尾概率",
                   "nights":"连续夜","state":"漏损分级","crew":"巡检组","dispatch":"工单状态","detail":"追溯依据"},
        "rows":result,"series":graph,
        "handoff":handoff,
        "stages":[{"title":"抄表校验","summary":f"取得 {len(spans)} 段可用脉冲，隔离 {len(issues)} 处异常",
                   "records":meter_evidence(spans,issues)},
                  {"title":"隔离夜窗","summary":f"有 {len(baseline)} 个历史基线，隔离 {len(excluded)} 条不可比夜窗",
                   "records":summarize_rates(current)+prior_notes},
                  {"title":"用水聚类","summary":f"{operation.size} 个历史画像，最优置换对齐率 {cluster_score:.0%}",
                   "records":list(classes.values())},
                  {"title":"漏损筛查","summary":f"处置版本 {policy.version}，分别评估突增、持续和关阀余流",
                   "records":evidence(findings,policy)+localization},
                  {"title":"巡检配次","summary":f"配额 {cap}，已安排 {len(crew_summary(assigned))} 个值班组",
                   "records":details(assigned)+contingencies+handoff_evidence(handoff)},
                  {"title":"水量追溯","summary":"工单与回执核验通过" if checked["passed"] else "工单存在时段冲突",
                   "records":audit+[item.describe() for item in district_balance]+pressure_restoration}],
    }
