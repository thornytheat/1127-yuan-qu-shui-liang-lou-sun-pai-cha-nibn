from fractions import Fraction
from meterloss.loss_screen.contracts import LossPolicy
from meterloss.loss_screen.scoring import normalized_rate,tail_probability,screen
from meterloss.night_windows.contracts import NightFlow

def flow(i,q,**edits):
    args=dict(meter="D3",sector="东翼",night=f"N{i}",start=i*1440,target=i>=5,total_l=Fraction(q*60),
              sealed_l=Fraction(0),minutes=60,full=60,sealed_min=0,pressure=400,excluded=None)
    args.update(edits)
    return NightFlow(**args)

def policy(**edits):
    args=dict(version="L2",minimum_rate=1.,minimum_persistence=2,pressure_anchor=400.,isolation_alarm=3.,
              calibration_cap=.3,cohort_reject=5.,minimum_samples=4)
    args.update(edits)
    return LossPolicy(**args)

def group(distance=0): return {"D3":{"cohort":"M-12","distance":distance,"typical_lpm":2.}}

def normal(): return [flow(i,2) for i in range(1,5)]

def test_finite_sample_tail_reference():
    # TRAP-44 校准排名保留有限样本保守项，空基线没有概率。
    assert tail_probability([1,3,5,7],6)==.4
    assert tail_probability([1,3,5,7],8)==.2
    assert tail_probability([],6) is None

def test_pressurization_changes_baseline_comparison():
    assert normalized_rate(flow(1,4,pressure=1600),400)==2
    assert normalized_rate(flow(1,5,minutes=0),400) is None

def test_persistent_drip_routes_for_investigation():
    rows=screen(normal(),[flow(5,5),flow(6,5)],group(),policy())
    assert rows[0].status=="疑似持续漏损"
    assert rows[0].persistence==2 and rows[0].probability==.2 and rows[0].excess==3

def test_flush_breaks_run():
    rows=screen(normal(),[flow(5,5),flow(6,7,excluded="冲洗"),flow(7,5)],group(),policy())
    assert rows[0].persistence==1 and rows[0].status=="观察"

def test_far_cohort_refuses_auto_decision():
    # TRAP-44 经验尾概率虽小，远离训练画像不能直接按漏损生成正式通知。
    rows=screen(normal(),[flow(5,5),flow(6,5)],group(9),policy())
    assert rows[0].status=="人工复核" and rows[0].probability==.2

def test_closure_sensor_override():
    rows=screen([], [flow(5,4,sealed_l=Fraction(301),sealed_min=50)],group(9),policy())
    assert rows[0].status=="关阀仍过水" and rows[0].isolated_rate==6.02

def test_absent_profile_and_no_valid_target():
    samples=[flow(5,4,excluded="覆盖不足")]
    assert screen(normal(),samples,{},policy())[0].status=="资料缺失"
    assert screen(normal(),samples,group(),policy())[0].status=="需补采"

def test_gap_breaks_consecutive_evidence():
    rows=screen(normal(),[flow(5,5),flow(8,6)],group(),policy())
    assert rows[0].persistence==1 and rows[0].status=="观察"
