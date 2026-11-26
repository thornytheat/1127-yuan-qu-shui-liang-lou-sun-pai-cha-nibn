from .contracts import ProfilePoint
from .medoids import fit,choose_group,best_overlap

def segment_profiles(history, registry, at):
    segmentation=fit(history,at)
    indexed={}
    for profile in registry:
        point=ProfilePoint.parse(profile)
        cohort,distance=choose_group(segmentation,point)
        indexed[point.key]={"meter":point.key,"sector":point.sector,"cohort":cohort,"distance":distance,
                            "typical_lpm":next(x.overnight_lpm for x in segmentation.medoids if x.key==cohort)}
    return segmentation, indexed
