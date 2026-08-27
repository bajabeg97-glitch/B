from pathlib import Path
from types import SimpleNamespace

from pa800_optimizer.engines import timing
from pa800_optimizer.engines.timing import _trained_rhythm_shifts,_trill_groups
from pa800_optimizer.models import NoteEvent


def test_trill_group_detects_close_alternating_two_note_run():
    notes=[NoteEvent(0,0,60 if index%2==0 else 62,80,index*48,index*48+36,index*2,index*2+1,index) for index in range(6)]
    groups=_trill_groups(notes,96)
    assert len(groups)==1 and [note.note for note in groups[0]]==[60,62,60,62,60,62]


def test_trill_group_rejects_wide_or_non_alternating_run():
    notes=[NoteEvent(0,0,note,80,index*48,index*48+36,index*2,index*2+1,index) for index,note in enumerate([60,65,60,65,60])]
    assert _trill_groups(notes,96)==[]


def test_explicit_trained_trill_application_is_bounded_and_never_uses_velocity(monkeypatch):
    notes=[NoteEvent(0,0,60 if index%2==0 else 62,80,index*48,index*48+36,index*2,index*2+1,index) for index in range(6)]
    contexts={(0,0):SimpleNamespace(family='PIANO',role='ACC1')};model={'model_digest':'abc','acceptance':{'pass':True,'confidence':.5},'authority_granted':False}
    monkeypatch.setattr(timing,'load_encoder_model',lambda _path,require_accepted=False:model)
    monkeypatch.setattr(timing,'_predict_masked_array',lambda *_args,**_kwargs:(('onset_delta_beats','duration_beats'),[[0.03125,0.03125] for _ in notes]))
    shifts,reasons,gates,gate_reasons,summary=_trained_rhythm_shifts(SimpleNamespace(ticks_per_beat=96),notes,contexts,'model.json')
    assert shifts and max(abs(value) for value in shifts.values())<=12
    assert any(reason=='explicit_trained_trill_spacing' for reason in reasons.values())
    assert gates and all(reason=='explicit_trained_note_duration' for reason in gate_reasons.values())
    assert summary['velocity_features_applied']==summary['pitch_features_applied']==summary['voice_settings_applied']==0
    assert summary['explicit_user_authority'] is True


def test_trained_model_cache_reuses_model_until_transfer_changes_file(tmp_path,monkeypatch):
    model_path=tmp_path/'model.json';model_path.write_text('one',encoding='utf-8');calls=[]
    monkeypatch.setattr(timing,'load_encoder_model',lambda path,require_accepted=True:calls.append(Path(path).read_text()) or {'model_digest':'x','acceptance':{'pass':True}})
    monkeypatch.setattr(timing,'_predict_masked_array',lambda *_args,**_kwargs:(('onset_delta_beats','duration_beats'),[]));timing._TRAINED_MODEL_CACHE.clear();mid=SimpleNamespace(ticks_per_beat=96)
    _trained_rhythm_shifts(mid,[],{},model_path);_trained_rhythm_shifts(mid,[],{},model_path)
    assert calls==['one']
    model_path.write_text('changed',encoding='utf-8');_trained_rhythm_shifts(mid,[],{},model_path)
    assert calls==['one','changed']


def test_last_note_cannot_move_earlier_and_shorten_track(monkeypatch):
    note=NoteEvent(0,0,60,80,48,96,0,1,0);ctx=SimpleNamespace(family='PIANO',role='ACC1',identity=SimpleNamespace(msb=121,lsb=3,program=0,address=lambda:(121,3,0)))
    mid=SimpleNamespace(ticks_per_beat=96,tracks=[[SimpleNamespace()]])
    monkeypatch.setattr(timing,'absolute_track',lambda _track:[[48,0,SimpleNamespace()],[96,1,SimpleNamespace()]])
    monkeypatch.setattr(timing,'rebuild_track',lambda events:events)
    monkeypatch.setattr(timing,'_trained_rhythm_shifts',lambda *_args:({timing.note_id(note):-3},{timing.note_id(note):'explicit_trained_rhythm_model'},{timing.note_id(note):-3},{timing.note_id(note):'explicit_trained_note_duration'},{'timing_proposed_notes':1}))
    monkeypatch.setattr(timing,'policy_for',lambda _family:{'timing':True})
    monkeypatch.setattr(timing,'profile_evidence_allows_mutation',lambda *_args:True)
    monkeypatch.setattr(timing,'sustained_timing_guard_ids',lambda *_args:set());monkeypatch.setattr(timing,'organ_legato_note_ids',lambda *_args:set());monkeypatch.setattr(timing,'ambiguous_occurrence_note_ids',lambda *_args:set());monkeypatch.setattr(timing,'expressive_controller_channels',lambda *_args:set())
    cfg=SimpleNamespace(enable_timing=True,timing_strength=1.0,apply_trained_rhythm_model=True,trained_rhythm_model_path='model.json',trained_rhythm_only=True,enable_rhythm_trill_correction=True)
    report=SimpleNamespace(changes=[],workstation={});timing.optimize_timing(mid,[note],{(0,0):ctx},{(0,0):{}},SimpleNamespace(),cfg,report)
    assert report.changes==[]