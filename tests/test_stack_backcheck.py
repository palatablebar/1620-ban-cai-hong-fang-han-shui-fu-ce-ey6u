from math import isclose

from kilnboard.stack_backcheck.calibration import conformal_radius,fit_adjustment
from kilnboard.stack_backcheck.contracts import ValidationPoint
from kilnboard.stack_backcheck.metrics import average_precision,classification,confusion,regression


def point(k,score,outcome,confirmed=True):
    return ValidationPoint(str(k),'站点',k,score,outcome,confirmed)


# TRAP-43
def test_no_positive_average_precision():
    assert average_precision([(.8,0),(.2,0)]) is None
    assert average_precision([]) is None
    assert average_precision([(.6,1),(.3,1)])==1


def test_score_ties_metrics_are_order_invariant():
    scores=[(.7,0),(.9,0),(.7,1),(.4,1)]
    assert average_precision(scores)==average_precision(list(reversed(scores)))
    assert isclose(average_precision(scores),(1/3 + 2/4)/2)


def test_conformal_skips_censored_and_uses_finite_sample_rank():
    evidence = [point(i,i,0) for i in range(1,9)]
    evidence.append(point(9,214,0,False))
    assert conformal_radius(evidence,.82)==8
    band = fit_adjustment(evidence,True,False)
    assert band.samples==8 and band.interval(3)==(0,11)


def test_isotonic_never_inverts_sort_order():
    source=[point(i,i/36, i%4==0 if i<19 else i%4!=0) for i in range(36)]
    curve = fit_adjustment(source,False,True)
    outputs = [curve.apply(i/35) for i in range(36)]
    assert min(outputs)>=0 and max(outputs)<=1
    assert outputs==sorted(outputs)


def test_one_class_residual_has_empirical_fallback():
    source=[point(i,i/2,0) for i in range(20)]
    curve=fit_adjustment(source,False,False)
    assert curve.apply(10)>curve.apply(3)
    measured=classification(source,curve,0.1,.5)
    assert measured['status']=='单一类别' and measured['average_precision'] is None


def test_censoring_report_separates_failed_lower_bound():
    sample=[point(1,5,6),point(2,5,7),point(3,2,10,False)]
    interval=fit_adjustment(sample,True,False)
    metrics=regression(sample,interval,2)
    assert metrics['count']==2 and metrics['right_censored']==1 and metrics['too_short_for_observed_censor']==1
    assert metrics['mae']==1.5 and metrics['baseline_mae']==4.5


def test_threshold_equality_is_selected():
    assert confusion([(.5,1),(.49999,1),(.9,0),(.2,0)],.5)=={'tp':1,'tn':1,'fp':1,'fn':1}


def test_real_replay_has_disjoint_calibration_and_holdout(prepared):
    evidence=prepared.replay.report()
    span=prepared.vintage
    assert evidence['calibration_count'] <= len(span.calibration.evaluated)
    assert evidence['holdout']['count'] <= len(span.holdout.evaluated)
    assert all(span.holdout.lower<=item.day<span.holdout.upper for item in prepared.replay.points)
