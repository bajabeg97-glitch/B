"""Build bounded, audition-only repair candidates from Phrase Doctor findings."""
from __future__ import annotations

import hashlib
import json


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def _build_repair_previews(notes, phrase_doctor):
    by_key={(note.track_index,note.channel+1,note.onset,note.note,note.occurrence):note for note in notes};rows=[]
    strengths=(('Repair',.50),('Natural',.75),('Expressive',1.0))
    for finding in phrase_doctor.get('findings',[]):
        key=tuple(finding.get('event_key') or ());note=by_key.get(key)
        if note is None or note.protected:continue
        kind=finding.get('kind');reference=finding.get('reference_value')
        if kind=='VELOCITY_ANOMALY' and reference is not None:
            base=max(-12,min(12,int(round(float(reference)-note.velocity))))
            task='velocity_delta'
        elif kind=='GATE_ANOMALY' and reference is not None:
            base=max(1,min(96,int(round(float(reference)-note.duration))))
            task='gate_delta'
        else:continue
        candidates=[]
        for label,strength in strengths:
            delta=int(round(base*strength))
            if delta:candidates.append({'label':label,'task':task,'delta':delta,'bounded':True,'apply_authority':False})
        if candidates:rows.append({'preview_id':_digest({'event_key':key,'kind':kind,'candidates':candidates})[:24],'phrase_id':finding.get('phrase_id'),'finding_kind':kind,'event_key':list(key),'confidence':finding.get('confidence'),'uncertainty':finding.get('uncertainty'),'candidates':candidates,'requested_action':'AUDITION_ONLY','applied':False})
    payload={'schema':'PA800_REPAIR_PREVIEWS_V1','analyzer_only':True,'authority_granted':False,'mutations':0,'applied_actions':0,'previews':rows,'summary':{'previews':len(rows),'candidates':sum(len(row['candidates']) for row in rows),'velocity_previews':sum(row['finding_kind']=='VELOCITY_ANOMALY' for row in rows),'gate_previews':sum(row['finding_kind']=='GATE_ANOMALY' for row in rows)},'limits':['Preview deltas are not applied to MIDI.','Timing-gap findings remain review-only until calibrated against musician-labelled data.']}
    return {**payload,'digest':_digest(payload)}


def _filter_protected_repair_previews(report,notes):
    """Remove candidates invalidated by the final RX/DNC/intent protection pass."""
    protected={(note.track_index,note.channel+1,note.onset,note.note,note.occurrence) for note in notes if note.protected}
    rows=[row for row in report.get('previews',[]) if tuple(row.get('event_key') or ()) not in protected]
    removed=len(report.get('previews',[]))-len(rows);summary=dict(report.get('summary') or {})
    summary.update({'previews':len(rows),'candidates':sum(len(row.get('candidates',[])) for row in rows),'velocity_previews':sum(row.get('finding_kind')=='VELOCITY_ANOMALY' for row in rows),'gate_previews':sum(row.get('finding_kind')=='GATE_ANOMALY' for row in rows),'removed_protected':removed})
    payload={**report,'previews':rows,'summary':summary}
    payload.pop('digest',None);return {**payload,'digest':_digest(payload)}