from dataclasses import replace
from types import SimpleNamespace
import pytest
from meterloss.water_balance.contracts import RepairReceipt
from meterloss.water_balance.repair_effect import normalize_repair,select_valid_repairs,aggregate_repairs
from meterloss.pipeline import run

def restored(ticket="N-3",meter="分-11",**changes):
    original=dict(ticket=ticket,meter=meter,zone="绿园路",closed=500,fault=True,before_rate=5.,after_rate=2.,
                  night_minutes=60,pressure=400,reviewer="魏工")
    original.update(changes)
    return RepairReceipt(**original)

@pytest.mark.parametrize(("pressure","rate_before","rate_after","total","state"),[
    (400,5,2,180,"确认隔离后节水"), (1600,5,2,90,"确认隔离后节水"),
    (100,5,2,360,"确认隔离后节水"), (400,1,3,-120,"修后未见净流量回落"),
    (400,2,2,0,"修后未见净流量回落"),
])
def test_normalized_flow_keeps_engineering_sign_and_constituent_range(pressure,rate_before,rate_after,total,state):
    input_row=restored(pressure=pressure,before_rate=rate_before,after_rate=rate_after)
    result=normalize_repair(input_row,400)
    assert result.assessed_l==pytest.approx(total)
    assert result.measured_l==60*(rate_before-rate_after)
    assert result.pressure_kpa==pressure and result.diagnostic==state
    assert result.meter==input_row.meter and result.duration_min==60

def test_latest_verified_equivalent_zone_omits_historical_and_orphan_receipts():
    data={r.ticket:r for r in [restored(),restored("N-9",closed=505),restored("N-X",meter="无注册"),
                              restored("N-Y",closed=510,zone="衙门东") ]}
    measured,historical=select_valid_repairs(data,{"分-11":"绿园路"})
    assert measured["分-11"].ticket=="N-9"
    assert len(historical)==3
    by_identity={row["ticket"]:row["reason"] for row in historical}
    assert by_identity=={"N-3":"有更新回执","N-X":"无当前巡检单","N-Y":"复测分区与巡检分区不同"}

def test_unconfirmed_or_worse_measurement_does_not_claim_savings():
    original=restored(pressure=1600)
    denied=restored("N-4","分-17",fault=False,pressure=100)
    increasing=restored("N-5","分-18",before_rate=2.,after_rate=5.)
    field=[SimpleNamespace(meter=item.meter,sector=item.zone) for item in [original,denied,increasing]]
    review=aggregate_repairs({r.ticket:r for r in [original,denied,increasing]},field,400)
    assert review[-1]["assessed_repairs"]==3 and review[-1]["qualified"]==1
    assert review[-1]["metered_saved_l"]==180 and review[-1]["pressure_corrected_saved_l"]==90
    assert next(r["result"] for r in review if r.get("ticket")=="N-4")=="未确认漏点"
    assert next(r["result"] for r in review if r.get("ticket")=="N-5")=="修后未见净流量回落"

@pytest.mark.parametrize("kpa", [0,-1,float("nan"),float("inf")])
def test_invalid_expected_pressure_is_rejected(kpa):
    with pytest.raises(ValueError,match="基准"):
        normalize_repair(restored(),kpa)

def test_sample_stage_generates_trace_for_each_reviewed_pressure_result():
    stage=run()["stages"][-1]["records"]
    verified=[row for row in stage if "pressure_corrected_saved_l" in row]
    assert verified
    assert sum(r["qualified"] for r in verified)>0
    assert all(row["reference_pressure_kpa"]==420 for row in verified)
    assert all(row["metered_saved_l"]>=0 for row in verified)
    sample=next(row for row in stage if row.get("result")=="确认隔离后节水")
    assert sample["valid_minutes"]==90 and sample["source_kpa"]==430
    assert sample["effect_l"]<sample["observed_l"]


def test_round_quota_does_not_change_signed_metered_savings_history():
    low=run(1)
    high=run(14)
    assert low["metrics"]["已派单"]<high["metrics"]["已派单"]
    for packet in (low, high):
        rows=[row for row in packet["stages"][-1]["records"] if "pressure_corrected_saved_l" in row]
        assert len(rows)>0
        assert rows==[row for row in high["stages"][-1]["records"] if "pressure_corrected_saved_l" in row]
        assert rows==[row for row in low["stages"][-1]["records"] if "pressure_corrected_saved_l" in row]
    assert low["stages"][-1]["records"][0]["digest"]!=high["stages"][-1]["records"][0]["digest"]


def test_no_valid_repair_claim_leaves_a_provenance_record_without_positive_total():
    receipt=restored(zone="外部站")
    evidence=aggregate_repairs({receipt.ticket:receipt},[SimpleNamespace(meter=receipt.meter,sector="绿园路")],400)
    assert evidence==[{"ticket":receipt.ticket,"meter":receipt.meter,"reason":"复测分区与巡检分区不同"}]
    assert not any("pressure_corrected_saved_l" in row for row in evidence)


def test_equal_timestamp_repair_tie_is_resolved_by_receipt_identifier():
    original=restored(ticket="R-07")
    corrected=restored(ticket="R-08",after_rate=1.)
    input_rows={r.ticket:r for r in (corrected,original)}
    selected,history=select_valid_repairs(input_rows,{original.meter:original.zone})
    assert selected[original.meter].ticket=="R-08"
    assert history[0]["ticket"]=="R-07"
