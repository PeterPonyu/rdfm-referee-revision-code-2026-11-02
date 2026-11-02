#!/usr/bin/env python3
"""Outcome-informed, prespecified paired-width sensitivity on saved engine data."""
import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
SCRIPT='tools/revision_20261102/a_nonempty_sensitivity.py'
PROTOCOL='archive/2026-11-02-referee-revision/remaining-useful-life/PROTOCOL-NONEMPTY.md'
REF='refs/heads/referee-revision-20261102-a-support-study'
BASE='archive/2026-10-28-finish/remaining-useful-life/studies/A-W3-4E/'
INPUTS={
 'prediction':(BASE+'predictions-FD004-seed-0-cap100-training.npz','9338b30abec74e70858711ce62840dbec0a98714add4d02ba74bb2d81204d58a'),
 'calibration':(BASE+'calibration-summary.csv','4f369273530d30ba6c728cbb3a7e559a792820d97742cd8813be285970bd0594'),
 'band':(BASE+'bands-FD004-seed-0-cap100-temporal_cnn-training_EVAL.npz','2ffc70925720faeb040df97ba5ceaca17e6369995b560c160335247bad46b26f'),
 'constraint':('tools/revision_20261028/a_lifetime_constraints_v1.py','f74b17d2a399bada6ddd90097279d0d7d8ba6b1397eac9478bb46701e5286d77')}
OUTPUT=ROOT/'archive/2026-11-02-referee-revision/remaining-useful-life/NONEMPTY-RESULT.json'
MACRO=ROOT/'build/referee-revision-2026-11-02/remaining-useful-life/revision-analysis.tex'

def sha(x):return hashlib.sha256(x).hexdigest()
def checkhash(data,expected):
 if sha(data)!=expected:raise ValueError('input hash mismatch')
def one(rows):
 if len(rows)!=1:raise ValueError('calibration selector must identify exactly one row')
 return rows[0]
def load_constraints():
 path=ROOT/INPUTS['constraint'][0];checkhash(path.read_bytes(),INPUTS['constraint'][1]);s=importlib.util.spec_from_file_location('a_constraint_frozen',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def pair(low,high,age,cap,mod):
 lower=np.maximum(low,0);upper=np.minimum(high,cap);support={'lower':lower,'upper':upper,'empty':lower>upper}
 exact=mod.inverse_capped(low,high,age,cap);sw=mod.geometric_width(support);ew=mod.geometric_width(exact);ok=~exact['empty']
 if np.any(support['empty'][ok]) or np.any(ew[ok]>sw[ok]+1e-9):raise ValueError('nonempty inverse band violates support containment')
 return sw,ew,ok,exact

def selftest():
 m=load_constraints();low=np.array([10.,10.]);high=np.array([20.,20.]);age=np.array([1.,2.]);sw,ew,ok,_=pair(low,high,age,100,m)
 assert np.all(ok) and np.allclose(sw,[10,10]) and np.allclose(ew,[10,9])
 _,_,ok,_=pair(np.array([101.]),np.array([103.]),np.array([1.]),100,m);assert not ok[0]
 for rows in ([],[1,2]):
  try:one(rows)
  except ValueError:pass
  else:raise AssertionError('missing or duplicate row accepted')
 try:checkhash(b'altered',sha(b'expected'))
 except ValueError:pass
 else:raise AssertionError('changed hash accepted')
 print('synthetic checks passed: narrowing, contradiction, missing/duplicate row, altered hash')

def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
def main(commit):
 if not re.fullmatch(r'[0-9a-f]{40}',commit):raise ValueError('registration commit must be a full SHA-1')
 if git('rev-parse',REF).decode().strip()!=commit:raise ValueError('registration ref mismatch')
 if git('rev-parse',commit+'^').decode().strip()!='49e7bd1041470b7614eb14350adfbfebbb18db46':raise ValueError('unexpected registration parent')
 for path in (SCRIPT,PROTOCOL):
  if git('show',commit+':'+path)!=(ROOT/path).read_bytes():raise ValueError('registration blob mismatch: '+path)
 raw={}
 for key,(path,expected) in INPUTS.items():
  b=(ROOT/path).read_bytes();checkhash(b,expected)
  if git('show','HEAD:'+path)!=b:raise ValueError('input differs from HEAD: '+path)
  raw[key]=b
 if OUTPUT.exists() or MACRO.exists():raise ValueError('refusing to replace an output')
 m=load_constraints();z=np.load(io.BytesIO(raw['prediction']),allow_pickle=False);bands=np.load(io.BytesIO(raw['band']),allow_pickle=False)
 rows=list(csv.DictReader(io.StringIO(raw['calibration'].decode())))
 row=one([r for r in rows if (r['subset'],r['seed'],r['centre'],r['target'],r['cap'],r['alpha'])==('FD004','0','temporal_cnn','cap100','100','0.10')])
 q=float(row['symmetric']);assert np.isfinite(q) and q>=0
 units=z['unit'];ages=z['cycle'];truth=np.minimum(z['truth_uncapped'],100);pred=z['temporal_cnn'];roles=z['role']
 evalunits=np.unique(units[roles=='EVAL']);savedunits=bands['unit']
 if len(evalunits)!=82 or set(evalunits)!=set(savedunits):raise ValueError('evaluation engine mismatch')
 ia=list(bands['alpha']).index('0.10');it1=list(bands['transform']).index('support_only');it2=list(bands['transform']).index('inverse_lifetime')
 allsupport=[];allexact=[];empty_total=0;engines_empty=0;covered=0
 for unit in evalunits:
  ix=np.flatnonzero((units==unit)&(roles=='EVAL'));age=ages[ix];y=truth[ix];p=pred[ix]
  if not len(ix) or np.any(np.diff(age)<=0) or np.any(~np.isfinite(p)):raise ValueError('invalid cycle ordering or predictions')
  low=p-q;high=p+q;sw,ew,ok,exact=pair(low,high,age,100,m)
  su=int(np.flatnonzero(savedunits==unit)[0]); observed_cov=bool(np.all(m.covered(exact,y)));covered+=int(observed_cov)
  checks=[len(ix)==int(bands['cycles'][ia,it2,su]),int((~ok).sum())==int(bands['empty_cycles'][ia,it2,su]),observed_cov==bool(bands['covered'][ia,it2,su]),np.isclose(sw.sum(),bands['geometric_width_sum'][ia,it1,su],atol=1e-6,rtol=0),np.isclose(ew.sum(),bands['geometric_width_sum'][ia,it2,su],atol=1e-6,rtol=0)]
  if not all(checks):raise ValueError('stored per-engine reconstruction mismatch: '+str(unit))
  allsupport.extend(sw[ok]);allexact.extend(ew[ok]);empty_total+=int((~ok).sum());engines_empty+=int(np.any(~ok))
 support=np.array(allsupport);exact=np.array(allexact)
 if len(support)==0 or support.sum()<=0:raise ValueError('no eligible width denominator')
 reductions=support-exact;difference=float(reductions.mean());frac=float(reductions.sum()/support.sum());narrow=int((reductions>1e-9).sum())
 def fmt(value,places):return str(Decimal(str(value)).quantize(Decimal('1').scaleb(-places),rounding=ROUND_HALF_UP))
 displayed={'a-nonempty-cycles':str(len(support)),'a-nonempty-support':fmt(support.mean(),2),'a-nonempty-exact':fmt(exact.mean(),2),'a-nonempty-reduction':fmt(difference,2),'a-nonempty-percent':fmt(100*frac,1),'a-nonempty-narrow':str(narrow)}
 content='\n'.join(['% Exploratory, support-matched nonempty-cycle sensitivity.']+[r'\expandafter\def\csname RevValue'+k+r'\endcsname{'+v+'}' for k,v in sorted(displayed.items())])+'\n'
 result={'classification':'outcome-informed exploratory sensitivity','registration_commit':commit,'original_fit_assignment':0,'new_random_seed':None,'hypothesis':'strictly positive average paired support-only minus exact width on nonempty exact cycles','decision':'positive' if difference>0 else 'failed','engine_count':len(evalunits),'complete_paths_covered':covered,'eligible_cycles':len(support),'excluded_empty_cycles':empty_total,'engines_with_empty_cycles':engines_empty,'support_mean':float(support.mean()),'exact_mean':float(exact.mean()),'mean_paired_reduction':difference,'fraction_support_width_removed':frac,'strictly_narrower_cycles':narrow,'display':displayed,'checks':'every per-engine saved count, support/inverse width sum, inverse empties and whole-path coverage matched','inputs':{k:{'path':p,'sha256':h} for k,(p,h) in INPUTS.items()},'script_sha256':sha((ROOT/SCRIPT).read_bytes()),'protocol_sha256':sha((ROOT/PROTOCOL).read_bytes()),'macro_path':str(MACRO.relative_to(ROOT)),'macro_sha256':sha(content.encode())}
 with MACRO.open('x') as f:f.write(content)
 with OUTPUT.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:result[k] for k in ['classification','decision','engine_count','eligible_cycles','excluded_empty_cycles','support_mean','exact_mean','mean_paired_reduction','fraction_support_width_removed','strictly_narrower_cycles']},indent=2))

if __name__=='__main__':
 if sys.argv.count('--registration-commit')>1 or sys.argv.count('--self-test')>1:raise SystemExit('repeated flag')
 p=argparse.ArgumentParser(allow_abbrev=False);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--registration-commit');a=p.parse_args();selftest() if a.self_test else main(a.registration_commit)
