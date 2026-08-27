"""Build and certify the canonical Neural Dataset V2 stress package."""
from __future__ import annotations
import argparse,hashlib,json,shutil
from pathlib import Path
import mido
from pa800_optimizer.neural.dataset_forge import CORRUPTION_TYPES,audit_dataset_manifest,forge_dataset
from pa800_optimizer.neural.event_contract import decode_unchanged_contract,encode_neural_contract,validate_neural_contract
from tools.instrument_intent_stress_midis import generate_case as generate_intent_case
from tools.section_narrative_stress_midis import generate_case as generate_section_case

ROOT=Path(__file__).resolve().parents[1]
SPECS=[('INT-001','positive'),('INT-002','positive'),('DRM-001','positive'),('BAS-005','positive'),('GTR-001','positive'),('PNO-002','positive'),('EXP-002','positive'),('AUT-003','negative'),('SEC3-001','positive'),('SEC3-004','positive'),('SEC3-006','positive'),('SEC3-012','positive')]

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _transpose(source,output,semitones=2):
    mid=mido.MidiFile(source,clip=False)
    for track in mid.tracks:
        for index,message in enumerate(track):
            if message.type in ('note_on','note_off') and 0<=message.note+semitones<=127:track[index]=message.copy(note=message.note+semitones)
    mid.save(output)

def _chord_source(output):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.extend([mido.MetaMessage('track_name',name='Neural Chord Comp',time=0),mido.Message('control_change',channel=0,control=0,value=121,time=0),mido.Message('control_change',channel=0,control=32,value=3,time=0),mido.Message('program_change',channel=0,program=0,time=0)])
    for chord in ((60,64,67),(62,65,69),(64,67,71),(65,69,72)):
        for pitch in chord:track.append(mido.Message('note_on',channel=0,note=pitch,velocity=68+(pitch%11),time=0))
        for index,pitch in enumerate(chord):track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=96 if index==0 else 0))
    mid.save(output)

def certify(output):
    output=Path(output)
    if output.exists():shutil.rmtree(output)
    sources=output/'sources';roundtrip_dir=output/'roundtrip';sources.mkdir(parents=True);roundtrip_dir.mkdir(parents=True);source_paths=[]
    for identifier,polarity in SPECS:
        path=sources/f'{identifier}_{polarity}.mid'
        if identifier.startswith('SEC3-'):generate_section_case(identifier,polarity,path)
        else:generate_intent_case(identifier,polarity,path)
        source_paths.append(path)
    transposed=sources/'GTR-001_transposed.mid';_transpose(sources/'GTR-001_positive.mid',transposed);source_paths.append(transposed);chord=sources/'NEURAL_CHORD_COMP.mid';_chord_source(chord);source_paths.append(chord)
    before={path.name:_sha(path) for path in source_paths};roundtrip=[];contracts={}
    for path in source_paths:
        contract=encode_neural_contract(path);contracts[path.name]=contract;validation=validate_neural_contract(contract);decoded=roundtrip_dir/path.name;result=decode_unchanged_contract(contract,decoded);roundtrip.append({'file':path.name,'contract_digest':contract['contract_digest'],'source_group_id':contract['source_group_id'],'raw_events':len(contract['raw_events']),'note_tokens':len(contract['note_tokens']),'protected_notes':sum(row['protected'] for row in contract['note_tokens']),'validation_pass':validation['pass'],'byte_identical':result['pass'] and path.read_bytes()==decoded.read_bytes()})
    first=forge_dataset(source_paths,output/'dataset_a','PROJECT_SYNTHETIC_FIXTURE','PA800_CANONICAL_STRESS_GENERATORS','CERTIFICATION');second=forge_dataset(source_paths,output/'dataset_b','PROJECT_SYNTHETIC_FIXTURE','PA800_CANONICAL_STRESS_GENERATORS','CERTIFICATION');audit=audit_dataset_manifest(first);after={path.name:_sha(path) for path in source_paths};guitar_same_group=contracts['GTR-001_positive.mid']['source_group_id']==contracts['GTR-001_transposed.mid']['source_group_id'];guitar_same_split=next(row['split'] for row in first['sources'] if row['file']=='GTR-001_positive.mid')==next(row['split'] for row in first['sources'] if row['file']=='GTR-001_transposed.mid')
    checks={'source_count':len(source_paths)==14,'roundtrip':all(row['validation_pass'] and row['byte_identical'] for row in roundtrip),'event_attribution':all(row['note_tokens']>0 for row in roundtrip),'all_corruption_types':set(first['summary']['corruption_types'])==set(CORRUPTION_TYPES),'dataset_scale':first['summary']['cases']>=50,'hard_negatives':first['summary']['hard_negatives']>=20,'protected_only_sources_fail_closed':first['summary']['protected_only_sources']>=2,'dataset_audit':audit['pass'],'deterministic_dataset_digest':first['dataset_digest']==second['dataset_digest'],'transposition_grouping':guitar_same_group and guitar_same_split,'original_sources_unchanged':before==after,'no_raw_private_payload_in_json':'source_bytes_b64' not in json.dumps(first),'authority':first['authority_granted'] is False and first['mutations_to_original_sources']==0,'velocity_is_profile_only':not any(str(name).startswith('VELOCITY_') for name in first['summary']['corruption_types'])}
    report={'schema':'PA800_NEURAL_DATASET_CERTIFICATION_V2','release':'3.2.0-alpha1','sources':len(source_paths),'roundtrip_passed':sum(row['validation_pass'] and row['byte_identical'] for row in roundtrip),'dataset_cases':first['summary']['cases'],'hard_negatives':first['summary']['hard_negatives'],'protected_only_sources':first['summary']['protected_only_sources'],'corruption_types':first['summary']['corruption_types'],'source_groups':len({row.get('source_group_id') for row in first['sources'] if row.get('included')}),'dataset_digest':first['dataset_digest'],'roundtrip':roundtrip,'dataset_audit':audit,'checks':checks,'mutations_to_original_sources':0,'authority_granted':False,'trained_model':False,'pass':all(checks.values())};(ROOT/'NEURAL_DATASET_CERTIFICATION_RESULT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return report

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'NEURAL_DATASET_STRESS_3.2.0'));args=parser.parse_args(argv);report=certify(args.output);print(json.dumps({key:value for key,value in report.items() if key!='roundtrip'},indent=2));return 0 if report['pass'] else 1

if __name__=='__main__':raise SystemExit(main())
