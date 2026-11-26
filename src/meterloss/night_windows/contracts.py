from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'key': '窗口编号',
    'start': '起始营运分',
    'stop': '结束营运分',
    'target': '目标观测窗口',
    'industrial': '生产夜班',
    'flush': '计划冲洗',
    'rain': '图示降雨',
    'sector': '定义分区',
    'pipe_kpa': '进水压力千帕',
    'ambient': '气温',
}


@dataclass(frozen=True, slots=True)
class NightWindow:
    key: str
    start: int
    stop: int
    target: bool
    industrial: bool
    flush: bool
    rain: float
    sector: str
    pipe_kpa: float
    ambient: float

    def __post_init__(self):
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("窗口编号缺失")
        if type(self.start) is not int or not 0 <= self.start <= 10080:
            raise ValueError("起始营运分越界")
        if type(self.stop) is not int or not 0 <= self.stop <= 10080:
            raise ValueError("结束营运分越界")
        if type(self.target) is not bool:
            raise ValueError("目标观测窗口须为布尔值")
        if type(self.industrial) is not bool:
            raise ValueError("生产夜班须为布尔值")
        if type(self.flush) is not bool:
            raise ValueError("计划冲洗须为布尔值")
        if isinstance(self.rain, bool) or not isinstance(self.rain, (float, int)):
            raise ValueError("图示降雨须为数值")
        if not isfinite(self.rain) or not 0 <= self.rain <= 150:
            raise ValueError("图示降雨越界")
        if not isinstance(self.sector, str) or not self.sector.strip():
            raise ValueError("定义分区缺失")
        if isinstance(self.pipe_kpa, bool) or not isinstance(self.pipe_kpa, (float, int)):
            raise ValueError("进水压力千帕须为数值")
        if not isfinite(self.pipe_kpa) or not 0 <= self.pipe_kpa <= 2000:
            raise ValueError("进水压力千帕越界")
        if isinstance(self.ambient, bool) or not isinstance(self.ambient, (float, int)):
            raise ValueError("气温须为数值")
        if not isfinite(self.ambient) or not -50 <= self.ambient <= 65:
            raise ValueError("气温越界")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            key = row["key"]
            key = key.strip() if isinstance(key, str) else key
            start = row["start"]
            stop = row["stop"]
            target = row["target"]
            industrial = row["industrial"]
            flush = row["flush"]
            rain = row["rain"]
            sector = row["sector"]
            sector = sector.strip() if isinstance(sector, str) else sector
            pipe_kpa = row["pipe_kpa"]
            ambient = row["ambient"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            key=key,
            start=start,
            stop=stop,
            target=target,
            industrial=industrial,
            flush=flush,
            rain=rain,
            sector=sector,
            pipe_kpa=pipe_kpa,
            ambient=ambient,
        )

    def as_record(self) -> dict:
        return asdict(self)


from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True,slots=True)
class NightFlow:
    meter: str
    sector: str
    night: str
    start: int
    target: bool
    total_l: Fraction
    sealed_l: Fraction
    minutes: int
    full: int
    sealed_min: int
    pressure: float
    excluded: str | None

    @property
    def rate(self):
        return float(self.total_l/self.minutes) if self.minutes else None

    @property
    def test_rate(self):
        return float(self.sealed_l/self.sealed_min) if self.sealed_min else None

    @property
    def coverage(self):
        return self.minutes/self.full
