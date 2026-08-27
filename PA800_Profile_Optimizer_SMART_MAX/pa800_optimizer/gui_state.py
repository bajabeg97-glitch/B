import json
import os
import re
import sys
import shutil
from datetime import datetime,timezone
from pathlib import Path

MIDI_EXTENSIONS = {'.mid', '.midi', '.kar'}


def build_training_command(project_root, training_folder, epochs=None,stamp=None,profile='MAX'):
    """Build the analyzer-training command used by the GUI worker."""
    root=Path(project_root);stamp=stamp or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f_UTC');candidate=root/'models'/'candidates'/('encoder_'+stamp+'.json')
    profile=str(profile).upper();settings={'BALANCED':(450,24,.35,.035),'MAX':(1200,48,.40,.025)};epochs_default,hidden,mask,rate=settings.get(profile,settings['MAX']);epochs=epochs_default if epochs is None else int(epochs)
    return [sys.executable,str(root/'tools'/'train_neural_encoder.py'),str(training_folder),'--output',str(candidate),'--epochs',str(epochs),'--hidden-size',str(hidden),'--mask-rate',str(mask),'--learning-rate',str(rate),'--training-profile',profile if profile in settings else 'MAX','--log-dir',str(root/'training_logs')]


def build_training_audit_command(project_root,training_folder):
    root=Path(project_root)
    # Audit does not save a model and deliberately does not target the active
    # filename, keeping this safe if the trainer is refactored later.
    return [sys.executable,str(root/'tools'/'train_neural_encoder.py'),str(training_folder),'--output',str(root/'models'/'candidates'/'AUDIT_ONLY.json'),'--log-dir',str(root/'training_logs'),'--audit-only']


def _activate_model_candidate(candidate,active):
    candidate=Path(candidate);active=Path(active);active.parent.mkdir(parents=True,exist_ok=True);temporary=active.with_suffix(active.suffix+'.candidate.tmp');shutil.copyfile(candidate,temporary);temporary.replace(active);return active


def _hardware_create_command(project_root,output_folder):
    root=Path(project_root);return [sys.executable,str(root/'tools'/'create_hardware_campaign.py'),'--output',str(output_folder)]


def _hardware_evaluate_commands(project_root,campaign_folder):
    root=Path(project_root);folder=Path(campaign_folder);evaluation=folder/'HARDWARE_EVALUATION.json';gate=folder/'FINAL_RELEASE_GATE.json'
    return ([sys.executable,str(root/'tools'/'evaluate_hardware_campaign.py'),str(folder/'CAMPAIGN.json'),str(folder/'RESULTS.csv'),'--output',str(evaluation)],[sys.executable,str(root/'tools'/'final_release_gate.py'),'--hardware-evaluation',str(evaluation),'--output',str(gate)],evaluation,gate)


def settings_path():
    """Per-user GUI settings; never stored inside the project ZIP/runtime folder."""
    base = os.environ.get('APPDATA')
    if base:
        return Path(base) / 'PA800_Profile_Optimizer' / 'gui_settings.json'
    return Path.home() / '.pa800_profile_optimizer' / 'gui_settings.json'


def load_settings(path=None):
    path = Path(path) if path else settings_path()
    defaults = {
        'input_dir': '',
        'output_dir': '',
        'mode': 'auto',
        'suffix': '_OPTIMIZED',
        'overwrite': False,
        'smart_mode': 'auto',
        'content_type': 'auto',
        'automation_version': 1,
        'midi_doctor': True,
        'velocity_conductor': True,
        'articulation_mode': 'suggest',
        'performance_mode': 'shadow',
        'safe_voice_upgrades': True,
        'voice_aesthetic': 'original',
        'hardware_evidence_path': '',
        'mix_fx_mode': 'auto',
        'export_preset': 'auto',
        'variant_label': 'optimized',
        'training_dir': '',
        'hardware_campaign_dir': '',
        'pattern_chords': 'C | Am | F | G7',
        'pattern_include_solo': True,
    }
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                defaults.update({k: data[k] for k in defaults if k in data})
                if int(data.get('automation_version',0) or 0)<1:
                    defaults['mode']='auto';defaults['smart_mode']='auto'
                if 'smart_mode' not in data and 'smart_sound_fx' in data:
                    defaults['smart_mode']='auto'
    except Exception:
        pass
    return defaults


def save_settings(data, path=None):
    path = Path(path) if path else settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        'input_dir': str(data.get('input_dir', '')),
        'output_dir': str(data.get('output_dir', '')),
        'mode': str(data.get('mode', 'auto')) if str(data.get('mode','auto')) in ('auto','preserve','natural','live','strong','max') else 'auto',
        'suffix': str(data.get('suffix', '_OPTIMIZED')),
        'overwrite': bool(data.get('overwrite', False)),
        'smart_mode': str(data.get('smart_mode', 'auto')) if str(data.get('smart_mode','auto')) in ('auto','off','suggest','apply') else 'auto',
        'content_type': str(data.get('content_type','auto')) if str(data.get('content_type','auto')) in ('auto','style','song') else 'auto',
        'automation_version': 1,
        'midi_doctor': bool(data.get('midi_doctor',True)),
        'velocity_conductor': bool(data.get('velocity_conductor',True)),
        'articulation_mode': str(data.get('articulation_mode','suggest')) if str(data.get('articulation_mode','suggest')) in ('off','suggest','apply') else 'suggest',
        'performance_mode': str(data.get('performance_mode','shadow')) if str(data.get('performance_mode','shadow')) in ('off','shadow','apply') else 'shadow',
        'safe_voice_upgrades': bool(data.get('safe_voice_upgrades',True)),
        'voice_aesthetic': str(data.get('voice_aesthetic','original')) if str(data.get('voice_aesthetic','original')) in ('original','natural','modern') else 'original',
        'hardware_evidence_path': str(data.get('hardware_evidence_path','')),
        'mix_fx_mode': str(data.get('mix_fx_mode','auto')) if str(data.get('mix_fx_mode','auto')) in ('auto','off','shadow','apply') else 'auto',
        'export_preset': str(data.get('export_preset','auto')) if str(data.get('export_preset','auto')) in ('auto','song','style','preserve') else 'auto',
        'variant_label': str(data.get('variant_label','optimized')),
        'training_dir': str(data.get('training_dir','')),
        'hardware_campaign_dir': str(data.get('hardware_campaign_dir','')),
        'pattern_chords': str(data.get('pattern_chords','C | Am | F | G7')),
        'pattern_include_solo': bool(data.get('pattern_include_solo',True)),
    }
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def list_midi_files(folder):
    p = Path(folder)
    if not p.is_dir():
        return []
    return sorted(
        [x for x in p.iterdir() if x.is_file() and x.suffix.lower() in MIDI_EXTENSIONS],
        key=lambda x: x.name.lower(),
    )


def output_path_for(input_path, output_dir, suffix='_OPTIMIZED'):
    inp = Path(input_path)
    out_dir = Path(output_dir)
    suffix = sanitize_suffix(suffix)
    source_tag={'midi':'_MIDI','kar':'_KAR'}.get(inp.suffix.lower().removeprefix('.'),'')
    return out_dir / (inp.stem + suffix + source_tag + '.mid')


def _effective_output_suffix(suffix,full_optimization_test=False):
    """Give explicit full-audition runs a non-colliding output identity."""
    value=sanitize_suffix(suffix)
    if full_optimization_test and not value.upper().endswith('_FULL_TEST'):
        value+='_FULL_TEST'
    return value


def sanitize_suffix(suffix):
    suffix='_OPTIMIZED' if suffix is None else str(suffix)
    suffix=re.sub(r'[^A-Za-z0-9._-]+','_',suffix).strip('.')
    return suffix or '_OPTIMIZED'
