#!/usr/bin/env python3
"""Pure causal interval constraints for uncapped and capped remaining life."""
from __future__ import annotations

import numpy as np


def uncapped(lo, hi, age, nonnegative=False):
    lower = np.maximum.accumulate(np.asarray(lo)+age)-age
    upper = np.minimum.accumulate(np.asarray(hi)+age)-age
    if nonnegative: lower = np.maximum(lower,0)
    return dict(lower=lower,upper=upper,empty=lower>upper)


def legacy_capped(lo, hi, age):
    lower = np.maximum.accumulate(np.asarray(lo)+age)-age
    upper = np.minimum.accumulate(np.asarray(hi))
    return dict(lower=lower,upper=upper,empty=lower>upper)


def inverse_capped(lo, hi, age, cap):
    lo = np.asarray(lo,float); hi = np.asarray(hi,float); age = np.asarray(age,float)
    supported_lo = np.maximum(lo,0); supported_hi = np.minimum(hi,cap)
    invalid = (supported_lo>supported_hi) | (supported_lo>cap) | (supported_hi<0)
    lifetime_lower = np.maximum.accumulate(age+supported_lo)
    lifetime_upper = np.minimum.accumulate(np.where(supported_hi<cap,age+supported_hi,np.inf))
    empty = np.maximum.accumulate(invalid) | (lifetime_lower>lifetime_upper)
    lower = np.minimum(np.maximum(lifetime_lower-age,0),cap)
    upper = np.minimum(np.maximum(lifetime_upper-age,0),cap)
    # A contradictory lifetime set may map both displayed endpoints to the cap.
    # The explicit empty-set flag is authoritative; never turn that into width.
    return dict(lower=lower,upper=upper,empty=empty,lifetime_lower=lifetime_lower,lifetime_upper=lifetime_upper)


def geometric_width(result):
    return np.where(result['empty'],0,np.maximum(result['upper']-result['lower'],0))


def covered(result,truth):
    return ~result['empty'] & (result['lower']<=truth) & (truth<=result['upper'])


def known_answer_test():
    checks=[]
    def check(name,ok):checks.append(dict(name=name,passed=bool(ok)))
    age=np.arange(1,11);truth=np.repeat(100.,10);lo=truth-1;hi=truth+1
    wrong=uncapped(lo,hi,age);correct=inverse_capped(lo,hi,age,100)
    check('flat_cap_refutes_naive_uncapped_intersection',np.all((lo<=truth)&(truth<=hi)) and not np.all(covered(wrong,truth)) and np.all(covered(correct,truth)))
    check('upper_at_or_above_cap_has_no_finite_lifetime_upper',np.all(np.isinf(correct['lifetime_upper'])) and np.all(correct['upper']==100))
    age=np.arange(1,5);l=np.array([99.,101.,99.,99.]);u=l+2
    contradiction=inverse_capped(l,u,age,100)
    check('lower_above_cap_is_infeasible_and_stays_empty',not contradiction['empty'][0] and np.all(contradiction['empty'][1:]) and np.all(geometric_width(contradiction)[1:]==0))
    tight=inverse_capped(np.array([10.,9.]),np.array([20.,19.]),np.array([1,2]),100)
    check('upper_below_cap_gives_finite_lifetime_constraint',np.array_equal(tight['lifetime_upper'],[21.,21.]) and np.array_equal(tight['upper'],[20.,19.]))
    rng=np.random.default_rng(2026102804);bad=contained_bad=0
    for i in range(100):
        life=int(rng.integers(50,301));cap=int(rng.choice([100,125,150]));t=np.arange(1,life+1);y=np.minimum(life-t,cap)
        p=y+rng.normal(0,5,len(y));q=20 if i%2==0 else 2;low=p-q;high=p+q
        for result in [legacy_capped(low,high,t),inverse_capped(low,high,t,cap)]:
            original=(low<=y)&(y<=high);projected=covered(result,y)
            bad+=int(not np.array_equal(np.logical_and.accumulate(original),np.logical_and.accumulate(projected)))
            nonempty=~result['empty'];contained_bad+=int(np.any(result['lower'][nonempty]<low[nonempty]-1e-10) or np.any(result['upper'][nonempty]>high[nonempty]+1e-10))
    check('every_capped_prefix_event_preserved_legacy_and_inverse',bad==0)
    check('nonempty_projected_sets_contained_in_current_band',contained_bad==0)
    original=np.array([100.,100.]);projected=np.array([0.,50.]);cycles=np.array([1,9])
    equal_engine=float(projected.mean()/original.mean());cycle_weighted=float(np.sum(projected*cycles)/np.sum(original*cycles))
    check('cycle_weighting_is_not_equal_engine_weighting',equal_engine==.25 and cycle_weighted==.45)
    return dict(passed=all(r['passed'] for r in checks),checks=checks,seed=2026102804,scientific_inputs_read=False)
