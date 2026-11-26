from collections import defaultdict
from math import sqrt
from statistics import median
from .contracts import Track

def normalized_rate(entry, anchoring):
    return entry.rate * sqrt(anchoring/max(50,entry.pressure)) if entry.rate is not None else None

def tail_probability(reference, observed):
    if not reference:
        return None
    return (1+sum(x>=observed for x in reference))/(len(reference)+1)

def meters_by_name(records):
    pairs=defaultdict(list)
    for row in records:
        pairs[row.meter].append(row)
    return {key:sorted(rows,key=lambda row:row.start) for key,rows in sorted(pairs.items())}

def screen(history, recent, cohorts, policy):
    prior=meters_by_name(history)
    diagnostics=[]
    for meter, daily in meters_by_name(recent).items():
        if meter not in cohorts:
            diagnostics.append(Track(meter,daily[0].sector,"资料缺失",len(daily),0,0,None,0,"未登记","用水画像未建档",None))
            continue
        group=cohorts[meter]
        features=[normalized_rate(entry,policy.pressure_anchor) for entry in prior.get(meter,())]
        baseline=[value for value in features if value is not None]
        values=[(normalized_rate(entry,policy.pressure_anchor),entry) for entry in daily if not entry.excluded]
        good=[(value,row) for value,row in values if value is not None]
        floor=median(baseline) if baseline else group["typical_lpm"]
        maximum=max((value for value,_ in good),default=floor)
        excess=max(0, maximum-floor)
        persistence=0
        longest=0
        prior_start=None
        signal={r.start:v for v,r in good}
        for entry in daily:
            value=signal.get(entry.start)
            if value is None or value-floor<policy.minimum_rate:
                persistence=0
            else:
                persistence=1 if prior_start is None or entry.start-prior_start>1500 else persistence+1
            longest=max(longest,persistence)
            prior_start=entry.start
        pvalue=tail_probability(baseline,maximum) if good else None
        isolated=max((row.test_rate for _,row in good if row.test_rate is not None),default=None)
        if not good:
            state,reason="需补采","目标窗口全部不可用于判断"
        elif isolated is not None and isolated>=policy.isolation_alarm:
            state,reason="关阀仍过水","隔离试验余流超过阈值"
        elif len(baseline)<policy.minimum_samples or group["distance"]>policy.cohort_reject:
            state,reason="人工复核","基线过少或偏离画像簇"
        elif longest>=policy.minimum_persistence and pvalue <= policy.calibration_cap:
            state,reason="疑似持续漏损","连续夜窗净余流及经验尾概率同时触发"
        else:
            state,reason="观察","未同时满足持续夜数及余流标准"
        diagnostics.append(Track(meter,daily[0].sector,state,len(daily),len(good),round(excess,4),
                                 round(pvalue,5) if pvalue is not None else None,longest,group["cohort"],reason,
                                 round(isolated,4) if isolated is not None else None))
    return tuple(diagnostics)
