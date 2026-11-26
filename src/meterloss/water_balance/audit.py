from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
from json import dumps
from .contracts import RepairReceipt, Investigation

def receipt_index(rows,now):
    evidence={}
    for raw in rows:
        row=RepairReceipt.parse(raw)
        if row.closed>now:
            continue
        if row.ticket in evidence and evidence[row.ticket]!=row:
            raise ValueError("同一复检单回传内容不一致")
        evidence[row.ticket]=row
    return evidence

def assess_repairs(findings,checks):
    decisions={find.meter:find for find in findings}
    total=0
    false_calls=0
    misses=0
    confirmed=0
    alerted=0
    actual_positive=0
    seen={}
    for row in sorted(checks.values(),key=lambda item:(item.closed,item.ticket)):
        if row.meter in decisions:
            seen[row.meter]=row
    for record in seen.values():
        predicted=decisions[record.meter].status in {"关阀仍过水","疑似持续漏损"}
        alerted+=predicted
        actual_positive+=record.fault
        false_calls+=predicted and not record.fault
        misses+=record.fault and not predicted
        if record.fault:
            confirmed+=1
            total+=max(0,record.before_rate-record.after_rate)*record.night_minutes
    recall=(actual_positive-misses)/actual_positive if actual_positive else None
    precision=(alerted-false_calls)/alerted if alerted else None
    return Investigation(confirmed,misses,false_calls,len(seen),round(total,3),alerted,precision,recall)

def audit_dispatch(work, controls):
    assigned=defaultdict(list)
    conflicts=[]
    meter_seen=set()
    for record in work:
        if record.meter in meter_seen:
            conflicts.append({"code":"duplicate_meter","meter":record.meter})
        meter_seen.add(record.meter)
        if record.state!="已派单":
            continue
        if not record.crew or record.from_minute is None or record.to_minute is None or record.to_minute-record.from_minute!=record.minutes:
            conflicts.append({"code":"broken_assignment","meter":record.meter})
            continue
        assigned[record.crew].append(record)
    for name,rows in assigned.items():
        ordered=sorted(rows,key=lambda row:row.from_minute)
        latest=None
        for row in ordered:
            if latest and latest.to_minute>row.from_minute:
                conflicts.append({"code":"crew_overlap","meter":row.meter,"crew":name})
            if latest is None or row.to_minute>latest.to_minute:
                latest=row
    digest=sha256(dumps([sorted((asdict(r) for r in work),key=lambda r:r["meter"]),controls],
                        sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {"passed":not conflicts,"digest":digest,"crews":len(assigned)}, conflicts
