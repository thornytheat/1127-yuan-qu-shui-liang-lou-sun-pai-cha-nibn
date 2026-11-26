import pytest
from fractions import Fraction
from meterloss.night_windows.contracts import NightWindow
from meterloss.night_windows.integration import measure, assert_windows, slice_nights, instant_overlap
from meterloss.meter_ingress.contracts import Span

def night(**updates):
    values=dict(key="周二",start=15,stop=75,target=True,industrial=False,flush=False,rain=0,
                sector="环东",pipe_kpa=420,ambient=9)
    values.update(updates)
    return NightWindow(**values)

def interval(left,right,l,isolated=False):
    return Span("A1","环东",left,right,l,isolated,False)

def test_half_open_no_double_count():
    # TRAP-23 相邻夜窗共享端点但不重复分水。
    pulse=interval(30,90,240)
    first=measure("A1",[pulse],night(start=30,stop=60))
    second=measure("A1",[pulse],night(start=60,stop=90))
    assert first.total_l+second.total_l==240
    assert instant_overlap(30,60,60,90)==0

def test_exact_fraction_without_per_window_rounding():
    pulse=interval(19,70,239)
    a=measure("A1",[pulse],night(start=19,stop=31))
    b=measure("A1",[pulse],night(start=31,stop=70))
    assert a.total_l==Fraction(239*12,51)
    assert a.total_l+b.total_l==239

def test_closed_heat_isolated():
    flow=measure("A1",[interval(15,45,50,True),interval(45,75,100)],night())
    assert flow.sealed_min==30 and flow.sealed_l==50
    assert flow.test_rate==5/3 and flow.rate==2.5

def test_production_and_wash_excluded():
    reading=interval(15,75,140)
    assert measure("A1",[reading],night(flush=True)).excluded=="计划冲洗"
    assert measure("A1",[reading],night(industrial=True)).excluded=="夜班生产"
    assert measure("A1",[reading],night()).excluded is None

def test_below_required_coverage():
    entry=measure("A1",[interval(19,46,20)],night())
    assert entry.coverage==.45 and entry.excluded=="覆盖不足"
    assert measure("A1",[],night()).rate is None

def test_cross_sector_windows_independent():
    assert len(assert_windows([night(),night(sector="环北")]))==2
    with pytest.raises(ValueError,match="重叠"):
        assert_windows([night(),night(start=70,stop=90)])

def test_validate_windows_and_thresholds():
    with pytest.raises(ValueError,match="结束"):
        assert_windows([night(stop=8)])
    with pytest.raises(ValueError,match="覆盖"):
        slice_nights([],[],0)

def test_overlapping_sampling_rejected():
    with pytest.raises(ValueError,match="重叠"):
        measure("A1",[interval(15,65,70),interval(35,75,40)],night())
