from .integration import slice_nights

def build_baseline(spans,night_specs):
    records=slice_nights(spans,night_specs)
    training=tuple(row for row in records if row.excluded is None and not row.target)
    return training,tuple(row for row in records if row.target),tuple(row for row in records if row.excluded)

def summarize_rates(daily):
    return [{"meter":row.meter,"sector":row.sector,"night":row.night,"minutes":row.minutes,
             "coverage":round(row.coverage,3),"rate_lpm":round(row.rate,3) if row.rate is not None else None,
             "isolation_rate":round(row.test_rate,3) if row.test_rate is not None else None,
             "status":row.excluded or "可比较"} for row in daily]
