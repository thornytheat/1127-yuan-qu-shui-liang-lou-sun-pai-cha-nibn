from dataclasses import asdict
from .contracts import LossPolicy
from .scoring import screen,tail_probability

def assess(baseline,samples,usage,controls):
    policy=LossPolicy.parse(controls)
    findings=screen(baseline,samples,usage,policy)
    return policy,findings

def evidence(findings, policy):
    out=[]
    for item in findings:
        row=asdict(item)
        row["version"]=policy.version
        row["followup"]=item.status in {"关阀仍过水","疑似持续漏损","人工复核"}
        out.append(row)
    return out
