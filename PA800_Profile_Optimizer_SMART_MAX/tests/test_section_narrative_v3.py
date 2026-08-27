import mido

from pa800_optimizer.analysis.musical_context import analyze_musical_context
from pa800_optimizer.analysis.section_narrative import analyze_section_narrative
from pa800_optimizer.analysis.section_narrative import render_section_narrative_summary,section_narrative_digest
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.models import NoteEvent
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.understanding_cli import analyze_file
from tools.evaluate_section_narrative_stress import evaluate
from tools.section_narrative_stress_midis import generate,generate_case


def _report(tmp_path,identifier,polarity='positive',content_type='song'):
    path=generate_case(identifier,polarity,tmp_path/f'{identifier}_{polarity}.mid')
    return path,analyze_file(path,content_type)['section_narrative']


def test_explicit_song_marker_is_e2_and_digest_is_stable(tmp_path):
    path,report=_report(tmp_path,'SEC3-001');second=analyze_file(path,'song')['section_narrative']
    assert any(row['label']=='CHORUS' and row['evidence_level']=='E2' for row in report['sections'])
    assert report['digest']==second['digest']==section_narrative_digest(report)
    assert report['authority_granted'] is False and report['mutations']==0


def test_velocity_only_loudness_is_rejected_as_section_boundary(tmp_path):
    _path,report=_report(tmp_path,'SEC3-010')
    assert report['summary']['sections']==1 and report['summary']['accepted_boundaries']==0
    assert report['summary']['rejected_velocity_only']>=1
    assert any(row['reason']=='VELOCITY_ONLY_REJECTED' for row in report['boundary_evidence'])


def test_layer_growth_is_build_but_dense_unique_bar_is_not_chorus(tmp_path):
    _path,build=_report(tmp_path,'SEC3-002');_path,accidental=_report(tmp_path,'SEC3-003','negative')
    assert 'BUILD' in {row['relationship'] for row in build['transitions']}
    assert 'CHORUS_CANDIDATE' not in {row['label'] for row in accidental['sections']}
    _path,repeated=_report(tmp_path,'SEC3-003','positive')
    assert sum(row['label']=='CHORUS_CANDIDATE' for row in repeated['sections'])>=2


def test_one_bar_break_and_boundary_overlap_are_preserved(tmp_path):
    _path,break_report=_report(tmp_path,'SEC3-004');_path,overlap=_report(tmp_path,'SEC3-006')
    assert 'BREAK_CANDIDATE' in {row['label'] for row in break_report['sections']}
    assert overlap['summary']['overlap_boundaries']==1
    assert overlap['boundary_overlaps'][0]['policy']=='PRESERVE_OVERLAP_DO_NOT_HARD_SPLIT'


def test_style_element_cv_remains_serialized_e2(tmp_path):
    _path,report=_report(tmp_path,'SEC3-012','positive','style')
    assert report['method']=='SERIALIZED_STYLE_ELEMENT_CV'
    assert report['summary']['explicit_sections']==2 and report['summary']['inferred_sections']==0
    assert all(row['evidence_level']=='E2' for row in report['sections'])


def test_all_24_real_smf_cases_and_12_adversarial_pairs_pass(tmp_path):
    generate(tmp_path);result=evaluate(tmp_path)
    assert result['pass'] and result['passed_cases']==24 and result['failed_cases']==0
    assert result['pair_separation_passed']==result['pair_separation_total']==12
    assert result['mutations']==0 and result['authority_granted'] is False


def test_optimizer_preserve_integrates_section_v3_without_byte_change(tmp_path):
    source=generate_case('SEC3-006','positive',tmp_path/'source.mid');output=tmp_path/'output.mid';before=source.read_bytes();report=Optimizer(OptimizeConfig.for_mode('preserve')).optimize(source,output)
    assert output.read_bytes()==before and report.section_narrative['schema']=='PA800_SECTION_NARRATIVE_V3'
    assert report.instrument_intent['section_model']['digest']==report.section_narrative['digest']
    assert report.quality_gate['checks']['section_narrative_v3_has_no_self_authority'] is True
    assert report.section_narrative['automation']['applied_actions']==0
    assert 'Authority: analyzer-only' in render_section_narrative_summary(report.section_narrative)


def test_song_bars_follow_serialized_time_signature_changes():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0),mido.MetaMessage('time_signature',numerator=3,denominator=4,time=1536)])
    notes=[NoteEvent(0,0,60,80,0,2688,0,1)]
    context=analyze_musical_context(mid,notes,{},'song');report=analyze_section_narrative(mid,notes,{},context)
    assert [(row['start_tick'],row['end_tick']) for row in report['bars']]==[(0,768),(768,1536),(1536,2112),(2112,2688)]
    assert [(row['numerator'],row['denominator']) for row in report['meter']['changes']]==[(4,4),(3,4)]
    assert context['section_basis']['bar_count']==4