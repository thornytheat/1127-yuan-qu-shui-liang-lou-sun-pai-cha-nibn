from dataclasses import asdict, dataclass


COLUMN_LABELS = {
    "meter": "表号",
    "sector": "分区",
    "grade": "本期漏损分级",
    "ticket": "回执工单",
    "handoff_state": "交班裁决",
    "next_round": "下一班名单",
    "receipt_rate": "修后升每分钟",
    "recheck_rate": "复测夜窗升每分钟",
    "recheck_night": "复测夜窗",
    "recheck_pressure": "夜窗供压",
    "receipt_pressure": "回执供压",
    "pressure_delta": "供压相对偏差",
    "reason": "裁决依据",
}


@dataclass(frozen=True, slots=True)
class HandoffDecision:
    """单个水表的交班裁决；本期分级只原样保留，不由回执改写。"""

    meter: str
    sector: str
    grade: str
    ticket: str | None
    handoff_state: str
    next_round: bool
    receipt_rate: float | None
    recheck_rate: float | None
    recheck_night: str | None
    recheck_pressure: float | None
    receipt_pressure: float | None
    pressure_delta: float | None
    reason: str

    def as_record(self) -> dict:
        row = asdict(self)
        for key in ("receipt_rate", "recheck_rate", "recheck_pressure",
                    "receipt_pressure", "pressure_delta"):
            if row[key] is not None:
                row[key] = round(row[key], 4)
        return row
