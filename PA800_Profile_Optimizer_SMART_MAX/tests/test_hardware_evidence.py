import json
from pa800_optimizer.hardware_evidence import HardwareEvidenceRegistry


def test_hardware_registry_matches_voice_and_articulation_e3(tmp_path):
    path=tmp_path/'evidence.json';path.write_text(json.dumps({'records':[
        {'kind':'voice','source_address':[121,0,24],'target_address':[121,15,24],'family':'GUITAR','aesthetic':'natural','approval':'auto'},
        {'kind':'articulation','source_address':[121,12,65],'control':81,'semantic':'growl_sax','approval':'safe-auto'},
        {'kind':'fx','source_address':[121,3,0],'family':'PIANO','scope':'section','approval':'auto'},
    ]}),encoding='utf-8')
    registry=HardwareEvidenceRegistry(path)
    assert registry.available and registry.voice_approval((121,0,24),(121,15,24),'GUITAR','natural')['evidence_level']=='E3'
    assert registry.voice_approval((121,0,24),(121,15,24),'GUITAR','modern') is None
    assert registry.articulation_approval((121,12,65),81,'growl_sax')['approval']=='safe-auto'
    assert registry.fx_approval((121,3,0),'PIANO','section')['approval']=='auto'


def test_invalid_hardware_record_never_grants_authority(tmp_path):
    path=tmp_path/'bad.json';path.write_text('{"records":[{"kind":"voice","approval":"auto"}]}',encoding='utf-8');registry=HardwareEvidenceRegistry(path)
    assert not registry.available and registry.records==[] and registry.errors