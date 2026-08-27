import copy
import json
from pathlib import Path

import mido

from pa800_optimizer.analysis.context import build_contexts
from pa800_optimizer.analysis.intent import classify_intents
from pa800_optimizer.analysis.instrument_intent import analyze_instrument_intent,intent_digest,render_intent_summary
from pa800_optimizer.analysis.musical_context import analyze_musical_context
from pa800_optimizer.analysis.musical_understanding import analyze_musical_understanding
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.profiles.registry import ProfileRegistry
from tools.instrument_intent_stress_midis import generate
from tools.evaluate_instrument_intent_stress import evaluate


def _track(name,channel,program,notes,msb=0,lsb=0,controller=None):
    track=mido.MidiTrack();track.extend([mido.MetaMessage('track_name',name=name,time=0),mido.Message('control_change',channel=channel,control=0,value=msb,time=0),mido.Message('control_change',channel=channel,control=32,value=lsb,time=0),mido.Message('program_change',channel=channel,program=program,time=0)])
    if controller is not None:track.append(mido.Message('control_change',channel=channel,control=controller,value=100,time=0))
    for index,(pitch,velocity) in enumerate(notes):track.extend([mido.Message('note_on',channel=channel,note=pitch,velocity=velocity,time=0 if index==0 else 24),mido.Message('note_off',channel=channel,note=pitch,velocity=0,time=72)])
    return track


def _analyze(mid):
    registry=ProfileRegistry();contexts=build_contexts(mid,registry,'song')
    for ctx in contexts.values():_profile,ctx.resolution_status=registry.resolve_identity(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.role)
    notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat);context=analyze_musical_context(mid,notes,contexts,'song');understanding=analyze_musical_understanding(mid,notes,contexts,context)
    return analyze_instrument_intent(mid,notes,contexts,context,understanding),notes


def test_intent_v3_attributes_every_note_and_is_deterministic_analyzer_only():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.append(_track('Lead Melody',0,73,[(72,70),(74,76),(76,82),(79,88),(81,84)]));mid.tracks.append(_track('Bass',1,33,[(36,72),(36,74),(38,76),(40,78)],msb=121))
    before=[[msg.dict() for msg in track] for track in mid.tracks];first,notes=_analyze(mid);second,_=_analyze(mid)
    assert first['schema']=='PA800_INSTRUMENT_INTENT_V3' and first['analyzer_only'] and not first['authority_granted'] and first['mutations']==0
    assert first['summary']['notes']==len(notes)==len(first['note_intents']) and first['summary']['event_attribution_percent']==100
    assert first['intent_digest']==second['intent_digest']==intent_digest(first)
    assert len({row['intent_id'] for level in ('track_intents','phrase_intents','note_intents','section_intents','ensemble_intents') for row in first[level]})==sum(len(first[level]) for level in ('track_intents','phrase_intents','note_intents','section_intents','ensemble_intents'))
    assert first['automation']['applied_actions']==0 and [[msg.dict() for msg in track] for track in mid.tracks]==before
    assert 'authority: analyzer-only' in render_intent_summary(first)


def test_sparse_or_expressive_evidence_fails_closed():
    sparse=mido.MidiFile(type=1,ticks_per_beat=192);sparse.tracks.append(_track('Mystery',0,0,[(60,64)]));report,_=_analyze(sparse);row=report['track_intents'][0]
    assert row['label']=='UNKNOWN' and row['evidence_level']=='E0' and row['allowed_actions']==['ANALYZE','REQUEST_GROUND_TRUTH']
    expressive=mido.MidiFile(type=1,ticks_per_beat=192);expressive.tracks.append(_track('Solo Brass',0,56,[(60,70),(62,76),(64,82),(67,88)],msb=121,controller=1));report,_=_analyze(expressive);row=report['track_intents'][0]
    assert 'CC1' in row['protected_dependencies'] and row['automation_authority'] is False


def test_canonical_intent_stress_generator_creates_55_pairs_of_real_smf(tmp_path):
    manifest=generate(tmp_path);assert manifest['scenario_count']==55 and manifest['midi_case_count']==110 and manifest['positive_cases']==manifest['negative_cases']==55
    files=sorted(tmp_path.glob('*.mid'));assert len(files)==110 and len({row['sha256'] for row in manifest['cases']})==110
    pairs={}
    for row in manifest['cases']:
        mid=mido.MidiFile(tmp_path/row['file']);assert mid.tracks and extract_notes(mid)
        pairs.setdefault(row['scenario_id'],{})[row['polarity']]=row['sha256']
        assert row['expected_mutations']==0 and row['expected_authority'] is False
    assert len(pairs)==55 and all(value['positive']!=value['negative'] for value in pairs.values())
    stored=json.loads((tmp_path/'INSTRUMENT_INTENT_STRESS_MANIFEST.json').read_text());assert stored['schema']=='PA800_INSTRUMENT_INTENT_STRESS_V1'


def test_full_intent_stress_corpus_is_deterministic_and_authority_free(tmp_path):
    generate(tmp_path);result=evaluate(tmp_path)
    assert result['pass'] and result['passed_cases']==110 and result['failed_cases']==0
    assert result['pair_separation_passed']==result['pair_separation_total']==55
    assert result['mutations']==0 and result['authority_granted'] is False
    assert all(row['pass'] and all(row['checks'].values()) for row in result['rows'])


def test_optimizer_report_and_quality_gate_include_intent_v3(tmp_path):
    source=tmp_path/'song.mid';output=tmp_path/'out.mid';mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.append(_track('Lead Melody',0,73,[(72,70),(74,76),(76,82),(79,88)]));mid.save(source);before=source.read_bytes()
    report=Optimizer(OptimizeConfig.for_mode('preserve')).optimize(source,output)
    assert output.read_bytes()==before and report.instrument_intent['schema']=='PA800_INSTRUMENT_INTENT_V3'
    assert report.quality_gate['checks']['instrument_intent_v3_has_no_self_authority'] is True
    assert 'FAMILY_INTENT' in report.workstation['phase_contract'] and 'INSTRUMENT_INTENT' in report.workstation['phase_contract'] and report.instrument_intent['automation']['applied_actions']==0