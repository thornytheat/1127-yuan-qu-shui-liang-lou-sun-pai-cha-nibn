from collections import defaultdict
from dataclasses import dataclass, asdict
from math import fsum,isfinite,sqrt
from statistics import median

@dataclass(frozen=True,slots=True)
class Confidence:
    meter: str
    chosen_nights: int
    naive_lpm: float | None
    normalized_lpm: float | None
    low_lpm: float | None
    high_lpm: float | None
    night_mad: float | None
    exception: str

def jackknife_center(observed):
    if not observed:
        return None,None,None
    representative=median(observed)
    if len(observed)==1:
        return representative,None,None
    shifted=[median(observed[:i]+observed[i+1:]) for i in range(len(observed))]
    return representative,min(shifted),max(shifted)

def estimate_baseline(by_meter, constant, min_count):
    if not isfinite(constant) or constant<50 or min_count<1:
        raise ValueError("最低基线证据设置有误")
    grouped=defaultdict(list)
    for sample in by_meter:
        grouped[sample.meter].append(sample)
    report=[]
    for key,log in sorted(grouped.items()):
        allowed=[row for row in log if not row.excluded and row.rate is not None]
        plain=[row.rate for row in allowed]
        known=[row.rate*sqrt(constant/max(50,row.pressure)) for row in allowed]
        center,low,high=jackknife_center(known)
        mad=median(abs(x-center) for x in known) if center is not None else None
        status="基线稳定"
        if len(allowed)<min_count:
            status="参考晚数不足"
        elif center and high is not None and low is not None and high-low>center*.3:
            status="单夜选择影响偏大"
        report.append(Confidence(key,len(allowed),median(plain) if plain else None,center,low,high,mad,status))
    return tuple(report)

def counter_pressure(records, anchoring, threshold=.1):
    if not isfinite(anchoring) or anchoring<=0 or not 0<threshold<1:
        raise ValueError("压力量级和敏感阈值无效")
    output=[]
    for item in records:
        available=item.naive_lpm is not None and item.normalized_lpm is not None
        adjustment=(item.normalized_lpm-item.naive_lpm) if available else None
        relative=adjustment/item.naive_lpm if available and item.naive_lpm else None
        ledger=asdict(item)
        ledger.update(reference_pressure=anchoring,pressure_delta=relative,
                      instability=relative is not None and abs(relative)>=threshold)
        for field in ("normalized_lpm","low_lpm","high_lpm","night_mad","pressure_delta"):
            if ledger[field] is not None:
                ledger[field]=round(ledger[field],6)
        output.append(ledger)
    return output
