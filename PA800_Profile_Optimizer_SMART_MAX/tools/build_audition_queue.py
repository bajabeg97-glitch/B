"""Export the embedded audition queue from an optimizer JSON report."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from pa800_optimizer.audition_queue import build_audition_queue


def export(report_path,output_csv=None):
    report=json.loads(Path(report_path).read_text(encoding='utf-8'));queue=report.get('audition_queue') or build_audition_queue(report.get('intelligence',[]),report.get('articulations',{}));output=Path(output_csv or Path(report_path).with_name(Path(report_path).stem+'_AUDITION_QUEUE.csv'));fields=sorted({key for row in queue['items'] for key in row}) or ['kind','decision']
    with output.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(queue['items'])
    output.with_suffix('.json').write_text(json.dumps(queue,indent=2,ensure_ascii=False),encoding='utf-8');return output


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('report');ap.add_argument('--output');ns=ap.parse_args(argv);print('AUDITION_QUEUE:',export(ns.report,ns.output))


if __name__=='__main__':main()