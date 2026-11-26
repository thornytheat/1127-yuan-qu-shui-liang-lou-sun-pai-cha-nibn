from collections import defaultdict
from .contracts import Reading, Span

def revise(raw,cutoff):
    groups=defaultdict(list)
    rejected=[]
    for record in raw:
        try:
            reading=Reading.parse(record)
            if reading.received < reading.minute or reading.count_l>=reading.limit_l:
                raise ValueError("快照时钟或寄存器范围无效")
        except ValueError as error:
            rejected.append({"fault":"invalid_reading","meter":record.get("meter"),"detail":str(error)})
            continue
        if reading.received <= cutoff:
            groups[(reading.meter,reading.minute)].append(reading)
    current=defaultdict(list)
    for (meter,minute),rows in sorted(groups.items()):
        best=max(r.version for r in rows)
        candidates=[r for r in rows if r.version==best]
        values={(r.count_l,r.sector,r.limit_l,r.max_rate,r.replaced,r.isolated) for r in candidates}
        if len(values)>1:
            rejected.append({"fault":"revision_conflict","meter":meter,"minute":minute})
        else:
            chosen=max(candidates,key=lambda r:(r.received,r.source))
            current[meter].append(chosen)
    rejected.sort(key=lambda row:(row["meter"] or "",row["fault"],str(row)))
    return dict(current),rejected

def difference(first,last):
    if first.meter != last.meter or first.sector != last.sector:
        return None,"sector_changed"
    if last.replaced or first.limit_l != last.limit_l:
        return None,"meter_replaced"
    duration=last.minute-first.minute
    if duration<=0 or duration>90:
        return None,"interval_unreliable"
    change=last.count_l-first.count_l
    rolled=change<0
    if rolled:
        if first.count_l<first.limit_l*.9 or last.count_l>last.limit_l*.15:
            return None,"non_rollover_reverse"
        change+=first.limit_l
    if change>min(first.max_rate,last.max_rate)*duration:
        return None,"flow_out_of_range"
    return Span(last.meter,last.sector,first.minute,last.minute,change,last.isolated and first.isolated,rolled),None

def assemble(raw,cutoff):
    meters,events=revise(raw,cutoff)
    spans=[]
    for meter,rows in sorted(meters.items()):
        for first,last in zip(rows,rows[1:]):
            span,error=difference(first,last)
            if span is None:
                events.append({"fault":error,"meter":meter,"left":first.minute,"right":last.minute})
            else:
                spans.append(span)
    return tuple(spans),events
