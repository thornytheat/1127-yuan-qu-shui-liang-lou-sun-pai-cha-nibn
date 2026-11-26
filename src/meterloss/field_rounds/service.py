from collections import defaultdict
from dataclasses import asdict
from .assignment import round_book

def route_work(findings, roster, capacity):
    return round_book(findings,roster["crews"],capacity,roster["walks"])

def details(work):
    return [asdict(job) for job in work]

def crew_summary(work):
    totals=defaultdict(int)
    for row in work:
        if row.crew:
            totals[row.crew]+=row.minutes
    return dict(sorted(totals.items()))
