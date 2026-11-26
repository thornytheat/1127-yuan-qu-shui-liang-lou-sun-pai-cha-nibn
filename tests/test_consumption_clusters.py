import pytest
from meterloss.consumption_clusters.medoids import fit, choose_group, best_overlap
from meterloss.consumption_clusters.contracts import ProfilePoint

def row(i,**updates):
    x=i//4%3
    base=dict(key=f"M{i:02d}",sector="北坡",overnight_lpm=1+x*3+i%4/20,daylight_lpm=5+x*12,
              weekday_load=.2+x*.2,pressure=360.,commercial=.1+x*.2,trusted=True,known_at=10)
    base.update(updates)
    return base

def data(): return [row(i) for i in range(12)]

def test_known_time_isolated():
    # TRAP-42 延迟登记的设备功能码不能进入过去模型。
    initial=fit(data(),50)
    assert fit(data()+[row(80,known_at=50,overnight_lpm=200)],50)==initial

def test_constant_scale_no_zero():
    # TRAP-32 压力恒定时稳健尺度限位而不除零。
    model=fit(data(),50)
    assert model.dispersions[3]==14 and model.size==12
    assert all(value>0 for value in model.dispersions)

def test_cohorts_separate_three_real_loads():
    model=fit(data(),50)
    groups=[choose_group(model,ProfilePoint.parse(item))[0] for item in data()]
    assert groups[0]==groups[3] and groups[4]==groups[7]
    assert len(set(groups))==3 and model.within_l1>0

def test_assignment_after_permutation():
    # TRAP-52 簇号交换后采用全局最优一对一映射。
    assert best_overlap(["R","R","S","S","T"],[2,2,0,0,1])==1
    assert best_overlap(["R","R","S","T"],[2,2,2,0])==.75
    assert best_overlap([],[]) is None

def test_partition_reference_uses_global_optimum():
    reference=["X"]*7+["Y"]*3
    proposed=[0]*4+[1]*3+[0]*3
    assert best_overlap(reference,proposed)==.6
    with pytest.raises(ValueError): best_overlap(["X"],[])

def test_order_not_needed_for_fit():
    reference=fit(data(),50)
    assert reference==fit(reversed(data()),50)
    assert tuple(item.key for item in reference.medoids)==tuple(sorted(item.key for item in reference.medoids))

def test_strict_labels_and_groups():
    with pytest.raises(ValueError): fit(data(),50,0)
    with pytest.raises(ValueError): fit(data()+[data()[0]],50)
    with pytest.raises(ValueError): fit(data(),5)

def test_immutable_inference_score():
    # TRAP-53 每个对象与冻结 medoid 集比较，未使用请求批统计。
    model=fit(data(),50)
    first=ProfilePoint.parse(row(5))
    noisy=ProfilePoint.parse(row(99,overnight_lpm=1300.))
    scores=[choose_group(model,point) for point in [first,noisy,first]]
    assert scores[0]==scores[2] and scores[0][1]<scores[1][1]
