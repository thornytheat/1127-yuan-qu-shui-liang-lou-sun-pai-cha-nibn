from collections import defaultdict
from dataclasses import dataclass
from .assignment import round_book

@dataclass(frozen=True,slots=True)
class Relief:
    name: str
    sick: tuple[str,...]
    unavailable: tuple[str,...]
    cap: int
    walkway: dict[str,int]

    def __post_init__(self):
        if not self.name or not 1<=self.cap<=100 or any(value<0 for value in self.walkway.values()):
            raise ValueError("值班应急演练缺少名称、配额或通行参数")

def crew_intervention(roster, exercise):
    unavailable=set(exercise.unavailable)
    excluded=set(exercise.sick)
    available=[]
    for team in roster:
        if team["name"] in excluded:
            continue
        covered=[area for area in team["zones"] if area not in unavailable]
        if covered:
            available.append(dict(team,zones=covered))
    return available

def compare_dispatch(previous, revised, flags):
    catalog={row.meter:row for row in previous}
    retrieval=[]
    for job in sorted(revised,key=lambda r:r.meter):
        old=catalog.pop(job.meter,None)
        old_values=(old.crew,old.from_minute,old.state) if old is not None else (None,None,"未记录")
        if old_values==(job.crew,job.from_minute,job.state):
            continue
        old_crew,old_at,old_state=old_values
        lag=job.from_minute-old_at if old_at is not None and job.from_minute is not None else None
        retrieval.append({"meter":job.meter,"diagnostic":flags.get(job.meter),"old_crew":old_crew,
                          "new_crew":job.crew,"lag":lag,"prior":old_state,"after":job.state})
    for missing,job in sorted(catalog.items()):
        retrieval.append({"meter":missing,"diagnostic":flags.get(missing),"prior":job.state,"after":"未复算"})
    return retrieval

def stress_assign(findings, dispatch, crew_roster, baseline_walk, changes):
    flags={item.meter:item.status for item in findings}
    results=[]
    high_priority={"关阀仍过水","疑似持续漏损"}
    for raw in changes:
        exercise=Relief(raw["name"],tuple(raw["sick"]),tuple(raw["unavailable"]),raw["cap"],raw["walkway"])
        shifted=crew_intervention(crew_roster,exercise)
        active=round_book(findings,shifted,exercise.cap,{**baseline_walk,**exercise.walkway})
        transition=compare_dispatch(dispatch,active,flags)
        gaps=defaultdict(int)
        active_tickets=0
        for row in active:
            if row.state=="已派单":
                active_tickets+=1
            elif flags[row.meter] in high_priority:
                gaps[row.sector]+=1
        results.append({"exercise":exercise.name,"active_crews":len(shifted),"visits":active_tickets,
                        "unserved_safety":dict(sorted(gaps.items())),"changes":transition})
    return results
