from meterloss.meter_ingress.contracts import Reading
from meterloss.meter_ingress.register import difference,assemble,revise

def raw(minute, quantity, **edits):
    row=dict(meter="W-11",sector="制冷区",minute=minute,received=minute+1,version=1,count_l=quantity,
             limit_l=10000,max_rate=120,replaced=False,isolated=False,source="脉冲终端")
    row.update(edits)
    return row

def test_rollover_conserves_counter_advances():
    # TRAP-24 实际寄存器翻转按边界进位，不能把反跳全部截零。
    spans,issues=assemble([raw(30,9980),raw(60,30)],70)
    assert spans[0].liters==50 and spans[0].rollover
    assert issues==[]

def test_replaced_meter_quarantines_edge():
    old=Reading.parse(raw(30,9000))
    new=Reading.parse(raw(50,3,replaced=True))
    assert difference(old,new)==(None,"meter_replaced")

def test_do_not_treat_any_reverse_as_rollover():
    rows=[raw(30,4150),raw(60,4100)]
    spans,issues=assemble(rows,65)
    assert spans==() and issues[0]["fault"]=="non_rollover_reverse"

def test_late_revision_does_not_change_cutoff():
    # TRAP-42 晚到修订不能修改更早的历史截面。
    original=[raw(30,700),raw(60,900)]
    update=raw(60,991,received=80,version=2)
    assert assemble(original+[update],79)==assemble(original,79)
    assert assemble(original+[update],80)[0][0].liters==291

def test_conflicting_revisions_are_dropped():
    # TRAP-25 同效修订不同读数不能随顺序覆盖。
    rows=[raw(45,850),raw(45,851)]
    result=revise(rows,60)
    assert result==revise(rows[::-1],60)
    assert result[0]=={} and result[1][0]["fault"]=="revision_conflict"

def test_cadence_under_ninety_minutes():
    bad=assemble([raw(1,20),raw(94,40)],100)
    assert bad[0]==() and bad[1][0]["fault"]=="interval_unreliable"
    assert assemble([raw(0,20),raw(90,40)],100)[0][0].length==90

def test_isolation_spanning_both_sides():
    both=assemble([raw(0,20,isolated=True),raw(10,40,isolated=True)],20)
    mixed=assemble([raw(0,20),raw(10,40,isolated=True)],20)
    assert both[0][0].isolated and not mixed[0][0].isolated

def test_reject_impossible_rate():
    bad=assemble([raw(9,20),raw(10,400)],21)
    assert bad[1][0]["fault"]=="flow_out_of_range"
    frame=assemble([raw(9,10000)],21)
    assert frame[1][0]["fault"]=="invalid_reading"
