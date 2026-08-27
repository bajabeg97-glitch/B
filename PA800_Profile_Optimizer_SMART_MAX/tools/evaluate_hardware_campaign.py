#!/usr/bin/env python3
"""Merge a campaign CSV into the manifest and calculate 2.5 gates."""
import argparse,csv,json
from pathlib import Path

from pa800_optimizer.analysis.hardware_campaign import evaluate_hardware_campaign

TRUE={'1','true','yes','y','da'}


def load(manifest,csv_path):
    data=json.loads(Path(manifest).read_text(encoding='utf-8'));records=[]
    with Path(csv_path).open(encoding='utf-8-sig',newline='') as handle:
        for row in csv.DictReader(handle):
            normalized=dict(row)
            for field in ('top1_correct','top3_correct','false_positive','mud_failure','stuck_note','wrong_program','lost_articulation','playback_error'):normalized[field]=str(row.get(field,'')).strip().lower() in TRUE
            records.append(normalized)
    data['records']=records;return data


def main():
    parser=argparse.ArgumentParser();parser.add_argument('manifest');parser.add_argument('results_csv');parser.add_argument('--output',default='HARDWARE_EVALUATION.json');args=parser.parse_args();result=evaluate_hardware_campaign(load(args.manifest,args.results_csv));Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({'pass':result['pass'],'records':result['input_records'],'gates':result['gates']},indent=2));raise SystemExit(0 if result['pass'] else 1)


if __name__=='__main__':main()