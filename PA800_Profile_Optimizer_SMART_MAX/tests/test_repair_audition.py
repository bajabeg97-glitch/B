import json

import mido
import pytest

from pa800_optimizer.core.midi_io import extract_notes,load_midi
from pa800_optimizer.repair_audition import _create_repair_variant,_describe_repair_variant


def _write_midi(path,velocity=90):
    mid=mido.MidiFile(ticks_per_beat=480);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.Message('note_on',channel=0,note=60,velocity=velocity,time=0))
    track.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=240))
    track.append(mido.MetaMessage('end_of_track',time=0));mid.save(path)


def _write_report(path,basis='EXACT_SOUND_PROFILE'):
    path.write_text(json.dumps({'velocity_conductor':{'factory_data_only':True,'contexts':[{'track':0,'channel':1,'profile_basis':basis,'evidence_level':'E2'}]},'changes':[{'track':0,'channel':0,'note':60,'occurrence':0,'kind':'velocity_conductor','old':70,'new':90,'protected':False}]}),encoding='utf-8')


def test_ab_variant_attenuates_only_exact_factory_velocity(tmp_path):
    base=tmp_path/'optimized.mid';report=tmp_path/'optimized.mid.report.json';output=tmp_path/'natural.mid';_write_midi(base);_write_report(report)
    preview=_describe_repair_variant(base,report,'Natural');result=_create_repair_variant(base,report,output,'Natural');before=extract_notes(load_midi(base))[0];after=extract_notes(load_midi(output))[0]
    assert before.velocity==90 and after.velocity==85
    assert (before.onset,before.off)==(after.onset,after.off)
    assert result['factory_data_only'] and result['rhythm_and_trills_preserved_from_base'] and result['verifier']['pass']
    assert preview['applied_velocity_changes']==result['applied_velocity_changes']==1
    assert preview['affected_note_keys']==result['affected_note_keys']==[[0,0,60,0]]
    assert output.with_suffix('.mid.ab.json').exists()


def test_ab_variant_rejects_non_exact_factory_velocity(tmp_path):
    base=tmp_path/'optimized.mid';report=tmp_path/'optimized.mid.report.json';_write_midi(base);_write_report(report,'FACTORY_FAMILY_AGGREGATE')
    with pytest.raises(ValueError,match='No exact Factory velocity changes'):_create_repair_variant(base,report,tmp_path/'repair.mid','Repair')


def test_ab_variant_rejects_truncated_change_ledger(tmp_path):
    base=tmp_path/'optimized.mid';report=tmp_path/'optimized.mid.report.json';_write_midi(base);_write_report(report)
    payload=json.loads(report.read_text(encoding='utf-8'));payload['change_summary']={'details_truncated':4};report.write_text(json.dumps(payload),encoding='utf-8')
    with pytest.raises(ValueError,match='complete, non-truncated'):_create_repair_variant(base,report,tmp_path/'repair.mid','Repair')