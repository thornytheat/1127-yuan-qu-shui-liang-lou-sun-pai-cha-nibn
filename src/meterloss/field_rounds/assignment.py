from .contracts import FieldCrew, Work

RANK={"关阀仍过水":0,"疑似持续漏损":1,"人工复核":2,"需补采":3,"资料缺失":4,"观察":5}

def estimate_task(track):
    if track.status=="关阀仍过水":
        return "隔离听漏",45,True,True
    if track.status=="疑似持续漏损":
        return "夜间听漏",35,True,False
    if track.status=="人工复核":
        return "查阅支路开户",25,False,False
    if track.status=="需补采":
        return "补抄数据",20,False,False
    return "归档",0,False,False

def prioritize(track):
    return RANK[track.status],-track.excess,-track.persistence,track.meter

def round_book(records, rosters, capacity, walks):
    if not 1<=capacity<=100:
        raise ValueError("巡检容量须在 1 至 100")
    crews=[FieldCrew.parse(item) for item in rosters]
    if len({row.name for row in crews})!=len(crews):
        raise ValueError("巡检组重复登记")
    updates={row.name:[row.starts,0,row.base] for row in crews}
    output=[]
    used=0
    for row in sorted(records,key=prioritize):
        kind,effort,sound,valve=estimate_task(row)
        if effort==0:
            output.append(Work(row.meter,row.sector,kind,None,0,None,None,"归档",row.reason))
            continue
        if used>=capacity:
            output.append(Work(row.meter,row.sector,kind,None,effort,None,None,"下一轮", "本轮工单配额已满"))
            continue
        candidates=[]
        for crew in crews:
            if row.sector not in crew.zones or sound and not crew.acoustic or valve and not crew.valve:
                continue
            clock,count,prior=updates[crew.name]
            travel=walks.get(f"{prior}>{row.sector}",0 if prior==row.sector else 20)
            if travel<0:
                raise ValueError("步行矩阵不可为负")
            start=clock+travel
            end=start+effort
            if count>=crew.max_cases or end>crew.starts+crew.hours:
                continue
            candidates.append((end,travel,crew.name,start))
        if not candidates:
            output.append(Work(row.meter,row.sector,kind,None,effort,None,None,"值班协调","无区内持证并可按时到达的小组"))
            continue
        end,travel,name,begin=min(candidates)
        updates[name]=[end,updates[name][1]+1,row.sector]
        output.append(Work(row.meter,row.sector,kind,name,effort,begin,end,"已派单",f"前往现场 {travel} 分钟"))
        used+=1
    return tuple(output)
