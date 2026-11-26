from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'name': '巡检组',
    'zones': '执勤分区',
    'hours': '值班分钟',
    'acoustic': '持证听漏',
    'valve': '可操作阀门',
    'max_cases': '最大工单',
    'base': '值守站',
    'starts': '开班分钟',
}


@dataclass(frozen=True, slots=True)
class FieldCrew:
    name: str
    zones: tuple
    hours: int
    acoustic: bool
    valve: bool
    max_cases: int
    base: str
    starts: int

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("巡检组缺失")
        if not isinstance(self.zones, tuple):
            raise ValueError("执勤分区须为序列")
        if type(self.hours) is not int or not 1 <= self.hours <= 900:
            raise ValueError("值班分钟越界")
        if type(self.acoustic) is not bool:
            raise ValueError("持证听漏须为布尔值")
        if type(self.valve) is not bool:
            raise ValueError("可操作阀门须为布尔值")
        if type(self.max_cases) is not int or not 1 <= self.max_cases <= 30:
            raise ValueError("最大工单越界")
        if not isinstance(self.base, str) or not self.base.strip():
            raise ValueError("值守站缺失")
        if type(self.starts) is not int or not 0 <= self.starts <= 10080:
            raise ValueError("开班分钟越界")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            name = row["name"]
            name = name.strip() if isinstance(name, str) else name
            zones = row["zones"]
            zones = tuple(zones)
            hours = row["hours"]
            acoustic = row["acoustic"]
            valve = row["valve"]
            max_cases = row["max_cases"]
            base = row["base"]
            base = base.strip() if isinstance(base, str) else base
            starts = row["starts"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            name=name,
            zones=zones,
            hours=hours,
            acoustic=acoustic,
            valve=valve,
            max_cases=max_cases,
            base=base,
            starts=starts,
        )

    def as_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Work:
    meter: str
    sector: str
    task: str
    crew: str | None
    minutes: int
    from_minute: int | None
    to_minute: int | None
    state: str
    notes: str
