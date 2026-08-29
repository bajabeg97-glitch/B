from core.models import MidiTrack, create_note_on
from core.velocity_models import ArticulationType, VelocityCurve
from engine.factory_velocity_engine import FactoryVelocityEngine
from engine.gold_velocity_engine import GoldVelocityEngine
from engine.unified_velocity_engine import UnifiedVelocityEngine


def _track_with_notes(velocities):
    track = MidiTrack(name="Piano", channel=0)
    tick = 0
    for vel in velocities:
        track.add_event(create_note_on(60, vel, tick))
        tick += 480
    return track


def test_factory_articulation_and_limits():
    engine = FactoryVelocityEngine()
    art_map = engine.create_articulation_map("piano", 0)
    assert art_map.get_articulation(20) == ArticulationType.GHOST
    assert art_map.get_articulation(110) == ArticulationType.MARCATO
    assert engine.apply_hard_limiting(3) == 10
    assert engine.apply_hard_limiting(127) == 120
    assert engine.validate_release_velocity(100, None) == 60
    assert engine.validate_release_velocity(80, 100) == int(80 * 0.6)


def test_factory_process_and_profile():
    engine = FactoryVelocityEngine()
    track = _track_with_notes([20, 64, 110])
    notes = [e for e in track.events]
    profile = engine.analyze_track_profile(notes, "piano")
    assert profile.min_velocity == 20
    assert profile.max_velocity == 110
    assert 0 < profile.ghost_ratio < 1
    processed = engine.process_note(notes[0], engine.create_articulation_map("piano", 0))
    assert processed.articulation == ArticulationType.GHOST
    assert processed.original_velocity == 20


def test_unified_modes_and_report():
    engine = UnifiedVelocityEngine()
    engine.set_mode("FACTORY_ONLY")
    assert engine.blend_ratio == 0.0
    engine.set_mode("BALANCED")
    track = _track_with_notes([40, 80, 100, 110])
    engine.load_gold_reference("gold", track)
    results = engine.process_track(track, instrument_type="piano", gold_profile_name="gold")
    assert len(results) == 4
    report = engine.generate_velocity_report(results)
    assert report["total_notes"] == 4
    assert report["mode_used"] == "BALANCED"
    changed = engine.apply_processing_to_track(track, results)
    assert changed >= 0


def test_gold_blend_and_invalid_mode():
    factory = FactoryVelocityEngine()
    gold = GoldVelocityEngine()
    track = _track_with_notes([70, 80, 90])
    notes = list(track.events)
    gold.load_gold_profile("ref", notes)
    art = factory.create_articulation_map("piano", 0)
    fdata = factory.process_note(notes[0], art)
    gdata = gold.apply_phrase_contour(notes[0], "ref", 0.5)
    blended = gold.blend_factory_and_gold(fdata, gdata, 0.5)
    assert 1 <= blended.processed_velocity <= 127
    unified = UnifiedVelocityEngine()
    try:
        unified.set_mode("NOPE")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_velocity_curves_stay_in_range():
    for value in (1, 64, 127):
        assert 0 <= VelocityCurve.linear(value) <= 127
        assert 0 <= VelocityCurve.exponential(value) <= 127
        assert 0 <= VelocityCurve.logarithmic(value) <= 127
        assert 0 <= VelocityCurve.s_curve(value) <= 127
    assert VelocityCurve.custom_map(64, {0: 10, 127: 120}) >= 10
