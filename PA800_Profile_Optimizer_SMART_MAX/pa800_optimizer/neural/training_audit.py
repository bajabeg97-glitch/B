"""Read-only, deterministic audit of user-selected neural training folders."""
from __future__ import annotations

import hashlib
import json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

from .dataset_forge import balanced_group_splits
from .event_contract import encode_neural_contract,neural_contract_digest,validate_neural_contract
from ..profiles.registry import ProfileRegistry

SCHEMA='PA800_NEURAL_TRAINING_FOLDER_AUDIT_V1'
MIDI_EXTENSIONS={'.mid','.midi','.kar'}


def _utc():return datetime.now(timezone.utc).isoformat()


def _reason(code,message,**details):
    row={'code':code,'message':message};row.update(details);return row


def audit_training_folder(folder,include_contracts=False):
    """Inspect a corpus without modifying it and produce grouped, leak-free splits."""
    root=Path(folder)
    if not root.is_dir():raise ValueError('Training folder does not exist: '+str(root))
    paths=sorted((path for path in root.rglob('*') if path.is_file() and path.suffix.lower() in MIDI_EXTENSIONS),key=lambda path:path.relative_to(root).as_posix().lower())
    accepted=[];rejected=[];contracts=[];seen_sha={};registry=None
    for path in paths:
        relative=path.relative_to(root).as_posix()
        try:raw=path.read_bytes()
        except Exception as exc:
            rejected.append({'file':relative,'reason':_reason('READ_ERROR','Fajl se ne može pročitati',error=repr(exc))});continue
        digest=hashlib.sha256(raw).hexdigest()
        if not raw:
            rejected.append({'file':relative,'bytes':0,'sha256':digest,'reason':_reason('EMPTY_FILE','Prazan MIDI/KAR fajl')});continue
        if digest in seen_sha:
            rejected.append({'file':relative,'bytes':len(raw),'sha256':digest,'reason':_reason('DUPLICATE_CONTENT','Isti sadržaj je već pronađen',duplicate_of=seen_sha[digest])});continue
        try:
            if registry is None:registry=ProfileRegistry()
            contract=encode_neural_contract(path,include_source_bytes=False,registry=registry,_source_bytes=raw);validation=validate_neural_contract(contract)
            if not validation['pass']:raise ValueError('contract validation: '+','.join(validation['errors']))
            notes=len(contract.get('note_tokens') or [])
            if notes<=0:
                rejected.append({'file':relative,'bytes':len(raw),'sha256':digest,'reason':_reason('NO_NOTE_EVENTS','Nema note-on/note-off parova za trening')});continue
            if contract['source']['filename']!=relative:
                contract['source']['filename']=relative
                contract['contract_digest']=neural_contract_digest(contract)
        except Exception as exc:
            rejected.append({'file':relative,'bytes':len(raw),'sha256':digest,'reason':_reason('INVALID_MIDI','MIDI/KAR parser ili ugovor nije validan',error_type=type(exc).__name__,error=str(exc))});continue
        seen_sha[digest]=relative;contracts.append(contract)
        accepted.append({'file':relative,'bytes':len(raw),'sha256':digest,'source_group_id':contract['source_group_id'],'notes':notes,'protected_notes':validation['protected_notes']})
    split_map=balanced_group_splits(row['source_group_id'] for row in accepted)
    for row in accepted:row['split']=split_map[row['source_group_id']]
    group_splits=defaultdict(set)
    for row in accepted:group_splits[row['source_group_id']].add(row['split'])
    leakage={group:sorted(splits) for group,splits in group_splits.items() if len(splits)>1}
    split_counts=Counter(row['split'] for row in accepted)
    reason_counts=Counter(row['reason']['code'] for row in rejected)
    enough=len(accepted)>=3 and all(split_counts[split]>0 for split in ('train','validation','test'))
    audit={'schema':SCHEMA,'created_utc':_utc(),'folder':str(root.resolve()),'read_only':True,'mutations_to_original_sources':0,'discovered_files':len(paths),'accepted_files':len(accepted),'rejected_files':len(rejected),'accepted':accepted,'rejected':rejected,'rejection_counts':dict(sorted(reason_counts.items())),'splits':{split:split_counts[split] for split in ('train','validation','test')},'source_groups':len(group_splits),'group_split_leakage':leakage,'minimum_requirements':{'unique_valid_sources':3,'all_splits_non_empty':True},'pass':enough and not leakage,'authority_granted':False}
    audit['audit_digest']=hashlib.sha256(json.dumps({key:value for key,value in audit.items() if key!='audit_digest'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    if include_contracts:audit['_contracts']=contracts
    return audit


def public_training_audit(audit):return {key:value for key,value in audit.items() if key!='_contracts'}


def render_training_audit(audit):
    lines=['=== AUDIT TRAINING FOLDERA ===','Folder: '+str(audit['folder']),'Pronađeno: %d | Validno: %d | Odbijeno: %d'%(audit['discovered_files'],audit['accepted_files'],audit['rejected_files']),'Splitovi: train=%d, validation=%d, test=%d'%(audit['splits']['train'],audit['splits']['validation'],audit['splits']['test']),'Group leakage: '+('NEMA' if not audit['group_split_leakage'] else 'OTKRIVEN')]
    for row in audit['accepted']:lines.append('[ACCEPT] %(file)s | notes=%(notes)s | split=%(split)s | group=%(source_group_id)s'%row)
    for row in audit['rejected']:lines.append('[REJECT] %s | %s | %s'%(row['file'],row['reason']['code'],row['reason']['message']))
    lines.append('AUDIT RESULT: '+('PASS — folder je spreman za trening' if audit['pass'] else 'FAIL — trebaju najmanje 3 validna izvora i sva tri split-a'))
    lines.append('Audit SHA256: '+audit['audit_digest'])
    return '\n'.join(lines)+'\n'