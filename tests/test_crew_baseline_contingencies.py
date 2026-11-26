import pytest
from fractions import Fraction
from meterloss.field_rounds.emergency_replay import Relief,crew_intervention,compare_dispatch,stress_assign
from meterloss.field_rounds.assignment import round_book
from meterloss.field_rounds.contracts import Work
from meterloss.loss_screen.contracts import Track
from meterloss.night_windows.calendar_replay import estimate_baseline,counter_pressure,jackknife_center
from meterloss.night_windows.contracts import NightFlow
from meterloss.pipeline import run

def fieldteam(name,zone,acoustic,**changes):
    duty=dict(name=name,zones=list(zone),hours=180,acoustic=acoustic,valve=acoustic,
              max_cases=4,base=zone[0],starts=120)
    duty.update(changes)
    return duty

def finding(label,sector,designation,excess):
    return Track(label,sector,designation,5,4,excess,.25,2,"R33","运维核查",None)

def contingent(**updates):
    rule=dict(name="夜班缺勤",sick=["检漏一"],unavailable=[],cap=4,walkway={})
    rule.update(updates)
    return rule

def readiness():
    return [fieldteam("检漏一",("站区","雨泵"),True),fieldteam("抄表二",("站区","雨泵"),False),
            fieldteam("听声三",("雨泵",),True)]

def analysis_batch():
    return (finding("A01","站区","关阀仍过水",6.1),finding("A02","雨泵","疑似持续漏损",5.5),
            finding("A03","雨泵","需补采",0),finding("A04","站区","观察",.3))

def test_shift_absence_reports_only_unserved_safety_and_preserves_baseline():
    cases=analysis_batch()
    roster=readiness()
    existing=round_book(cases,roster,4,{"站区>雨泵":10})
    plan=stress_assign(cases,existing,roster,{"站区>雨泵":10},[contingent()])[0]
    assert plan["active_crews"]==2
    assert plan["visits"]==2 and plan["unserved_safety"]=={"站区":1}
    first=next(row for row in plan["changes"] if row["meter"]=="A01")
    assert first["prior"]=="已派单" and first["after"]=="值班协调"
    assert first["old_crew"]=="检漏一" and first["new_crew"] is None and first["lag"] is None
    assert existing[0].crew=="检漏一" and roster[0]["zones"]==["站区","雨泵"]

def test_asset_closure_retains_other_service_areas_in_crew_scope():
    limits=Relief("避险",(),("雨泵",),5,{})
    after=crew_intervention(readiness(),limits)
    assert [(row["name"],row["zones"]) for row in after]==[("检漏一",["站区"]),("抄表二",["站区"])]
    assert len(readiness()[0]["zones"])==2

def test_walkway_detour_adds_time_only_to_jobs_crossing_closed_link():
    all_cases=(finding("A01","站区","关阀仍过水",6.1),finding("A02","雨泵","疑似持续漏损",4.2))
    roster=readiness()[:1]
    baseline=round_book(all_cases,roster,4,{"站区>雨泵":8})
    changed=contingent(sick=[],walkway={"站区>雨泵":25})
    view=stress_assign(all_cases,baseline,roster,{"站区>雨泵":8},[changed])[0]
    assert view["visits"]==2 and view["unserved_safety"]=={}
    entry=view["changes"][0]
    assert entry["meter"]=="A02" and entry["lag"]==17
    assert entry["old_crew"]==entry["new_crew"]=="检漏一"

def test_compare_stage_distinguishes_missing_from_steady_dispatch():
    job=Work("A","地窖","隔离","甲",40,150,190,"已派单","")
    other=Work("B","大堂","复查","乙",33,150,183,"已派单","")
    assert compare_dispatch([job,other],[other],{"A":"测值可疑"})==[
        {"meter":"A","diagnostic":"测值可疑","prior":"已派单","after":"未复算"}
    ]
    new=compare_dispatch([job],[job,other],{})[0]
    assert new["meter"]=="B" and new["prior"]=="未记录" and new["old_crew"] is None

@pytest.mark.parametrize("adjust",[{"name":""},{"cap":101},{"cap":0},{"walkway":{"站区>雨泵":-2}}])
def test_corrupt_emergency_drill_not_entered_in_roster(adjust):
    payload=contingent(**adjust)
    with pytest.raises(ValueError):
        Relief(**payload)

def baseline(n,rate,pressure=400,**adjust):
    options=dict(meter="L9",sector="吊桥",night=f"N{n}",start=n*1440,target=False,total_l=Fraction(rate*60),
                 sealed_l=Fraction(0),minutes=60,full=60,sealed_min=0,pressure=pressure,excluded=None)
    options.update(adjust)
    return NightFlow(**options)

@pytest.mark.parametrize(("values","expected"), [([], (None,None,None)),([4],(4,None,None)),
    ([1,100],(50.5,1,100)),([2,5,9],(5,3.5,7)),([2,2,8,8],(5.,2,8)),
])
def test_jackknife_centers_use_one_observed_night_per_fold(values,expected):
    assert jackknife_center(values)==expected
    assert jackknife_center(values[::-1])==expected

def test_pressure_normalization_per_night_before_median():
    stable=estimate_baseline([baseline(1,4,1600),baseline(2,3,900),baseline(3,2,400)],400,3)[0]
    assert stable.normalized_lpm==2 and stable.naive_lpm==3 and stable.night_mad==0
    row=counter_pressure([stable],400)[0]
    assert row["pressure_delta"]==round(-1/3,6) and row["instability"]
    assert row["exception"]=="基线稳定"

def test_missing_and_wash_windows_absent_from_confidence_points():
    records=[baseline(1,50,excluded="计划冲洗"),baseline(2,3,minutes=0),baseline(3,2)]
    sparse=estimate_baseline(records,400,4)[0]
    assert sparse.chosen_nights==1 and sparse.low_lpm is None
    assert sparse.exception=="参考晚数不足"
    known=estimate_baseline(records,400,1)[0]
    assert known.exception=="基线稳定" and known.naive_lpm==2
    none=estimate_baseline(records[:2],400,4)[0]
    row=counter_pressure([none],400)[0]
    assert row["pressure_delta"] is None and not row["instability"]
    assert row["night_mad"] is None

def test_exception_marks_sensitivity_to_leaving_one_night_out():
    source=[baseline(1,2),baseline(2,2),baseline(3,7),baseline(4,9)]
    found=estimate_baseline(source,400,4)[0]
    assert found.normalized_lpm==4.5
    assert found.low_lpm==2 and found.high_lpm==7
    assert found.exception=="单夜选择影响偏大"
    with pytest.raises(ValueError):
        estimate_baseline(source,0,1)
    with pytest.raises(ValueError):
        counter_pressure([found],400,2)

def test_application_contingency_stage_evidence_contains_metrics():
    instance=run()
    snapshot=instance["stages"]
    replays=[row for row in snapshot[4]["records"] if "exercise" in row]
    assert len(replays)==2
    assert any(row["changes"] for row in replays)
    assert all(r["active_crews"]>0 and r["visits"]>=0 for r in replays)
    confidence=[row for row in snapshot[1]["records"] if row.get("reference_pressure")==420]
    assert len(confidence)>8
    assert all(r["night_mad"] is None or r["night_mad"]>=0 for r in confidence)
