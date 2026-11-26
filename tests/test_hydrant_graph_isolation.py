import pytest
from meterloss.loss_screen.isolation_graph import PipeLink, ValvePulse, downstream, localize, path_to_root
from meterloss.pipeline import run

def section(source, target, **changes):
    fields=dict(sector="景行",parent=source,child=target,material="球墨铸铁",age_years=8,prior=.2)
    fields.update(changes)
    return fields

def branch():
    return [section("入口","A"),section("A","B"),section("B","C"),section("B","D"),section("A","E")]

def change(label,target,after,**edits):
    record=dict(name=label,sector="景行",interrupted=target,before_lpm=9.,after_lpm=after,reliable=True,observed=100)
    record.update(edits)
    return record

def test_subtree_rollup_includes_actuated_valve_own_segment():
    state=path_to_root(list(map(lambda row:PipeLink(**row),branch())))
    assert downstream(state,"B")=={"B","C","D"}
    assert downstream(state,"E")=={"E"}
    assert state["C"]=="B"

def test_independent_valves_localize_to_intersection_of_positive_cuts():
    trial=[change("V1","B",5.),change("V2","C",4.),change("V3","D",8.8),change("V4","E",8.8)]
    result=localize(branch(),trial,130)[0]
    assert result["priority_branch"]=="C" and result["located"]
    assert result["isolation_support"]==4
    assert result["rank"][0]["share"] > .8
    assert sum(item["share"] for item in result["rank"])==pytest.approx(1.,abs=.000004)
    assert result==localize(branch()[::-1],trial[::-1],130)[0]

def test_insufficient_experiment_count_keeps_candidate_pending():
    prior=branch()
    prior[2]=section("B","C",prior=.9)
    evidence=localize(prior,[change("V1","C",5.)],130)[0]
    assert evidence["rank"][0]["node"]=="C" and evidence["rank"][0]["share"]>.65
    assert evidence["priority_branch"] is None and not evidence["located"]
    assert evidence["isolation_support"]==1

def test_unknown_and_future_valve_trials_do_not_enter_replay():
    experiment=[change("V1","B",5.),change("V2","C",4.,observed=130),change("V6","E",3.,reliable=False),
                change("V9","不存在",3.)]
    old=localize(branch(),experiment,129)[0]
    reviewed=localize(branch(),experiment,130)[0]
    assert old["isolation_support"]==1 and old["priority_branch"] is None
    assert reviewed["isolation_support"]==2 and reviewed["rank"][0]["node"]=="C"

def test_isolation_right_at_measurement_boundary_supports_cut():
    trial=[change("V1","B",7.8,before_lpm=9.1),change("V2","C",7.5)]
    outcome=localize(branch(),trial,140)[0]
    assert outcome["priority_branch"]=="C"
    assert outcome["rank"][-1]["share"]<.08

@pytest.mark.parametrize(("payload","expected"),[
    ([section("A","B"),section("B","C"),section("C","A")],"存在环"),
    ([section("A","B"),section("A","C"),section("B","C")],"多条入边"),
    ([section("A","B"),section("Z","Y")],"进水根"),
])
def test_network_structure_detection_refuses_ambiguous_isolation(payload,expected):
    with pytest.raises(ValueError,match=expected):
        localize(payload,[],120)

@pytest.mark.parametrize("invalid",[{"before_lpm":-2},{"after_lpm":float("nan")},{"reliable":1}])
def test_invalid_isolation_samples_rejected(invalid):
    with pytest.raises(ValueError):
        ValvePulse(**dict(change("V1","C",5.),**invalid))

def test_duplicate_night_valve_id_cannot_strengthen_its_evidence():
    record=change("V1","C",5.)
    with pytest.raises(ValueError,match="多次"):
        localize(branch(),[record,record],200)

def test_workbench_shows_rank_without_demanding_every_zone_be_resolved():
    instance=run()
    stages=instance["stages"][3]["records"]
    ranked=[row for row in stages if "isolation_support" in row]
    assert len(ranked)==3
    assert {row["located"] for row in ranked}=={True,False}
    for zone in ranked:
        ranked_share=[row["share"] for row in zone["rank"]]
        assert ranked_share==sorted(ranked_share,reverse=True)


def test_exact_one_point_two_liters_is_in_positive_experiment_class():
    outcomes=localize(branch(),[change("A","B",7.5,before_lpm=8.7),change("B","C",7.5,before_lpm=8.7)],120)
    below=localize(branch(),[change("A","B",7.50001,before_lpm=8.7),change("B","C",7.50001,before_lpm=8.7)],120)
    assert outcomes[0]["priority_branch"]=="C"
    assert below[0]["priority_branch"]!=outcomes[0]["priority_branch"]
    evidence=below[0]["rank"]
    c_position=next(i for i,row in enumerate(evidence) if row["node"]=="C")
    assert c_position==len(evidence)-1


def test_valve_result_is_not_borrowed_by_neighboring_sector_with_same_branch_labels():
    north=[dict(row,sector="景北") for row in branch()]
    station=[change("V1","B",5.),change("V2","C",5.)]
    findings=localize(branch()+north,station,120)
    result={record["sector"]: record for record in findings}
    assert result["景行"]["priority_branch"]=="C"
    assert result["景北"]["isolation_support"]==0
    assert not result["景北"]["located"] and result["景北"]["priority_branch"] is None
    assert {r["share"] for r in result["景北"]["rank"]}=={.2}
