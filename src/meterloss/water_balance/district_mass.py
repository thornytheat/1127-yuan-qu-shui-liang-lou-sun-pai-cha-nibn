from dataclasses import dataclass
from collections import defaultdict
from fractions import Fraction
from math import isfinite

@dataclass(frozen=True,slots=True)
class SupplyAccount:
    sector: str
    night: str
    before_l: int
    after_l: int
    storage_at_start: int
    storage_at_end: int
    exempted_l: int
    sample_coverage: float
    edition: int
    known_at: int

    def __post_init__(self):
        readings=(self.before_l,self.after_l,self.storage_at_start,self.storage_at_end,self.exempted_l)
        if any(type(x) is not int or x<0 for x in readings) or self.after_l<self.before_l:
            raise ValueError("供水总表及池容需为非负递增整数升")
        if not self.sector or not self.night or not 0<=self.sample_coverage<=1 or self.edition<1:
            raise ValueError("供水账本缺少分区、夜窗、覆盖率或版本")

    @property
    def net_available(self):
        incoming=self.after_l-self.before_l
        storage=self.storage_at_end-self.storage_at_start
        return incoming-storage-self.exempted_l

@dataclass(frozen=True,slots=True)
class Balance:
    sector: str
    night: str
    accounted_l: Fraction
    supply_l: int
    unaccounted_l: Fraction
    branches: int
    usable: int
    status: str
    unaccounted_share: float | None

    def describe(self):
        return {"sector":self.sector,"night":self.night,"branch_l":round(float(self.accounted_l),3),
                "supply_l":self.supply_l,"unexplained_l":round(float(self.unaccounted_l),3),
                "branch_meters":self.branches,"usable_meters":self.usable,
                "balance_state":self.status,"unexplained_share":self.unaccounted_share}

def agreed_accounts(records, cutoff):
    bins=defaultdict(list)
    for source in records:
        account=SupplyAccount(**source)
        if account.known_at<=cutoff:
            bins[(account.sector,account.night)].append(account)
    selected={}
    for key,rows in sorted(bins.items()):
        top=max(r.edition for r in rows)
        versions={r for r in rows if r.edition==top}
        if len(versions)>1:
            raise ValueError(f"供水总表同效版本冲突 {key}")
        selected[key]=next(iter(versions))
    return selected

def reconcile_districts(entries, meters, reported_at, minimum_share=.8):
    if not 0<minimum_share<=1:
        raise ValueError("供水分区需要有效覆盖比例")
    index=agreed_accounts(meters,reported_at)
    children=defaultdict(list)
    identities=set()
    for row in entries:
        group=(row.sector,row.night)
        identity=(*group,row.meter)
        if identity in identities:
            raise ValueError("同一夜窗中出现重复支路")
        identities.add(identity)
        children[group].append(row)
    report=[]
    for (sector,night), account in index.items():
        visible=children[sector,night]
        ready=[row for row in visible if not row.excluded and row.coverage>=minimum_share]
        downstream=sum((row.total_l for row in ready),Fraction(0))
        incoming=account.net_available
        residual=incoming-downstream
        if incoming<0:
            outcome="水池交换量异常"
        elif account.sample_coverage<minimum_share or not visible or len(ready)/len(visible)<minimum_share:
            outcome="总分表同观测不足"
        elif residual<0:
            outcome="分表总量超过供水总表"
        elif incoming and float(residual/incoming)>.15:
            outcome="总表净损耗偏高"
        else:
            outcome="供水差额在限值内"
        share=(round(float(residual/incoming),6) if incoming>0 and outcome not in
               {"总分表同观测不足","水池交换量异常"} else None)
        report.append(Balance(sector,night,downstream,incoming,residual,len(visible),len(ready),outcome,share))
    return tuple(report)
