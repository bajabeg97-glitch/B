from pa800_optimizer.analysis.repair_previews import _build_repair_previews
from pa800_optimizer.models import NoteEvent


def test_repair_previews_offer_bounded_audition_variants_without_mutation():
    note=NoteEvent(0,0,60,120,0,144,0,1,0)
    doctor={'findings':[{'phrase_id':'phrase:0','kind':'VELOCITY_ANOMALY','event_key':[0,1,0,60,0],'reference_value':70,'confidence':.72,'uncertainty':.28}]}
    result=_build_repair_previews([note],doctor)
    assert result['analyzer_only'] and result['authority_granted'] is False and result['mutations']==0
    assert result['summary']['previews']==1
    row=result['previews'][0]
    assert [item['label'] for item in row['candidates']]==['Repair','Natural','Expressive']
    assert all(item['task']=='velocity_delta' and abs(item['delta'])<=12 and not item['apply_authority'] for item in row['candidates'])