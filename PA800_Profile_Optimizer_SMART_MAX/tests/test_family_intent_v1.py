import mido

from pa800_optimizer.analysis.context import build_contexts
from pa800_optimizer.analysis.family_intent import analyze_family_intents,family_intent_digest,render_family_intent_summary
from pa800_optimizer.analysis.intent import classify_intents
from pa800_optimizer.analysis.musical_context import analyze_musical_context
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.profiles.registry import ProfileRegistry
from tools.evaluate_family_intent_stress import evaluate
from tools.instrument_intent_stress_midis import generate,generate_case


def _analyze(path):
    mid=mido.MidiFile(path);registry=ProfileRegistry();contexts=build_contexts(mid,registry,'song')
    for ctx in contexts.values():_profile,ctx.resolution_status=registry.resolve_identity(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.role)
    notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat);context=analyze_musical_context(mid,notes,contexts,'song')
    return mid,notes,analyze_family_intents(mid,notes,contexts,context)


def test_drum_model_separates_anchor_backbeat_fill_and_ghost(tmp_path):
    path=generate_case('DRM-001','positive',tmp_path/'drum.mid');mid,notes,report=_analyze(path);labels={row['label'] for row in report['note_intents']}
    assert {'KICK_ANCHOR','BACKBEAT_SNARE','GHOST_HIT_CANDIDATE'}<=labels
    assert report['summary']['classified_notes']==len(notes) and report['summary']['by_family']=={'DRUM_KIT':len(notes)}
    assert report['digest']==family_intent_digest(report) and mid.ticks_per_beat==192


def test_bass_model_labels_foundation_motion_without_rewriting_special_note(tmp_path):
    path=generate_case('BAS-005','positive',tmp_path/'bass.mid');_mid,_notes,report=_analyze(path);bass=[row for row in report['note_intents'] if row['family']=='BASS'];labels={row['label'] for row in bass}
    assert {'PASSING_TONE_CANDIDATE','REPEATED_OR_PEDAL_TONE'}&labels
    protected=[row for row in bass if row['note']==24]
    assert protected and 'LOW_VELOCITY_SPECIAL_CANDIDATE' in protected[0]['protected_dependencies'] and protected[0]['allowed_actions']==['ANALYZE','PRESERVE']


def test_guitar_model_preserves_ordered_strum_direction(tmp_path):
    positive=generate_case('GTR-001','positive',tmp_path/'strum.mid');negative=generate_case('GTR-001','negative',tmp_path/'line.mid');_m,_n,strum=_analyze(positive);_m,_n,line=_analyze(negative)
    assert set(strum['summary']['by_label'])=={'ORDERED_ASCENDING_STRUM_CANDIDATE'}
    assert 'SINGLE_NOTE_LINE' in line['summary']['by_label'] or 'RIFF_OSTINATO_TONE' in line['summary']['by_label']
    assert strum['digest']!=line['digest'] and all(row['automation_authority'] is False for row in strum['note_intents'])


def test_piano_model_tracks_chord_voice_arpeggio_and_damper_dependency(tmp_path):
    path=generate_case('PNO-002','positive',tmp_path/'piano.mid');_mid,_notes,report=_analyze(path);rows=report['note_intents']
    assert 'ARPEGGIATED_CHORD_TONE' in {row['label'] for row in rows}
    assert rows and all('CC64' in row['protected_dependencies'] for row in rows)
    assert all(row['allowed_actions']==['ANALYZE','PRESERVE'] for row in rows)


def test_family_stress_runs_all_38_real_smf_cases_and_19_pairs(tmp_path):
    generate(tmp_path);result=evaluate(tmp_path)
    assert result['pass'] and result['passed_cases']==38 and result['failed_cases']==0
    assert result['pair_separation_passed']==result['pair_separation_total']==19
    assert result['mutations']==0 and result['authority_granted'] is False


def test_optimizer_preserve_integrates_family_intent_without_byte_change(tmp_path):
    source=generate_case('GTR-001','positive',tmp_path/'source.mid');output=tmp_path/'output.mid';before=source.read_bytes();report=Optimizer(OptimizeConfig.for_mode('preserve')).optimize(source,output)
    assert output.read_bytes()==before and report.family_intent['schema']=='PA800_FAMILY_INTENT_V1'
    assert report.instrument_intent['family_models']['digest']==report.family_intent['digest']
    assert report.quality_gate['checks']['family_intent_v1_has_no_self_authority'] is True
    assert report.family_intent['automation']['applied_actions']==0 and 'Authority: analyzer-only' in render_family_intent_summary(report.family_intent)