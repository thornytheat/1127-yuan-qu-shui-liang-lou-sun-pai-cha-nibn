from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'ticket': '复测工单',
    'meter': '表号',
    'zone': '修复分区',
    'closed': '复检分钟',
    'fault': '是否确认漏点',
    'before_rate': '修前升每分钟',
    'after_rate': '修后升每分钟',
    'night_minutes': '复测覆盖分钟',
    'pressure': '复测供水压',
    'reviewer': '复检签字',
}


@dataclass(frozen=True, slots=True)
class RepairReceipt:
    ticket: str
    meter: str
    zone: str
    closed: int
    fault: bool
    before_rate: float
    after_rate: float
    night_minutes: int
    pressure: float
    reviewer: str

    def __post_init__(self):
        if not isinstance(self.ticket, str) or not self.ticket.strip():
            raise ValueError("复测工单缺失")
        if not isinstance(self.meter, str) or not self.meter.strip():
            raise ValueError("表号缺失")
        if not isinstance(self.zone, str) or not self.zone.strip():
            raise ValueError("修复分区缺失")
        if type(self.closed) is not int or not 0 <= self.closed <= 10080:
            raise ValueError("复检分钟越界")
        if type(self.fault) is not bool:
            raise ValueError("是否确认漏点须为布尔值")
        if isinstance(self.before_rate, bool) or not isinstance(self.before_rate, (float, int)):
            raise ValueError("修前升每分钟须为数值")
        if not isfinite(self.before_rate) or not 0 <= self.before_rate <= 2500:
            raise ValueError("修前升每分钟越界")
        if isinstance(self.after_rate, bool) or not isinstance(self.after_rate, (float, int)):
            raise ValueError("修后升每分钟须为数值")
        if not isfinite(self.after_rate) or not 0 <= self.after_rate <= 2500:
            raise ValueError("修后升每分钟越界")
        if type(self.night_minutes) is not int or not 1 <= self.night_minutes <= 1440:
            raise ValueError("复测覆盖分钟越界")
        if isinstance(self.pressure, bool) or not isinstance(self.pressure, (float, int)):
            raise ValueError("复测供水压须为数值")
        if not isfinite(self.pressure) or not 10 <= self.pressure <= 2000:
            raise ValueError("复测供水压越界")
        if not isinstance(self.reviewer, str) or not self.reviewer.strip():
            raise ValueError("复检签字缺失")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            ticket = row["ticket"]
            ticket = ticket.strip() if isinstance(ticket, str) else ticket
            meter = row["meter"]
            meter = meter.strip() if isinstance(meter, str) else meter
            zone = row["zone"]
            zone = zone.strip() if isinstance(zone, str) else zone
            closed = row["closed"]
            fault = row["fault"]
            before_rate = row["before_rate"]
            after_rate = row["after_rate"]
            night_minutes = row["night_minutes"]
            pressure = row["pressure"]
            reviewer = row["reviewer"]
            reviewer = reviewer.strip() if isinstance(reviewer, str) else reviewer
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            ticket=ticket,
            meter=meter,
            zone=zone,
            closed=closed,
            fault=fault,
            before_rate=before_rate,
            after_rate=after_rate,
            night_minutes=night_minutes,
            pressure=pressure,
            reviewer=reviewer,
        )

    def as_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Investigation:
    confirmed: int
    missed: int
    false_calls: int
    total_checks: int
    recovered_liters: float
    alerts_sampled: int
    precision: float | None
    recall: float | None
