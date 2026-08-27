"""Build a transparent Voice/Articulation audition queue from one run."""
from __future__ import annotations


def build_audition_queue(intelligence,articulations,repair_previews=None):
    items=[]
    for row in intelligence or []:
        if row.get('action')!='SUGGEST_ONLY' or not row.get('candidate_address'):continue
        improvement=float(row.get('improvement') or 0);confidence=float(row.get('confidence') or 0);priority=improvement*.6+confidence*10
        items.append({'kind':'VOICE','track':row.get('track'),'channel':row.get('channel'),'current':row.get('current_sound'),'candidate':row.get('candidate_sound'),'current_address':row.get('current_address'),'candidate_address':row.get('candidate_address'),'aesthetic':row.get('aesthetic','original'),'confidence':confidence,'improvement':improvement,'evidence_level':row.get('evidence_level','E1'),'reason':row.get('reason'),'priority':round(priority,3),'decision':''})
    for context in (articulations or {}).get('contexts',[]):
        for suggestion in context.get('suggestions',[]):
            if suggestion.get('action') in ('EXISTING_ACTIVE','APPLY'):continue
            confidence=float(suggestion.get('confidence') or 0);priority=confidence*10+(2 if suggestion.get('phrase_position')=='END' else 1 if suggestion.get('phrase_position')=='BODY' else 0)
            items.append({'kind':'ARTICULATION','track':suggestion.get('track'),'channel':suggestion.get('channel'),'sound':context.get('sound'),'address':context.get('address'),'controller':suggestion.get('controller'),'control':suggestion.get('control'),'semantic':suggestion.get('semantic'),'tick':suggestion.get('tick'),'note':suggestion.get('note'),'phrase_position':suggestion.get('phrase_position'),'confidence':confidence,'evidence_level':suggestion.get('evidence_level',context.get('evidence_level','E2')),'reason':suggestion.get('reason'),'priority':round(priority,3),'decision':''})
    for preview in (repair_previews or {}).get('previews',[]):
        for candidate in preview.get('candidates',[]):
            items.append({'kind':'REPAIR_PREVIEW','preview_id':preview.get('preview_id'),'phrase_id':preview.get('phrase_id'),'event_key':preview.get('event_key'),'variant':candidate.get('label'),'task':candidate.get('task'),'delta':candidate.get('delta'),'confidence':preview.get('confidence'),'evidence_level':'E1','reason':'A/B audition candidate; accepting it must create a separate variant.','priority':round(float(preview.get('confidence') or 0)*10,3),'decision':'PENDING','apply_authority':False})
    items.sort(key=lambda row:(-row['priority'],row['kind'],row.get('track') or 0,row.get('channel') or 0))
    return {'schema':'PA800_AUDITION_QUEUE_V2','items':items,'count':len(items),'voice_items':sum(row['kind']=='VOICE' for row in items),'articulation_items':sum(row['kind']=='ARTICULATION' for row in items),'repair_preview_items':sum(row['kind']=='REPAIR_PREVIEW' for row in items),'mutations':0,'authority_granted':False}