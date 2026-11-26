import pytest
from meterloss.field_rounds.assignment import round_book, estimate_task
from meterloss.loss_screen.contracts import Track

def q(key="W1",state="关阀仍过水", excess=4,**more):
    row=dict(meter=key,sector="南区",status=state,night_count=2,stable_count=2,excess=excess,probability=.1,
             persistence=2,cohort="A",reason="测值依据",isolated_rate=4)
    row.update(more)
    return Track(**row)

def crew(**edits):
    row=dict(name="巡检一组",zones=["南区","北区"],hours=200,acoustic=True,valve=True,
             max_cases=4,base="南区",starts=60)
    row.update(edits)
    return row

def test_dual_credentials_for_closed_valve():
    rows=[q(),q("W2","需补采")]
    results=round_book(rows,[crew(valve=False)],10,{})
    assert results[0].state=="值班协调" and results[1].state=="已派单"

def test_explicit_priority_reproducible():
    # TRAP-19 冲突任务按安全等级、超流量、持续夜数和表号排队。
    rows=[q("W2",excess=18,state="疑似持续漏损"),q("W3",excess=2),q(excess=4)]
    actual=round_book(rows,[crew()],1,{})
    assert actual==round_book(rows[::-1],[crew()],1,{})
    assert [(x.meter,x.state) for x in actual]==[("W1","已派单"),("W3","下一轮"),("W2","下一轮")]

def test_travel_changes_next_start():
    rows=[q(),q("W2",state="疑似持续漏损",sector="北区")]
    a,b=round_book(rows,[crew()],5,{"南区>北区":17})
    assert a.to_minute==105 and b.from_minute==122 and b.to_minute==157

def test_blocked_scope():
    rows=[q(sector="西区")]
    assert round_book(rows,[crew()],2,{})[0].state=="值班协调"
    assert not round_book(rows,[crew()],2,{})[0].crew

def test_active_shift_end_inclusive():
    result=round_book([q()],[crew(hours=45)],1,{})
    assert result[0].state=="已派单"
    assert round_book([q()],[crew(hours=44)],1,{})[0].state=="值班协调"

def test_archived_records_use_no_clock():
    rows=[q("X","观察"),q("W2","疑似持续漏损")]
    a,b=round_book(rows,[crew()],1,{})
    assert a.state=="已派单" and b.state=="归档" and b.minutes==0

def test_select_faster_walk_crew():
    teams=[crew(name="远组",base="北区"),crew(name="近组")]
    selected=round_book([q()],teams,1,{"北区>南区":15})
    assert selected[0].crew=="近组"

def test_invalid_walk_plan():
    with pytest.raises(ValueError,match="配额|容量"):
        round_book([],[],0,{})
    with pytest.raises(ValueError,match="重复"):
        round_book([], [crew(),crew()],1,{})
    with pytest.raises(ValueError,match="步行"):
        round_book([q()],[crew()],1,{"南区>南区":-9})
