"""Create human-editable Intent V3 track-role annotation sheets."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from pa800_optimizer.understanding_cli import analyze_file


def generate(input_folder,output_csv,limit=230):
    folder=Path(input_folder);files=sorted(path for path in folder.iterdir() if path.suffix.lower() in ('.mid','.midi','.kar'))[:max(0,int(limit))];rows=[];manifest=[]
    for file_index,path in enumerate(files):
        digest=hashlib.sha256(path.read_bytes()).hexdigest();report=analyze_file(path,'auto');content=report['content_detection']['content_type'];intent=report['instrument_intent'];split=('test' if file_index%5==0 else 'validation' if file_index%5==1 else 'train')
        manifest.append({'file':path.name,'source_sha256':digest,'content_type':content,'split':split,'intent_digest':intent['intent_digest']})
        for row in intent['track_intents']:
            rows.append({'file':path.name,'source_sha256':digest,'content_type':content,'split':split,'track':row['track'],'channel':row['channel'],'family':row['identity']['family'],'sound':row['identity']['sound'],'predicted_function':row['label'],'prediction_confidence':row['confidence'],'evidence_level':row['evidence_level'],'human_function':'','annotator':'','comments':''})
    output=Path(output_csv);output.parent.mkdir(parents=True,exist_ok=True);fields=list(rows[0]) if rows else ['file','source_sha256','content_type','split','track','channel','predicted_function','prediction_confidence','human_function','annotator','comments']
    with output.open('w',encoding='utf-8-sig',newline='') as stream:writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    manifest_path=output.with_suffix('.manifest.json');manifest_path.write_text(json.dumps({'schema':'PA800_INSTRUMENT_INTENT_GROUND_TRUTH_TEMPLATE_V2','input_folder':str(folder),'files':len(files),'track_rows':len(rows),'annotation_csv':output.name,'entries':manifest},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return output,manifest_path


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('input_folder');parser.add_argument('--output',default='INSTRUMENT_INTENT_GROUND_TRUTH.csv');parser.add_argument('--limit',type=int,default=230);args=parser.parse_args(argv);sheet,manifest=generate(args.input_folder,args.output,args.limit);print('TRACK_SHEET:',sheet);print('MANIFEST:',manifest);return 0


if __name__=='__main__':raise SystemExit(main())