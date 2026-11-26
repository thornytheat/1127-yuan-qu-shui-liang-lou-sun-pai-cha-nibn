import json
import pytest
from meterloss.pipeline import run

def test_water_meter_report_visibly_routes_findings():
    outcome=run()
    assert len(outcome["rows"])>=10 and len(outcome["series"])>=5
    assert len(outcome["stages"])==6
    assert outcome["stages"][-1]["records"][0]["passed"]
    assert outcome["metrics"]["待排查漏损"]>0
    json.dumps(outcome,allow_nan=False)

def test_smaller_round_changes_assignment_book():
    tiny=run(1)
    roomy=run(12)
    assert tiny["metrics"]["已派单"]==1
    assert roomy["metrics"]["已派单"]>1
    assert any(row["dispatch"]=="下一轮" for row in tiny["rows"])

def test_measurement_faults_are_not_silent():
    case=run()
    failures={row.get("fault") for row in case["stages"][0]["records"]}
    assert {"invalid_reading","revision_conflict","meter_replaced"}<=failures
    assert any(row["state"]=="需补采" for row in case["rows"])

def test_summary_reproducibility():
    assert run()==run()
    assert run()["metrics"]["复测回收升"]>0

def test_bad_round_sizes_are_rejected():
    for size in (0,101,True,"15"):
        with pytest.raises(ValueError): run(size)
