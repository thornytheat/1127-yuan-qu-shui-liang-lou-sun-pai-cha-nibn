from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'key': '校准对象编号',
    'sector': '表所属供水区',
    'overnight_lpm': '最低夜流升每分钟',
    'daylight_lpm': '营业涨幅升每分钟',
    'weekday_load': '工作日增量占比',
    'pressure': '代表供压千帕',
    'commercial': '营业占比',
    'trusted': '进入基线练习',
    'known_at': '资料到达分钟',
}


@dataclass(frozen=True, slots=True)
class ProfilePoint:
    key: str
    sector: str
    overnight_lpm: float
    daylight_lpm: float
    weekday_load: float
    pressure: float
    commercial: float
    trusted: bool
    known_at: int

    def __post_init__(self):
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("校准对象编号缺失")
        if not isinstance(self.sector, str) or not self.sector.strip():
            raise ValueError("表所属供水区缺失")
        if isinstance(self.overnight_lpm, bool) or not isinstance(self.overnight_lpm, (float, int)):
            raise ValueError("最低夜流升每分钟须为数值")
        if not isfinite(self.overnight_lpm) or not 0 <= self.overnight_lpm <= 3000:
            raise ValueError("最低夜流升每分钟越界")
        if isinstance(self.daylight_lpm, bool) or not isinstance(self.daylight_lpm, (float, int)):
            raise ValueError("营业涨幅升每分钟须为数值")
        if not isfinite(self.daylight_lpm) or not 0 <= self.daylight_lpm <= 3000:
            raise ValueError("营业涨幅升每分钟越界")
        if isinstance(self.weekday_load, bool) or not isinstance(self.weekday_load, (float, int)):
            raise ValueError("工作日增量占比须为数值")
        if not isfinite(self.weekday_load) or not 0 <= self.weekday_load <= 1:
            raise ValueError("工作日增量占比越界")
        if isinstance(self.pressure, bool) or not isinstance(self.pressure, (float, int)):
            raise ValueError("代表供压千帕须为数值")
        if not isfinite(self.pressure) or not 0 <= self.pressure <= 2000:
            raise ValueError("代表供压千帕越界")
        if isinstance(self.commercial, bool) or not isinstance(self.commercial, (float, int)):
            raise ValueError("营业占比须为数值")
        if not isfinite(self.commercial) or not 0 <= self.commercial <= 1:
            raise ValueError("营业占比越界")
        if type(self.trusted) is not bool:
            raise ValueError("进入基线练习须为布尔值")
        if type(self.known_at) is not int or not 0 <= self.known_at <= 10080:
            raise ValueError("资料到达分钟越界")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            key = row["key"]
            key = key.strip() if isinstance(key, str) else key
            sector = row["sector"]
            sector = sector.strip() if isinstance(sector, str) else sector
            overnight_lpm = row["overnight_lpm"]
            daylight_lpm = row["daylight_lpm"]
            weekday_load = row["weekday_load"]
            pressure = row["pressure"]
            commercial = row["commercial"]
            trusted = row["trusted"]
            known_at = row["known_at"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            key=key,
            sector=sector,
            overnight_lpm=overnight_lpm,
            daylight_lpm=daylight_lpm,
            weekday_load=weekday_load,
            pressure=pressure,
            commercial=commercial,
            trusted=trusted,
            known_at=known_at,
        )

    def as_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True,slots=True)
class Cohorts:
    medoids: tuple[ProfilePoint,...]
    dispersions: tuple[float,...]
    size: int
    within_l1: float
