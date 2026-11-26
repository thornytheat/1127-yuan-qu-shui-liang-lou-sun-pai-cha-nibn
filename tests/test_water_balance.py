from types import SimpleNamespace
import pytest
from meterloss.water_balance.audit import receipt_index, assess_repairs, audit_dispatch
from meterloss.field_rounds.contracts import Work

def receipt(ticket="XR",meter="A",**edits):
    values=dict(ticket=ticket,meter=meter,zone="按表",
                closed=340,fault=True,before_rate=4.2,after_rate=.8,night_minutes=50,pressure=400,reviewer="刘班长")
    values.update(edits)
    return values

def word(meter,state="疑似持续漏损"): return SimpleNamespace(meter=meter,status=state)

def job(meter="A",first=300,last=330,work=30):
    return Work(meter,"Q","紧急听漏","周班",work,first,last,"已派单","")

def test_empty_class_has_undefined_recall():
    # TRAP-43 没有已核实漏点，无正例时返回未知召回而不是百分百。
    score=assess_repairs([word("A")],receipt_index([receipt(fault=False)],400))
    assert score.recall is None and score.precision==0
    assert score.confirmed==0 and score.total_checks==1

def test_localized_return_volume():
    score=assess_repairs([word("A")],receipt_index([receipt()],400))
    assert score.recovered_liters==170 and score.confirmed==1
    assert score.precision==score.recall==1

def test_elapsed_closure_windows():
    receipts=[receipt(),receipt("XR-later",closed=401,after_rate=0)]
    assert len(receipt_index(receipts,400))==1
    later=assess_repairs([word("A")],receipt_index(receipts,401))
    assert later.recovered_liters==210

def test_conflicting_repair_key():
    with pytest.raises(ValueError,match="复检"):
        receipt_index([receipt(),receipt(after_rate=2)],400)
    assert len(receipt_index([receipt(),receipt()],400))==1

def test_missed_rare_issue_not_hidden():
    records=[word("A","观察"),word("B","观察")]
    checks=receipt_index([receipt(),receipt("B-T","B",fault=False)],406)
    score=assess_repairs(records,checks)
    assert score.recall==0 and score.missed==1 and score.precision is None

def test_upstream_changes_dispatch_stamp():
    # TRAP-54 策略或台账版本变更，审核签名随依赖变更。
    a=audit_dispatch([job()],{"version":"2","sensor":"K9"})
    b=audit_dispatch([job()],{"version":"2","sensor":"K11"})
    assert a[0]["passed"] and a[0]["digest"]!=b[0]["digest"]

def test_double_assignment_and_overlap():
    data=[job(),job("A",330,360),job("C",350,390,40)]
    state,issues=audit_dispatch(data,{})
    assert not state["passed"]
    assert {r["code"] for r in issues}=={"duplicate_meter","crew_overlap"}

def test_duration_field_rebalanced():
    state,issues=audit_dispatch([job(last=331)],{})
    assert state["crews"]==0 and issues[0]["code"]=="broken_assignment"
