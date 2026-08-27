"""Style-grouped proxy holdout for instrument-family profile stability.

The source stability artifact already splits support by disjoint Style groups.
This evaluator performs leave-one-fold-out prediction of velocity medians.  It
measures Factory generalization only; it is not an audio preference test.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
TARGETS={
    'BASS':10.0,'GUITAR':10.0,'PIANO':8.0,
    'STRINGS':10.0,'ENSEMBLE':10.0,'SYNTH_PAD':10.0,'CHOIR_VOICE':10.0,
    'ORGAN':8.0,'BRASS':10.0,'REED':10.0,'PIPE':10.0,'HARMONICA':10.0,
    'ACCORDION_REED':10.0,
}


def evaluate(data=None):
    if data is None:data=json.loads((ROOT/'pa800_optimizer'/'profiles'/'data'/'factory_profile_stability_v1.json').read_text(encoding='utf-8'))
    rows=[];families=defaultdict(list)
    for profile in data.get('profiles',[]):
        identity=profile.get('identity',{});family=str(identity.get('org_family') or '').upper()
        if family not in TARGETS:continue
        folds=[fold for fold in profile.get('folds',[]) if fold.get('p50') is not None or fold.get('v_p50') is not None]
        values=[float(fold.get('p50',fold.get('v_p50'))) for fold in folds]
        if len(values)<3:continue
        errors=[]
        for index,held in enumerate(values):errors.append(abs(held-statistics.median(values[:index]+values[index+1:])))
        row={'family':family,'address':[identity.get('msb'),identity.get('lsb'),identity.get('program')],'sound':identity.get('sound'),'role':identity.get('role'),'styles':profile.get('support',{}).get('styles'),'stability':profile.get('stability'),'fold_medians':values,'loo_absolute_errors':errors,'median_error':round(statistics.median(errors),3),'max_error':round(max(errors),3),'proxy_threshold':TARGETS[family]}
        row['proxy_pass']=row['stability'] in ('STABLE','MODERATE') and row['max_error']<=TARGETS[family];rows.append(row);families[family].append(row)
    summary={}
    for family,items in sorted(families.items()):
        summary[family]={'profiles':len(items),'stable_or_moderate':sum(row['stability'] in ('STABLE','MODERATE') for row in items),'proxy_pass':sum(row['proxy_pass'] for row in items),'median_loo_error':round(statistics.median(row['median_error'] for row in items),3) if items else None,'threshold':TARGETS[family]}
    return {'schema':'PA800_INSTRUMENT_FAMILY_GROUPED_HOLDOUT_V1','grouping':'disjoint Factory Style folds stored in factory_profile_stability_v1.json','authority_granted':False,'warning':'Velocity-median reconstruction proxy; not audible Pa800 quality or role accuracy.','families':summary,'rows':rows}


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'INSTRUMENT_FAMILY_HOLDOUT_2.4.json'));args=parser.parse_args(argv);report=evaluate();Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({key:value for key,value in report.items() if key!='rows'},indent=2,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())