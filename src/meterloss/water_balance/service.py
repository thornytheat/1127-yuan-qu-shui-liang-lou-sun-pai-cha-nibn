from dataclasses import asdict
from .audit import receipt_index, assess_repairs, audit_dispatch

def finalize(findings,work,receipt_entries,recheck,settings):
    indexed=receipt_index(receipt_entries,recheck)
    score=assess_repairs(findings,indexed)
    checklist,notes=audit_dispatch(work,settings)
    evidence=[{**checklist,**asdict(score)},*notes]
    return checklist,score,evidence
