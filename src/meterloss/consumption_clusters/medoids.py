from functools import lru_cache
from math import fsum
from statistics import median
from .contracts import Cohorts,ProfilePoint

def features(x):
    return x.overnight_lpm,x.daylight_lpm,x.weekday_load,x.pressure,x.commercial

def l1(left,right,scales):
    return fsum(abs(a-b)/s for a,b,s in zip(features(left),features(right),scales,strict=True))

def fit(records, at, groups=3):
    samples=sorted((point for point in map(ProfilePoint.parse,records) if point.trusted and point.known_at<at),
                   key=lambda item:item.key)
    if not 1<=groups<=len(samples) or len({x.key for x in samples})!=len(samples):
        raise ValueError("聚类样本数或身份无效")
    features_by_col=zip(*(features(row) for row in samples),strict=True)
    dispersions=[]
    for col,floor in zip(features_by_col,(.3,1.2,.1,14,.1),strict=True):
        pivot=median(col)
        dispersions.append(max(floor,median(abs(v-pivot) for v in col)*1.4826))
    scales=tuple(dispersions)
    all_ids=tuple(range(len(samples)))
    distances=[[l1(left,right,scales) for right in samples] for left in samples]
    first=min(all_ids,key=lambda i:(fsum(distances[i]),samples[i].key))
    centers=[first]
    while len(centers)<groups:
        others=(i for i in all_ids if i not in centers)
        centers.append(min(others,key=lambda i:(-min(distances[i][j] for j in centers),samples[i].key)))
    def cost(picks):
        return fsum(min(distances[i][j] for j in picks) for i in all_ids)
    for _ in range(12):
        best=cost(centers)
        change=None
        for old in sorted(centers):
            for incoming in all_ids:
                if incoming in centers:
                    continue
                prospect=sorted(incoming if j==old else j for j in centers)
                candidate=cost(prospect)
                if candidate+1e-9<best:
                    best=candidate
                    change=prospect
        if change is None:
            break
        centers=change
    return Cohorts(tuple(samples[i] for i in sorted(centers)),scales,len(samples),round(cost(centers),6))

def choose_group(group, observed):
    score,key=min((l1(point,observed,group.dispersions),point.key) for point in group.medoids)
    return key,round(score,6)

def best_overlap(reference,predicted):
    if len(reference)!=len(predicted):
        raise ValueError("参考簇标签与推断数不一致")
    if not reference:
        return None
    cluster_ids=sorted(set(predicted))
    truth_ids=sorted(set(reference))
    num=max(len(cluster_ids),len(truth_ids))
    if num>12:
        raise ValueError("聚类映射最多支持 12 组")
    alignment=[[0]*num for _ in range(num)]
    left={label:i for i,label in enumerate(truth_ids)}
    right={label:i for i,label in enumerate(cluster_ids)}
    for actual,guess in zip(reference,predicted,strict=True):
        alignment[left[actual]][right[guess]]+=1
    @lru_cache(None)
    def match(i,assigned):
        if i==num:
            return 0
        return max(alignment[i][j]+match(i+1,assigned|(1<<j)) for j in range(num) if not assigned&(1<<j))
    return match(0,0)/len(reference)
