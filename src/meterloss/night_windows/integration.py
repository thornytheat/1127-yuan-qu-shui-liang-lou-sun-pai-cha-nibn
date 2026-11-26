from collections import defaultdict
from fractions import Fraction
from .contracts import NightFlow,NightWindow

def instant_overlap(left,right,from_min,to_min):
    return max(0,min(right,to_min)-max(left,from_min))

def assert_windows(windows):
    by_sector=defaultdict(list)
    for row in windows:
        if row.stop<=row.start:
            raise ValueError("夜窗结束时间须在起点之后")
        by_sector[row.sector].append(row)
    for place,slots in by_sector.items():
        ordered=sorted(slots,key=lambda row:row.start)
        if any(a.stop>b.start for a,b in zip(ordered,ordered[1:])):
            raise ValueError(f"{place}夜窗重叠")
    return by_sector

def measure(meter, spans, night, minimum=.8):
    total=sealed=Fraction(0)
    covered=isolated=0
    for row in spans:
        overlap=instant_overlap(row.left,row.right,night.start,night.stop)
        quantity=Fraction(row.liters*overlap,row.length)
        covered+=overlap
        total+=quantity
        if row.isolated:
            sealed+=quantity
            isolated+=overlap
    full=night.stop-night.start
    reason=None
    if covered>full:
        raise ValueError("采集脉冲重叠，覆盖率非法")
    if night.flush:
        reason="计划冲洗"
    elif night.industrial:
        reason="夜班生产"
    elif covered/full<minimum:
        reason="覆盖不足"
    return NightFlow(meter,night.sector,night.key,night.start,night.target,total,sealed,covered,
                     full,isolated,night.pipe_kpa,reason)

def slice_nights(spans, schedule, minimum=.8):
    if not 0 < minimum <= 1:
        raise ValueError("覆盖阈值须为零到一")
    indexed=assert_windows(NightWindow.parse(row) for row in schedule)
    by_meter=defaultdict(list)
    for row in spans:
        by_meter[(row.sector,row.meter)].append(row)
    return tuple(measure(meter,values,window,minimum) for (sector,meter),values in sorted(by_meter.items())
                 for window in sorted(indexed.get(sector,()),key=lambda entry:entry.start))
