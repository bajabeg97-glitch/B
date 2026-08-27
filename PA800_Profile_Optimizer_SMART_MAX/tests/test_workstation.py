import json
import wave

import pytest

from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.workstation import PHASES,WorkstationSession,apply_export_preset,build_mixer_snapshot


def test_session_variants_undo_redo_are_non_destructive(tmp_path):
    source=tmp_path/'song.mid';a=tmp_path/'a.mid';b=tmp_path/'b.mid';source.write_bytes(b'original');a.write_bytes(b'variant-a');b.write_bytes(b'variant-b');session=WorkstationSession(tmp_path/'session.json')
    va=session.record_variant(source,a,config={'mode':'natural'},label='A');vb=session.record_variant(source,b,config={'mode':'modern'},label='B')
    assert session.active_variant()['id']==vb['id'] and a.exists() and b.exists()
    assert session.undo()['id']==va['id'] and a.exists() and b.exists()
    assert session.redo()['id']==vb['id'] and len(session.data['variants'])==2


def test_session_records_accept_and_reject_audition_decisions(tmp_path):
    session=WorkstationSession(tmp_path/'session.json')
    accepted=session._record_audition_decision('ACCEPT','Natural',tmp_path/'in.mid',tmp_path/'out.mid',tmp_path/'report.json',{'factory_data_only':True})
    rejected=session._record_audition_decision('REJECT',details={'reason':'musician_choice'})
    reloaded=WorkstationSession(tmp_path/'session.json')
    assert accepted['action']=='ACCEPT' and rejected['action']=='REJECT'
    assert [row['action'] for row in reloaded.data['audition_decisions']]==['ACCEPT','REJECT']


def test_corrupt_existing_session_is_not_silently_reset_or_overwritten(tmp_path):
    path=tmp_path/'session.json';original=b'{broken-json';path.write_bytes(original)
    with pytest.raises(ValueError,match='Invalid workstation session'):
        WorkstationSession(path)
    assert path.read_bytes()==original


def test_audio_reference_records_wave_metadata_and_hash(tmp_path):
    source=tmp_path/'song.mid';output=tmp_path/'out.mid';source.write_bytes(b'x');output.write_bytes(b'y');session=WorkstationSession(tmp_path/'session.json');variant=session.record_variant(source,output)
    audio=tmp_path/'capture.wav'
    with wave.open(str(audio),'wb') as stream:stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\x00\x00'*8000)
    row=session.attach_audio(audio,variant['id'])
    assert row['duration_seconds']==1.0 and row['sample_rate']==8000 and row['variant_id']==variant['id']
    assert row['waveform_envelope'] and max(row['waveform_envelope'])==0


def test_phase_journal_resumes_only_nonterminal_files(tmp_path):
    a=tmp_path/'a.mid';b=tmp_path/'b.mid';session=WorkstationSession(tmp_path/'session.json');session.begin_batch([a,b],{'mode':'auto'});session.record_phase(a,'PREFLIGHT',{'pass':True});session.record_phase(a,'VERIFY',{'pass':True});session.finish_file(a,'PASS',tmp_path/'a_out.mid');session.record_phase(b,'DOCTOR',{'repairs':1})
    reloaded=WorkstationSession(tmp_path/'session.json')
    assert reloaded.pending_inputs()==[str(b)]
    item=next(row for row in reloaded.data['batch']['items'] if row['input']==str(b));assert item['last_phase']=='DOCTOR' and item['phases']==['DOCTOR']


def test_export_presets_enforce_content_and_preserve_authority():
    song=apply_export_preset(OptimizeConfig.for_mode('live'),'song');style=apply_export_preset(OptimizeConfig.for_mode('live'),'style');preserve=apply_export_preset(OptimizeConfig.for_mode('max'),'preserve')
    assert song.content_type=='song' and style.content_type=='style'
    assert preserve.mode=='preserve' and preserve.smart_policy_override=='suggest' and not preserve.apply_high_confidence_sound_changes and preserve.mix_fx_policy=='shadow'


def test_mixer_snapshot_joins_context_velocity_fx_and_voice():
    report={'contexts':[{'track':0,'channel':1,'role':'SONG','family':'PIANO','sound':'Grand','evidence_level':'E2','conflict':False}],'musical_context':{'track_functions':[{'track':0,'channel':1,'function':'LEAD'}]},'velocity_conductor':{'contexts':[{'track':0,'channel':1,'normalized_median_before':.8,'normalized_median_after':1.0,'effective_energy_after':.95}]},'mix_fx_director':{'contexts':[{'track':0,'channel':1,'existing_events':2,'changes':1,'apply_status':'applied_bounded_dry_guard'}]},'intelligence':[{'track':0,'channel':1,'action':'KEEP_BEST','sound_apply_status':'already_target'}],'verifier':{'pass':True}}
    snapshot=build_mixer_snapshot(report);row=snapshot['rows'][0]
    assert row['function']=='LEAD' and row['velocity_after']==1.0 and row['fx_changes']==1 and snapshot['summary']['verifier_pass']