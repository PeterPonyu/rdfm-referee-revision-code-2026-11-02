#!/usr/bin/env python3
"""Post hoc descriptions from fixed aggregate outputs; see the registered protocol."""
import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = 'tools/revision_20261102/reviewer_saved_cells.py'
PROTOCOL = 'archive/2026-11-02-referee-revision/PROTOCOLS/REVIEWER-SAVED-CELLS.md'
REF = 'refs/heads/referee-revision-20261102-evidence'
OUT = 'archive/2026-11-02-referee-revision/REVIEWER-SAVED-LEDGER.json'
INPUTS = {
 'a': ('archive/2026-10-28-finish/remaining-useful-life/studies/A-W3-4E/bands-FD004-seed-0-cap100-temporal_cnn-training_EVAL.npz', '2ffc70925720faeb040df97ba5ceaca17e6369995b560c160335247bad46b26f'),
 'b': ('archive/2026-10-28-finish/spatial-transcriptomics/studies/B-W3-5/results.json', '0a66f6994ba98b9ba48142513c2def5d0d6bd47b5c4d67dc2ed04fd10c137c71'),
 'c': ('archive/2026-10-27-revision-w2/multi-site-prediction/studies/C-W2-3-loso-remedy/per-fold-results.csv', 'ff25505da97f2973f00f788a35d44c1920bf23d8e17280b6cd588b2b5a4edee7'),
 'r_choices': ('archive/2026-10-28-finish/restoration-risk/studies/R-W3-3/summary-01/summary.json', '06cb47cbfe7a4cd6dc31d1dd4b84035e50a069d8ffde6654ff9491eab1449a18'),
 'r_metrics': ('archive/2026-10-27-revision/restoration-risk/analysis/registered-report/complete-metric-summary.csv', '53243ea33db5c6c16f63490962049e602b15dce9d99ba320abc43fcf3b3a0ce2'),
}
SLUGS = {'a':'remaining-useful-life','b':'spatial-transcriptomics','c':'multi-site-prediction','r':'restoration-risk'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_hash(data, expected):
    if digest(data) != expected:
        raise ValueError('input hash mismatch')


def one(rows, label):
    if len(rows) != 1:
        raise ValueError(f'{label}: expected exactly one row; got {len(rows)}')
    return rows[0]


def pair(rows):
    groups = {}
    methods = {'a_record_weighted', 'b_site_balanced'}
    for row in rows:
        if row['method'] not in methods:
            continue
        key = (row['seed'], row['held_out_site'])
        group = groups.setdefault(key, {})
        if row['method'] in group:
            raise ValueError(f'duplicate pairing {key}')
        group[row['method']] = row
    if not groups or any(set(group) != methods for group in groups.values()):
        raise ValueError('missing paired row')
    return groups


def count_comparison(groups, field):
    ans = {'higher': 0, 'equal': 0, 'lower': 0}
    for group in groups.values():
        a = Decimal(group['a_record_weighted'][field])
        b = Decimal(group['b_site_balanced'][field])
        ans['higher' if b > a else 'lower' if b < a else 'equal'] += 1
    return ans


def fmt(x, places):
    return str(Decimal(str(x)).quantize(Decimal('1').scaleb(-places), rounding=ROUND_HALF_UP))


def self_test():
    good = [dict(seed='1',held_out_site='x',method='a_record_weighted',threshold='0.2'),dict(seed='1',held_out_site='x',method='b_site_balanced',threshold='0.3')]
    assert count_comparison(pair(good), 'threshold') == {'higher':1,'equal':0,'lower':0}
    for bad in (good[:1], good + good[:1]):
        try: pair(bad)
        except ValueError: pass
        else: raise AssertionError('bad pairing accepted')
    for bad in ([], [1, 2]):
        try: one(bad, 'synthetic')
        except ValueError: pass
        else: raise AssertionError('bad selection accepted')
    try: check_hash(b'changed', digest(b'expected'))
    except ValueError: pass
    else: raise AssertionError('bad hash accepted')
    print('synthetic checks: paired rows accepted; missing, duplicate and changed-hash inputs rejected')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def main(commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('registration commit must be a full lowercase SHA-1')
    if git('rev-parse',REF).decode().strip() != commit:
        raise ValueError('registration branch does not point to supplied commit')
    head = git('rev-parse','HEAD').decode().strip()
    if git('rev-parse',commit + '^').decode().strip() != head:
        raise ValueError('registration is not a direct child of current HEAD')
    for path in (SCRIPT,PROTOCOL):
        if git('show',commit + ':' + path) != (ROOT / path).read_bytes():
            raise ValueError(f'registered file changed: {path}')
    data = {}
    for key,(path,expected) in INPUTS.items():
        raw = (ROOT / path).read_bytes()
        check_hash(raw,expected)
        if git('show', 'HEAD:' + path) != raw:
            raise ValueError(f'input differs from HEAD: {path}')
        data[key] = raw
    paths = {key:ROOT/'build/referee-revision-2026-11-02'/slug/'revision-cells.tex' for key,slug in SLUGS.items()}
    outputs = list(paths.values()) + [ROOT / OUT]
    if any(path.exists() for path in outputs):
        raise ValueError('output already exists')

    values = {key:{} for key in SLUGS}
    details = {}
    def add(paper,key,raw,display,selector):
        values[paper][key] = str(display)
        details[key] = {'paper':paper,'selector':selector,'raw':str(raw),'display':str(display)}

    a = np.load(io.BytesIO(data['a']), allow_pickle=False)
    alpha = list(a['alpha']).index('0.10')
    transform = list(a['transform']).index('inverse_lifetime')
    empty = a['empty_cycles'][alpha,transform]
    cycles = a['cycles'][alpha,transform]
    if len(empty) != 82 or len(cycles) != 82:
        raise ValueError('unexpected engine denominator')
    for key,val in [('a-empty-engines',int((empty>0).sum())),('a-empty-cycles',int(empty.sum())),('a-total-cycles',int(cycles.sum()))]:
        add('a',key,val,val,'alpha=0.10, transform=inverse_lifetime, primary-role FD004')
    b = json.loads(data['b'])['results']['oracle_matched_coverage']['0.9']
    aps = Decimal(str(b['APS']['metrics']['mean_set_size']['mean']))
    hull = Decimal(str(b['APS_HULL']['metrics']['mean_set_size']['mean']))
    diff = hull - aps
    add('b','b-hull-minus-aps',diff,fmt(diff,4),'oracle-matched family mean sizes: APS_HULL minus APS at coverage 0.9')
    groups = pair(list(csv.DictReader(io.StringIO(data['c'].decode()))))
    if len(groups) != 380 or len({k[0] for k in groups}) != 20 or len({k[1] for k in groups}) != 19:
        raise ValueError('unexpected site/allocation pairing dimensions')
    tc,cc = count_comparison(groups,'threshold'),count_comparison(groups,'coverage')
    add('c','c-threshold-higher',tc['higher'],tc['higher'],'site-balanced greater threshold in paired seed/site')
    add('c','c-pairs',len(groups),len(groups),'paired seed/site rows')
    details['c-all-comparisons'] = {'paper':'c','threshold':tc,'coverage':cc,'interpretation':'reused sites; score weights and infinity mass differ'}
    choices = [x for x in json.loads(data['r_choices'])['individual_selections'] if x['classifier']=='logistic']
    keys = [(x['seed'],x['sigma']) for x in choices]
    if len(choices)!=15 or len(set(keys))!=15 or any(x['pixel_selected']!='unet' for x in choices):
        raise ValueError('unexpected selector cells or pixel selections')
    agree = sum(x['decision_selected']==x['pixel_selected'] for x in choices)
    add('r','r-selector-agree',agree,agree,'logistic decision and pixel selector agree on U-Net')
    add('r','r-selector-total',len(choices),len(choices),'logistic pipeline/noise cells')
    rows = list(csv.DictReader(io.StringIO(data['r_metrics'].decode())))
    rule_map = {'degraded':'always_degraded','restored':'always_restored','flip':'flip_aware_confidence','sign':'true_sign'}
    metric_map = {'accuracy':('absolute_accuracy',4),'harm':('marginal_harm',4),'help':('help_kept',1)}
    for name,rule in rule_map.items():
        for short,(metric,places) in metric_map.items():
            matches = [x for x in rows if (x['run'],x['classifier'],x['transformation'],x['restorer'],x['rule'],x['metric']) == ('decisive','logistic','low-resolution','cubic',rule,metric)]
            row = one(matches, f'{rule}/{metric}')
            if row['n_valid'] != '10': raise ValueError('unexpected replicate count')
            add('r',f'r-{name}-{short}',row['mean'],fmt(row['mean'],places),f'decisive/logistic/low-resolution/cubic/{rule}/{metric}')
    rendered = {}
    for paper,path in paths.items():
        lines = ['% Deterministic post hoc descriptions; provenance is in REVIEWER-SAVED-LEDGER.json.',r'\newcommand{\Rev}[1]{\csname RevValue#1\endcsname}']
        for key,value in sorted(values[paper].items()):
            lines.append(r'\expandafter\def\csname RevValue'+key+r'\endcsname{'+value+'}')
        rendered[path] = ('\n'.join(lines)+'\n').encode()
    ledger = {'classification':'post hoc descriptive; outcomes already observed', 'seed':None,'registration_commit':commit,'script':SCRIPT,'script_sha256':digest((ROOT/SCRIPT).read_bytes()),'protocol':PROTOCOL,'protocol_sha256':digest((ROOT/PROTOCOL).read_bytes()),'inputs':{key:{'path':path,'sha256':sha} for key,(path,sha) in INPUTS.items()},'results':details,'outputs':{str(path.relative_to(ROOT)):digest(raw) for path,raw in rendered.items()}}
    for path,raw in rendered.items():
        with path.open('xb') as f: f.write(raw)
    with (ROOT/OUT).open('x') as f:
        json.dump(ledger,f,indent=2,sort_keys=True); f.write('\n')
    print(f'wrote {len(rendered)} candidate macro files and {OUT}; post hoc only')


if __name__ == '__main__':
    if sys.argv.count('--registration-commit')>1 or sys.argv.count('--self-test')>1:
        raise SystemExit('repeated flag')
    p = argparse.ArgumentParser(allow_abbrev=False)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--self-test',action='store_true')
    group.add_argument('--registration-commit')
    args = p.parse_args()
    if args.self_test: self_test()
    else: main(args.registration_commit)
