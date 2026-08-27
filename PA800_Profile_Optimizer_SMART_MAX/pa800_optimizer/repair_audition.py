"""Create verifier-backed A/B variants from exact Factory velocity changes."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from .core.midi_io import extract_notes, load_midi, save_midi
from .models import Change
from .runtime_safety import OutputLock, commit_artifacts, temp_path_for
from .verifier import verify


_VARIANT_STRENGTH = {'REPAIR': .50, 'NATURAL': .75, 'EXPRESSIVE': 1.0}


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _load_report(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('Invalid optimizer report.')
    velocity=data.get('velocity_conductor') or {}
    if not velocity.get('factory_data_only'):
        raise ValueError('A/B apply requires velocity_factory_data_only=true.')
    return data


def _exact_factory_keys(report):
    rows=(report.get('velocity_conductor') or {}).get('contexts') or []
    return {(int(row['track']),int(row['channel'])-1) for row in rows if row.get('profile_basis')=='EXACT_SOUND_PROFILE' and row.get('evidence_level') in ('E2','E3')}


def _factory_velocity_deltas(report):
    exact=_exact_factory_keys(report);deltas={};rejected=0
    for row in report.get('changes') or []:
        if row.get('kind')!='velocity_conductor':continue
        key=(int(row['track']),int(row['channel']),int(row['note']),int(row['occurrence']))
        if key[:2] not in exact or row.get('protected'):
            rejected+=1;continue
        deltas[key]=deltas.get(key,0)+(int(row['new'])-int(row['old']))
    return deltas,rejected


def _repair_plan(base_midi_path,report_path,label):
    label=str(label or '').strip().upper()
    if label not in _VARIANT_STRENGTH:raise ValueError('Unknown A/B variant: '+label)
    report=_load_report(report_path)
    if int((report.get('change_summary') or {}).get('details_truncated') or 0) and label!='EXPRESSIVE':
        raise ValueError('A/B attenuation requires a complete, non-truncated change ledger.')
    factory_deltas,rejected=_factory_velocity_deltas(report)
    if not factory_deltas and label!='EXPRESSIVE':
        raise ValueError('No exact Factory velocity changes are available for this A/B variant.')
    before=load_midi(str(base_midi_path));note_by_key={(n.track_index,n.channel,n.note,n.occurrence):n for n in extract_notes(before)};strength=_VARIANT_STRENGTH[label];rows=[];missing=[]
    for key,delta in sorted(factory_deltas.items()):
        note=note_by_key.get(key)
        if note is None:missing.append(list(key));continue
        target=max(1,min(127,int(round(note.velocity+(strength-1.0)*delta))))
        if target!=note.velocity:rows.append({'key':key,'old':note.velocity,'new':target})
    return {'label':label,'report':report,'before':before,'strength':strength,'rows':rows,'missing':missing,'rejected':rejected}


def _describe_repair_variant(base_midi_path,report_path,label):
    """Return the exact notes an A/B confirmation will modify, without writing."""
    plan=_repair_plan(base_midi_path,report_path,label)
    return {'variant':plan['label'].title(),'strength':plan['strength'],'applied_velocity_changes':len(plan['rows']),'affected_note_keys':[list(row['key']) for row in plan['rows']],'missing_note_keys':plan['missing'],'rejected_non_exact_or_protected':plan['rejected']}


def _create_repair_variant(base_midi_path, report_path, output_path, label):
    """Attenuate only exact-Factory velocity deltas on a separate MIDI copy."""
    plan=_repair_plan(base_midi_path,report_path,label);label=plan['label'];before=plan['before'];after=copy.deepcopy(before);notes=extract_notes(after)
    note_by_key={(n.track_index,n.channel,n.note,n.occurrence):n for n in notes};authorized=[]
    for row in plan['rows']:
        key=row['key'];note=note_by_key[key];target=row['new'];old=note.velocity;after.tracks[note.track_index][note.on_index]=after.tracks[note.track_index][note.on_index].copy(velocity=target);note.velocity=target
        authorized.append(Change(note.track_index,note.on_index,'velocity',old,target,'accepted_exact_factory_ab_'+label.lower(),channel=note.channel,note=note.note,occurrence=note.occurrence,protected=False))

    checks=verify(before,after,{},set(),[],authorized,[])
    if not checks.get('pass'):raise RuntimeError('A/B verifier rejected variant: '+json.dumps(checks.get('note_diff_diagnostics'),ensure_ascii=False))

    output=Path(output_path);sidecar=output.with_suffix(output.suffix+'.ab.json');tmp=temp_path_for(output,'.tmp.mid');jtmp=temp_path_for(sidecar,'.tmp.json')
    try:
        save_midi(after,str(tmp));persisted=load_midi(str(tmp));disk_checks=verify(before,persisted,{},set(),[],authorized,[])
        if not disk_checks.get('pass'):raise RuntimeError('Persisted A/B verifier rejected variant.')
        payload={'schema':'PA800_REPAIR_AUDITION_V1','created_utc':_utc(),'variant':label.title(),'strength':plan['strength'],'base_midi':str(Path(base_midi_path)),'optimizer_report':str(Path(report_path)),'output':str(output),'factory_data_only':True,'profile_basis':'EXACT_SOUND_PROFILE','rhythm_and_trills_preserved_from_base':True,'applied_velocity_changes':len(authorized),'affected_note_keys':[list(row['key']) for row in plan['rows']],'rejected_non_exact_or_protected':plan['rejected'],'missing_note_keys':plan['missing'],'verifier':disk_checks}
        jtmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False,sort_keys=True),encoding='utf-8')
        with OutputLock(output):commit_artifacts([(tmp,output),(jtmp,sidecar)])
        return {**payload,'sidecar':str(sidecar)}
    finally:
        for path in (tmp,jtmp):
            try:path.unlink()
            except FileNotFoundError:pass