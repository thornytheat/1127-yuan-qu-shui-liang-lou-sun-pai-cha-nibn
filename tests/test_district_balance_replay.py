import pytest
from dataclasses import replace
from fractions import Fraction
from meterloss.night_windows.contracts import NightFlow
from meterloss.water_balance.district_mass import SupplyAccount, agreed_accounts, reconcile_districts
from meterloss.pipeline import run

def factory(**changes):
    default=dict(sector="纺织园西",night="辛夜",before_l=40000,after_l=41850,storage_at_start=2400,
                 storage_at_end=2550,exempted_l=100,sample_coverage=.98,edition=1,known_at=320)
    default.update(changes)
    return default

def submeter(name="B-13", **changes):
    default=dict(meter=name,sector="纺织园西",night="辛夜",start=300,target=True,total_l=Fraction(1000),
                 sealed_l=Fraction(0),minutes=90,full=90,sealed_min=0,pressure=390,excluded=None)
    default.update(changes)
    return NightFlow(**default)

def test_storage_fill_and_legitimate_discharge_are_removed_before_balance():
    report=reconcile_districts([submeter(),submeter("B-14",total_l=Fraction(850,3))],[factory()],400)[0]
    assert report.supply_l==1600
    assert report.accounted_l==Fraction(3850,3)
    assert report.unaccounted_l==Fraction(950,3)
    assert report.accounted_l+report.unaccounted_l==report.supply_l
    assert report.status=="总表净损耗偏高"
    shown=report.describe()
    assert shown["usable_meters"]==2 and shown["unexplained_share"]==pytest.approx(950/4800,abs=.000001)

def test_empty_and_limited_total_meter_stays_incomplete_even_with_submeters():
    at=reconcile_districts([], [factory()],420)[0]
    below=reconcile_districts([submeter()],[factory(sample_coverage=.75)],420)[0]
    assert at.unaccounted_share is None and below.unaccounted_share is None
    assert at.branches==at.usable==0
    assert below.branches==below.usable==1
    assert at.status==below.status=="总分表同观测不足"

@pytest.mark.parametrize(("quantity","state","share"),[
    (1600,"供水差额在限值内",0), (1360,"供水差额在限值内",.15),
    (1359,"总表净损耗偏高",.150625), (1700,"分表总量超过供水总表",-.0625),
])
def test_net_loss_is_unrounded_and_threshold_is_strict(quantity,state,share):
    report=reconcile_districts([submeter(total_l=Fraction(quantity))],[factory()],420)[0]
    assert report.status==state and report.unaccounted_share==share
    assert report.unaccounted_l==1600-quantity

def test_out_of_service_meters_do_not_contaminate_totals():
    active=[submeter("00"),submeter("01",total_l=Fraction(358),minutes=45),
            submeter("02",total_l=Fraction(100),excluded="计划冲洗")]
    data=reconcile_districts(active,[factory()],330,minimum_share=.7)[0]
    assert data.branches==3 and data.usable==1 and data.accounted_l==1000
    assert data.unaccounted_share is None and data.status=="总分表同观测不足"

def test_visible_version_overwrites_prior_without_editing_stored_receipt():
    initial=factory()
    revised=factory(edition=2,known_at=410,after_l=42100)
    old=reconcile_districts([submeter()],[initial,revised],400)[0]
    new=reconcile_districts([submeter()],[initial,revised],410)[0]
    assert old.supply_l==1600 and new.supply_l==1850
    assert initial["after_l"]==41850
    with pytest.raises(ValueError,match="同效"):
        agreed_accounts([initial, factory(after_l=41900)],400)

def test_disconnected_night_identity_never_matches_other_zone():
    decoys=[submeter(sector="高新区东"),submeter(night="庚夜夜")]
    state=reconcile_districts(decoys,[factory()],430)[0]
    assert state.branches==0 and state.status=="总分表同观测不足"
    with pytest.raises(ValueError,match="重复支路"):
        reconcile_districts([submeter(),submeter()],[factory()],420)

def test_negative_effective_supply_is_called_out_as_storage_error():
    unusual=factory(storage_at_end=9000)
    calc=SupplyAccount(**unusual)
    summary=reconcile_districts([submeter()],[unusual],420)[0]
    assert calc.net_available<0 and summary.supply_l==calc.net_available
    assert summary.status=="水池交换量异常" and summary.unaccounted_share is None

@pytest.mark.parametrize("bad",[{"before_l":-1},{"after_l":38909},{"edition":0},{"sample_coverage":1.01},{"exempted_l":1.1}])
def test_corrupt_supply_balance_record_rejected(bad):
    with pytest.raises(ValueError):
        SupplyAccount(**factory(**bad))

def test_operator_packet_includes_visible_supply_night_for_each_zone():
    response=run()
    packet=[row for row in response["stages"][-1]["records"] if "balance_state" in row]
    assert len(packet)==6
    assert len({row["sector"] for row in packet})==3
    assert any(row["balance_state"]=="总分表同观测不足" for row in packet)
    for row in packet:
        assert row["branch_l"]+row["unexplained_l"]==pytest.approx(row["supply_l"],abs=.002)
