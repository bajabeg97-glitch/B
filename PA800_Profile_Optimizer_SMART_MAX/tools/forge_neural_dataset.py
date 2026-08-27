"""Create a provenance-aware neural clean/corrupt MIDI dataset."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from pa800_optimizer.neural.dataset_forge import audit_dataset_manifest,forge_dataset

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('input_folder');parser.add_argument('--output',required=True);parser.add_argument('--license',required=True);parser.add_argument('--provenance',required=True);parser.add_argument('--dataset-use',choices=('TRAINING','CERTIFICATION'),default='TRAINING');args=parser.parse_args(argv)
    sources=sorted(path for path in Path(args.input_folder).rglob('*') if path.suffix.lower() in ('.mid','.midi','.kar'));manifest=forge_dataset(sources,args.output,args.license,args.provenance,args.dataset_use);audit=audit_dataset_manifest(manifest);print(json.dumps({'manifest':str(Path(args.output)/'DATASET_MANIFEST.json'),'sources':manifest['summary']['unique_sources'],'cases':manifest['summary']['cases'],'hard_negatives':manifest['summary']['hard_negatives'],'audit':audit},indent=2));return 0 if audit['pass'] else 1

if __name__=='__main__':raise SystemExit(main())