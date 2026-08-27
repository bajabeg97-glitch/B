import csv,json
from pa800_optimizer.audition_queue import build_audition_queue
from pa800_optimizer.analysis.repair_previews import _filter_protected_repair_previews
from pa800_optimizer.models import NoteEvent
from tools.build_audition_queue import export


def fixture():
    intelligence=[{'action':'SUGGEST_ONLY','track':2,'channel':1,'current_sound':'Piano GM','candidate_sound':'Grand Piano','current_address':[121,0,0],'candidate_address':[121,3,0],'aesthetic':'natural','confidence':.9,'improvement':12,'evidence_level':'E2','reason':'test'}]
    articulations={'contexts':[{'sound':'Alto Sax DNC','address':[121,12,65],'evidence_level':'E2','suggestions':[{'action':'SUGGEST','track':3,'channel':2,'controller':'SC2','control':81,'semantic':'growl_sax','tick':100,'note':65,'phrase_position':'END','confidence':.88,'reason':'phrase'}]}]}
    return intelligence,articulations


def test_audition_queue_combines_voice_and_articulation_without_mutation():
    queue=build_audition_queue(*fixture())
    assert queue['count']==2 and queue['voice_items']==1 and queue['articulation_items']==1 and queue['mutations']==0
    assert queue['items'][0]['priority']>=queue['items'][1]['priority']


def test_audition_queue_exports_csv_and_json(tmp_path):
    intelligence,articulations=fixture();report=tmp_path/'report.json';report.write_text(json.dumps({'intelligence':intelligence,'articulations':articulations}),encoding='utf-8');output=export(report)
    assert len(list(csv.DictReader(output.open(encoding='utf-8-sig'))))==2 and output.with_suffix('.json').exists()


def test_audition_queue_exposes_repair_previews_as_pending_ab_candidates():
    previews={'previews':[{'preview_id':'p1','phrase_id':'phrase:0','event_key':[0,1,0,60,0],'confidence':.72,'candidates':[{'label':'Repair','task':'velocity_delta','delta':-6},{'label':'Natural','task':'velocity_delta','delta':-9}]}]}
    queue=build_audition_queue([],{},previews)
    rows=[row for row in queue['items'] if row['kind']=='REPAIR_PREVIEW']
    assert queue['schema']=='PA800_AUDITION_QUEUE_V2' and queue['repair_preview_items']==2
    assert {row['variant'] for row in rows}=={'Repair','Natural'} and all(row['decision']=='PENDING' and not row['apply_authority'] for row in rows)


def test_final_protection_removes_preview_and_audition_candidates():
    preview={'schema':'PA800_REPAIR_PREVIEWS_V1','analyzer_only':True,'authority_granted':False,'mutations':0,'applied_actions':0,'previews':[{'preview_id':'p1','event_key':[0,1,0,60,0],'finding_kind':'VELOCITY_ANOMALY','candidates':[{'label':'Natural','task':'velocity_delta','delta':-3}]}]}
    note=NoteEvent(0,0,60,90,0,96,0,1,0,protected=True)
    filtered=_filter_protected_repair_previews(preview,[note]);queue=build_audition_queue([],{},filtered)
    assert filtered['summary']['previews']==0 and filtered['summary']['removed_protected']==1
    assert queue['repair_preview_items']==0