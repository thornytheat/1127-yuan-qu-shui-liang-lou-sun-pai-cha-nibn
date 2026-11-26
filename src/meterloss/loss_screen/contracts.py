from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'version': '工单策略版',
    'minimum_rate': '最小异常净雨量',
    'minimum_persistence': '持续夜数',
    'pressure_anchor': '基准供水压',
    'isolation_alarm': '关阀余流阈',
    'calibration_cap': '尾部校准排名上限',
    'cohort_reject': '簇外距离阈值',
    'minimum_samples': '基线最少夜数',
}


@dataclass(frozen=True, slots=True)
class LossPolicy:
    version: str
    minimum_rate: float
    minimum_persistence: int
    pressure_anchor: float
    isolation_alarm: float
    calibration_cap: float
    cohort_reject: float
    minimum_samples: int

    def __post_init__(self):
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("工单策略版缺失")
        if isinstance(self.minimum_rate, bool) or not isinstance(self.minimum_rate, (float, int)):
            raise ValueError("最小异常净雨量须为数值")
        if not isfinite(self.minimum_rate) or not 0 <= self.minimum_rate <= 1000:
            raise ValueError("最小异常净雨量越界")
        if type(self.minimum_persistence) is not int or not 1 <= self.minimum_persistence <= 30:
            raise ValueError("持续夜数越界")
        if isinstance(self.pressure_anchor, bool) or not isinstance(self.pressure_anchor, (float, int)):
            raise ValueError("基准供水压须为数值")
        if not isfinite(self.pressure_anchor) or not 10 <= self.pressure_anchor <= 2000:
            raise ValueError("基准供水压越界")
        if isinstance(self.isolation_alarm, bool) or not isinstance(self.isolation_alarm, (float, int)):
            raise ValueError("关阀余流阈须为数值")
        if not isfinite(self.isolation_alarm) or not 0 <= self.isolation_alarm <= 1000:
            raise ValueError("关阀余流阈越界")
        if isinstance(self.calibration_cap, bool) or not isinstance(self.calibration_cap, (float, int)):
            raise ValueError("尾部校准排名上限须为数值")
        if not isfinite(self.calibration_cap) or not 0.01 <= self.calibration_cap <= 1:
            raise ValueError("尾部校准排名上限越界")
        if isinstance(self.cohort_reject, bool) or not isinstance(self.cohort_reject, (float, int)):
            raise ValueError("簇外距离阈值须为数值")
        if not isfinite(self.cohort_reject) or not 0.1 <= self.cohort_reject <= 1000:
            raise ValueError("簇外距离阈值越界")
        if type(self.minimum_samples) is not int or not 2 <= self.minimum_samples <= 100:
            raise ValueError("基线最少夜数越界")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            version = row["version"]
            version = version.strip() if isinstance(version, str) else version
            minimum_rate = row["minimum_rate"]
            minimum_persistence = row["minimum_persistence"]
            pressure_anchor = row["pressure_anchor"]
            isolation_alarm = row["isolation_alarm"]
            calibration_cap = row["calibration_cap"]
            cohort_reject = row["cohort_reject"]
            minimum_samples = row["minimum_samples"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            version=version,
            minimum_rate=minimum_rate,
            minimum_persistence=minimum_persistence,
            pressure_anchor=pressure_anchor,
            isolation_alarm=isolation_alarm,
            calibration_cap=calibration_cap,
            cohort_reject=cohort_reject,
            minimum_samples=minimum_samples,
        )

    def as_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True,slots=True)
class Track:
    meter: str
    sector: str
    status: str
    night_count: int
    stable_count: int
    excess: float
    probability: float | None
    persistence: int
    cohort: str
    reason: str
    isolated_rate: float | None
