"""Aggregate per-file Factory Usage Meter reports for batch auditing."""
from __future__ import annotations

import csv
import json
from collections import Counter,defaultdict
from pathlib import Path


def aggregate_usage_reports(reports):
    files=[];classes=Counter();stages=Counter();families=defaultdict(Counter);invalid=[]
    for source,payload in reports:
        meter=(payload or {}).get('factory_usage_meter') or {}
        if meter.get('schema')!='PA800_FACTORY_USAGE_METER_V1':
            invalid.append(str(source));continue
        files.append({'source':str(source),'notes_total':int(meter.get('notes_total',0)),'pass':bool(meter.get('pass')),'blocked_mutation_count':int(meter.get('blocked_mutation_count',0))})
        classes.update({key:int(value) for key,value in (meter.get('classification_counts') or {}).items()})
        stages.update({key:int(value) for key,value in (meter.get('stage_counts') or {}).items()})
        for row in meter.get('by_family') or []:
            family=str(row.get('family','UNKNOWN'))
            for key,value in row.items():
                if key not in ('family','coverage_percent') and isinstance(value,(int,float)):families[family][key]+=int(value)
    total=int(stages.get('total',0));classification_sum=sum(classes.values())
    family_rows=[]
    for family,row in sorted(families.items(),key=lambda item:(-item[1]['total'],item[0])):
        family_rows.append({'family':family,**dict(row),'coverage_percent':round(100*row['total']/max(1,total),4)})
    return {
        'schema':'PA800_FACTORY_USAGE_BATCH_V1','files_total':len(files),'invalid_reports':invalid,
        'notes_total':total,'classification_counts':dict(sorted(classes.items())),'stage_counts':dict(stages),
        'stage_percentages':{key:round(100*int(stages.get(key,0))/max(1,total),4) for key in ('available','resolved','used','mutated','blocked')},
        'by_family':family_rows,'files':files,
        'invariants':{'classification_sum':classification_sum,'classification_equals_total':classification_sum==total,'all_reports_pass':all(row['pass'] for row in files),'no_blocked_note_mutated':all(row['blocked_mutation_count']==0 for row in files)},
        'pass':not invalid and classification_sum==total and all(row['pass'] and row['blocked_mutation_count']==0 for row in files),
    }


def load_and_aggregate(paths):
    reports=[]
    for path in paths:
        p=Path(path)
        try:payload=json.loads(p.read_text(encoding='utf-8'))
        except Exception:payload={}
        reports.append((p,payload))
    return aggregate_usage_reports(reports)


def write_batch_outputs(result,json_path,csv_path):
    Path(json_path).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    fields=['family','total','available','resolved','used','mutated','blocked','coverage_percent']
    with Path(csv_path).open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for row in result.get('by_family') or []:writer.writerow({field:row.get(field,0) for field in fields})