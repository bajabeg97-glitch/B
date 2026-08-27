"""Evaluate Drum/Bass/Guitar/Piano family intent on canonical real-SMF pairs."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from pa800_optimizer.understanding_cli import analyze_file


ROOT=Path(__file__).resolve().parents[1]
FAMILIES={'DRM','BAS','GTR','PNO'}


def evaluate(folder):
    folder=Path(folder);manifest=json.loads((folder/'INSTRUMENT_INTENT_STRESS_MANIFEST.json').read_text(encoding='utf-8'));rows=[]
    cases=[case for case in manifest.get('cases',[]) if case['scenario_id'].split('-')[0] in FAMILIES]
    for case in cases:
        path=folder/case['file'];first=analyze_file(path,'auto');second=analyze_file(path,'auto');family=first.get('family_intent',{});summary=family.get('summary',{});note_rows=family.get('note_intents',[])
        checks={
            'schema':family.get('schema')=='PA800_FAMILY_INTENT_V1',
            'analysis_only':family.get('analyzer_only') is True and family.get('authority_granted') is False and int(family.get('mutations',-1))==0,
            'no_automation_apply':int((family.get('automation') or {}).get('applied_actions',-1))==0,
            'deterministic_digest':family.get('digest')==second.get('family_intent',{}).get('digest'),
            'has_input_notes':int(summary.get('input_notes',0))>0,
            'all_rows_authority_free':all(row.get('automation_authority') is False and int(row.get('mutations',-1))==0 for row in note_rows),
            'integrated_digest':first.get('instrument_intent',{}).get('family_models',{}).get('digest')==family.get('digest'),
        }
        rows.append({'scenario_id':case['scenario_id'],'polarity':case['polarity'],'file':case['file'],'family_digest':family.get('digest'),'classified_notes':summary.get('classified_notes',0),'by_family':summary.get('by_family',{}),'by_label':summary.get('by_label',{}),'checks':checks,'pass':all(checks.values())})
    pairs={}
    for row in rows:pairs.setdefault(row['scenario_id'],{})[row['polarity']]=row['family_digest']
    separated={key:set(value)=={'positive','negative'} and value['positive']!=value['negative'] for key,value in pairs.items()};failures=[row for row in rows if not row['pass']];categories=Counter(row['scenario_id'].split('-')[0] for row in rows)
    return {'schema':'PA800_FAMILY_INTENT_STRESS_RESULT_V1','fixture_schema':manifest.get('schema'),'midi_case_count':len(rows),'scenario_count':len(pairs),'category_case_counts':dict(sorted(categories.items())),'passed_cases':len(rows)-len(failures),'failed_cases':len(failures),'pair_separation_passed':sum(separated.values()),'pair_separation_total':len(separated),'all_pairs_separated':bool(separated) and all(separated.values()),'mutations':0,'authority_granted':False,'rows':rows,'pass':len(rows)==38 and not failures and len(separated)==19 and all(separated.values())}


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default=str(ROOT/'INSTRUMENT_INTENT_STRESS_2.5.0'));parser.add_argument('--output',default=str(ROOT/'FAMILY_INTENT_STRESS_RESULT.json'));args=parser.parse_args(argv);report=evaluate(args.folder);Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({key:value for key,value in report.items() if key!='rows'},indent=2));return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())