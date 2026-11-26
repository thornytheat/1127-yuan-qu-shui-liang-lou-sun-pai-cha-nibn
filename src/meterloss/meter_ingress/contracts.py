from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'meter': '表号',
    'sector': '分区',
    'minute': '营运分钟',
    'received': '接档分钟',
    'version': '入账版次',
    'count_l': '累计升',
    'limit_l': '计数器翻转值',
    'max_rate': '最大升每分钟',
    'replaced': '更换标记',
    'isolated': '阀门关闭',
    'source': '抄表来源',
}


@dataclass(frozen=True, slots=True)
class Reading:
    meter: str
    sector: str
    minute: int
    received: int
    version: int
    count_l: int
    limit_l: int
    max_rate: float
    replaced: bool
    isolated: bool
    source: str

    def __post_init__(self):
        if not isinstance(self.meter, str) or not self.meter.strip():
            raise ValueError("表号缺失")
        if not isinstance(self.sector, str) or not self.sector.strip():
            raise ValueError("分区缺失")
        if type(self.minute) is not int or not 0 <= self.minute <= 10080:
            raise ValueError("营运分钟越界")
        if type(self.received) is not int or not 0 <= self.received <= 11000:
            raise ValueError("接档分钟越界")
        if type(self.version) is not int or not 1 <= self.version <= 200:
            raise ValueError("入账版次越界")
        if type(self.count_l) is not int or not 0 <= self.count_l <= 9999999:
            raise ValueError("累计升越界")
        if type(self.limit_l) is not int or not 100 <= self.limit_l <= 10000000:
            raise ValueError("计数器翻转值越界")
        if isinstance(self.max_rate, bool) or not isinstance(self.max_rate, (float, int)):
            raise ValueError("最大升每分钟须为数值")
        if not isfinite(self.max_rate) or not 1 <= self.max_rate <= 3000:
            raise ValueError("最大升每分钟越界")
        if type(self.replaced) is not bool:
            raise ValueError("更换标记须为布尔值")
        if type(self.isolated) is not bool:
            raise ValueError("阀门关闭须为布尔值")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("抄表来源缺失")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            meter = row["meter"]
            meter = meter.strip() if isinstance(meter, str) else meter
            sector = row["sector"]
            sector = sector.strip() if isinstance(sector, str) else sector
            minute = row["minute"]
            received = row["received"]
            version = row["version"]
            count_l = row["count_l"]
            limit_l = row["limit_l"]
            max_rate = row["max_rate"]
            replaced = row["replaced"]
            isolated = row["isolated"]
            source = row["source"]
            source = source.strip() if isinstance(source, str) else source
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            meter=meter,
            sector=sector,
            minute=minute,
            received=received,
            version=version,
            count_l=count_l,
            limit_l=limit_l,
            max_rate=max_rate,
            replaced=replaced,
            isolated=isolated,
            source=source,
        )

    def as_record(self) -> dict:
        return asdict(self)


from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class Span:
    meter: str
    sector: str
    left: int
    right: int
    liters: int
    isolated: bool
    rollover: bool

    @property
    def length(self):
        return self.right-self.left

    @property
    def rate(self):
        return self.liters / self.length
