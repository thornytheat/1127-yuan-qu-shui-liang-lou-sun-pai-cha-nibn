from dataclasses import asdict
from .register import assemble

def validate_readings(raw,asof):
    return assemble(raw,asof)

def meter_evidence(spans, issues):
    result=[dict(asdict(row),rate=round(row.rate,3)) for row in spans if row.rollover]
    result.extend(issues)
    total={}
    for row in spans:
        key=(row.sector,row.meter)
        total[key]=total.get(key,0)+row.liters
    result.extend({"sector":zone,"meter":meter,"liters":quantity} for (zone,meter),quantity in sorted(total.items()))
    return result
