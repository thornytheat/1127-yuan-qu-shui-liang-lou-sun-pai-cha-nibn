from collections import defaultdict
from dataclasses import dataclass
from math import fsum, isfinite, sqrt

@dataclass(frozen=True, slots=True)
class PressureEffect:
    ticket: str
    meter: str
    zone: str
    assessed_l: float
    measured_l: float
    duration_min: int
    pressure_kpa: float
    diagnostic: str

def normalize_repair(row,reference_kpa):
    if not isfinite(reference_kpa) or reference_kpa<=0:
        raise ValueError("复测基准供压必须为正")
    if row.night_minutes<=0 or row.pressure<=0:
        raise ValueError("复测有效时长和供压缺失")
    measured=(row.before_rate-row.after_rate)*row.night_minutes
    adjust=measured*sqrt(reference_kpa/row.pressure)
    if not row.fault:
        state="未确认漏点"
    elif measured<=0:
        state="修后未见净流量回落"
    else:
        state="确认隔离后节水"
    return PressureEffect(row.ticket,row.meter,row.zone,adjust,measured,row.night_minutes,row.pressure,state)

def select_valid_repairs(receipts,active):
    latest={}
    ignored=[]
    for row in sorted(receipts.values(),key=lambda entry:(entry.closed,entry.ticket)):
        if row.meter not in active:
            ignored.append({"ticket":row.ticket,"meter":row.meter,"reason":"无当前巡检单"})
            continue
        if active[row.meter]!=row.zone:
            ignored.append({"ticket":row.ticket,"meter":row.meter,"reason":"复测分区与巡检分区不同"})
            continue
        if row.meter in latest:
            old=latest[row.meter]
            ignored.append({"ticket":old.ticket,"meter":row.meter,"reason":"有更新回执"})
        latest[row.meter]=row
    return latest,ignored

def aggregate_repairs(receipts,findings,reference_kpa):
    active={item.meter:item.sector for item in findings}
    matched,history=select_valid_repairs(receipts,active)
    outcomes=[normalize_repair(row,reference_kpa) for row in matched.values()]
    places=defaultdict(list)
    for row in outcomes:
        places[row.zone].append(row)
        history.append({"ticket":row.ticket,"meter":row.meter,"source_kpa":row.pressure_kpa,
                        "effect_l":round(row.assessed_l,3),"observed_l":round(row.measured_l,3),
                        "valid_minutes":row.duration_min,"result":row.diagnostic})
    for zone,records in sorted(places.items()):
        positive=[row for row in records if row.diagnostic=="确认隔离后节水"]
        savings=round(fsum(row.assessed_l for row in positive),3)
        plain=round(fsum(row.measured_l for row in positive),3)
        history.append({"sector":zone,"assessed_repairs":len(records),"qualified":len(positive),
                        "metered_saved_l":plain,"pressure_corrected_saved_l":savings,
                        "reference_pressure_kpa":reference_kpa})
    return history
