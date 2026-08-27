"""Safely materialize embedded Factory/Gold archives for labeled training."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

MIDI={'.mid','.midi','.kar'}


def extract(archive,destination,label):
    destination.mkdir(parents=True,exist_ok=True);rows=[]
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            pure=PurePosixPath(info.filename)
            if info.is_dir() or pure.suffix.lower() not in MIDI:continue
            if pure.is_absolute() or '..' in pure.parts:raise ValueError('Unsafe ZIP member: '+info.filename)
            name=('%04d_'%len(rows))+pure.name;target=destination/name
            with source.open(info) as incoming,target.open('wb') as outgoing:shutil.copyfileobj(incoming,outgoing)
            rows.append({'corpus':label,'source_member':info.filename,'training_file':name,'bytes':info.file_size})
    return rows


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--factory',required=True);ap.add_argument('--gold',required=True);ap.add_argument('--output',required=True);ns=ap.parse_args(argv)
    root=Path(ns.output);factory=extract(ns.factory,root/'factory','FACTORY');gold=extract(ns.gold,root/'gold','GOLD');combined=root/'combined';combined.mkdir(parents=True,exist_ok=True)
    for label,folder in (('FACTORY',root/'factory'),('GOLD',root/'gold')):
        for path in sorted(folder.iterdir()):
            if path.is_file():shutil.copy2(path,combined/(label+'_'+path.name))
    manifest={'schema':'PA800_PREPARED_FACTORY_GOLD_TRAINING_V1','factory_files':len(factory),'gold_files':len(gold),'combined_files':len(factory)+len(gold),'velocity_neural_input':False,'velocity_neural_output':False,'rows':factory+gold}
    (root/'PREPARED_CORPUS_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in manifest.items() if k!='rows'},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
