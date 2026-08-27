from pathlib import Path
from pa800_optimizer.gui_state import _effective_output_suffix, list_midi_files, load_settings, output_path_for, save_settings, sanitize_suffix


def test_list_midi_files_and_output_name(tmp_path):
    (tmp_path / 'B.MID').write_bytes(b'')
    (tmp_path / 'a.kar').write_bytes(b'')
    (tmp_path / 'ignore.txt').write_text('x')
    names = [p.name for p in list_midi_files(tmp_path)]
    assert names == ['a.kar', 'B.MID']
    assert output_path_for(tmp_path/'a.kar', tmp_path/'out', '_OPTIMIZED').name == 'a_OPTIMIZED_KAR.mid'


def test_gui_settings_roundtrip(tmp_path):
    p = tmp_path / 'settings.json'
    save_settings({'input_dir':'IN','output_dir':'OUT','mode':'max','suffix':'_X','overwrite':True,'smart_mode':'apply','content_type':'song'}, p)
    s = load_settings(p)
    assert s['input_dir'] == 'IN'
    assert s['output_dir'] == 'OUT'
    assert s['mode'] == 'max'
    assert s['suffix'] == '_X'
    assert s['overwrite'] is True
    assert s['smart_mode'] == 'apply'
    assert s['content_type'] == 'song'


def test_suffix_is_path_safe():
    assert sanitize_suffix('../bad/name') == '_bad_name'


def test_full_optimization_uses_a_distinct_output_suffix():
    assert _effective_output_suffix('_OPTIMIZED',False)=='_OPTIMIZED'
    assert _effective_output_suffix('_OPTIMIZED',True)=='_OPTIMIZED_FULL_TEST'
    assert _effective_output_suffix('_FULL_TEST',True)=='_FULL_TEST'


def test_auto_pilot_gui_defaults(tmp_path):
    s=load_settings(tmp_path/'missing.json')
    assert s['mode']=='auto'
    assert s['smart_mode']=='auto'
    assert s['midi_doctor'] is True
    assert s['velocity_conductor'] is True
    assert s['articulation_mode']=='suggest'
    assert s['performance_mode']=='shadow'
    assert s['voice_aesthetic']=='original'
    assert s['hardware_evidence_path']==''
    assert s['mix_fx_mode']=='auto'
    assert s['export_preset']=='auto'
    assert s['variant_label']=='optimized'


def test_old_settings_are_migrated_to_auto_pilot(tmp_path):
    p=tmp_path/'settings.json'
    p.write_text('{"mode":"live","smart_mode":"suggest","input_dir":"IN"}',encoding='utf-8')
    s=load_settings(p)
    assert (s['mode'],s['smart_mode'])==('auto','auto')
    assert s['input_dir']=='IN'