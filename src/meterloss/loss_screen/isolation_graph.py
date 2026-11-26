from dataclasses import dataclass
from collections import defaultdict
from math import exp, fsum, isfinite, log

@dataclass(frozen=True,slots=True)
class PipeLink:
    sector: str
    parent: str
    child: str
    material: str
    age_years: float
    prior: float

    def __post_init__(self):
        if self.parent==self.child or not self.sector or not self.child or not self.parent:
            raise ValueError("管线结构包含自连接或身份缺失")
        if not isfinite(self.prior) or not 0<self.prior<=1 or not 0<=self.age_years<=100:
            raise ValueError("管段先验或寿命非法")

@dataclass(frozen=True,slots=True)
class ValvePulse:
    name: str
    sector: str
    interrupted: str
    before_lpm: float
    after_lpm: float
    reliable: bool
    observed: int

    def __post_init__(self):
        if not all(isfinite(x) and 0<=x<=2000 for x in (self.before_lpm,self.after_lpm)):
            raise ValueError("隔离脉冲读数超出仪表范围")
        if type(self.reliable) is not bool:
            raise ValueError("隔离测点必须注明复核状态")

    @property
    def delta(self):
        return self.before_lpm-self.after_lpm

def path_to_root(segments):
    node_to_parent={}
    for link in segments:
        if link.child in node_to_parent:
            raise ValueError("支路节点有多条入边")
        node_to_parent[link.child]=link.parent
    for location in node_to_parent:
        visited=set()
        current=location
        while current in node_to_parent:
            if current in visited:
                raise ValueError("供水图中存在环")
            visited.add(current)
            current=node_to_parent[current]
    return node_to_parent

def downstream(parent_of,start):
    children=defaultdict(list)
    for node,parent in parent_of.items():
        children[parent].append(node)
    visited=set()
    pending=[start]
    while pending:
        node=pending.pop()
        if node in visited:
            continue
        visited.add(node)
        pending.extend(children.get(node,()))
    return visited

def localize(pipes,trials,cutoff,min_support=2):
    if min_support<1:
        raise ValueError("最少独立隔离测试次数须为正")
    lines=defaultdict(list)
    for raw in pipes:
        item=PipeLink(**raw)
        lines[item.sector].append(item)
    attempts=defaultdict(list)
    for raw in trials:
        entry=ValvePulse(**raw)
        if entry.reliable and entry.observed<=cutoff:
            attempts[entry.sector].append(entry)
    findings=[]
    for zone,segments in sorted(lines.items()):
        parents=path_to_root(segments)
        if len({segment.parent for segment in segments if segment.parent not in parents})!=1:
            raise ValueError("单个分区应有唯一的进水根")
        available=[]
        seen=set()
        for experiment in attempts[zone]:
            if experiment.name in seen:
                raise ValueError("隔离试验编号不能多次进入计算")
            seen.add(experiment.name)
            if experiment.interrupted in parents:
                available.append((experiment,downstream(parents,experiment.interrupted)))
        distribution=[]
        for segment in segments:
            topology_log=log(segment.prior)
            for experiment,below in available:
                dropped=round(experiment.delta, 6)>=1.2
                agreement=dropped==(segment.child in below)
                topology_log+=log(.86 if agreement else .14)
            distribution.append((topology_log,segment.child,segment.material))
        peak=max(distribution)[0]
        evidence=[(exp(x-peak),node,material) for x,node,material in distribution]
        weights=fsum(weight for weight,_,_ in evidence)
        ordered=sorted(evidence,key=lambda entry:(-entry[0],entry[1]))
        strong=len(available)>=min_support and ordered[0][0]/weights>=.65
        findings.append({"sector":zone,"isolation_support":len(available),"located":strong,
                         "priority_branch":ordered[0][1] if strong else None,
                         "rank":[{"node":node,"material":material,"share":round(weight/weights,6)}
                                 for weight,node,material in ordered]})
    return findings
