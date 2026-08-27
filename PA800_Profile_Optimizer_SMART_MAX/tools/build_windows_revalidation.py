"""Build a clean Windows revalidation ZIP from canonical project sources."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
import tomllib
from pathlib import Path

try:from tools.factory_data_bundle import BUNDLE_NAME,create_factory_bundle,verify_factory_bundle
except ModuleNotFoundError:from factory_data_bundle import BUNDLE_NAME,create_factory_bundle,verify_factory_bundle


ROOT=Path(__file__).resolve().parents[1]
VERSION=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
DEFAULT_OUTPUT=ROOT.parent/('PA800_SMART_MAX_%s_PC_REVALIDATION.zip'%VERSION)
EXCLUDED_DIRS={'prism-uploads','validation_results','.venv','__pycache__','.pytest_cache','.git'}
REQUIRED_RELEASE_FILES={
    BUNDLE_NAME,
    'ENSURE_FACTORY_DATA.bat',
    'FIX_DATA_AND_RUN_GUI.bat',
    'RUN.bat',
    'RUN_AUTO_PILOT_GUI.bat',
    'CREATE_HARDWARE_CAMPAIGN.bat',
    'EVALUATE_HARDWARE_CAMPAIGN.bat',
    'PA800_HARDWARE_CAMPAIGN/CAMPAIGN.json',
    'PA800_HARDWARE_CAMPAIGN/RESULTS.csv',
    'PA800_HARDWARE_CAMPAIGN/READ_ME_FIRST.txt',
    'pa800_optimizer/profiles/data/factory_sound_profiles_v1.json',
    'pa800_optimizer/profiles/data/factory_drum_key_profiles_v1.json',
    'pa800_optimizer/profiles/data/factory_velocity_semantics_v2.json',
    'pa800_optimizer/profiles/data/factory_atomic_max_summary.json',
    'pa800_optimizer/profiles/data/factory_profile_stability_v1.json',
    'pa800_optimizer/profiles/data/factory_profile_completeness_v1.json',
    'pa800_optimizer/profiles/data/exact_instrument_neural_profiles_v1.json',
}

FACTORY_DATA_MARKER='pa800_optimizer/profiles/data/'
SOURCE_FACTORY_FILES={
    'factory_sound_profiles_v1.json','factory_drum_key_profiles_v1.json','factory_drum_key_profiles_v1.csv',
    'factory_velocity_semantics_v2.json','factory_profile_stability_v1.json','factory_element_profile_stability_v1.json',
    'factory_atomic_max_summary.json','factory_control_forensics_max.json','factory_controller_profiles.json',
    'factory_arranger_atoms_v1.json','factory_technique_candidates_max.csv','factory_analysis_coverage_max.csv',
    'pa800_dnc_manual_registry_v1.json',
}


def _excluded(relative):
    return any(part in EXCLUDED_DIRS for part in relative.parts) or relative.suffix=='.pyc'


def _validate_stage(stage):
    """Reject a release that cannot start or has empty/corrupt Factory data."""
    errors=[]
    for relative in sorted(REQUIRED_RELEASE_FILES):
        path=stage/relative
        if not path.is_file():
            errors.append('missing '+relative)
            continue
        if path.stat().st_size==0:
            errors.append('empty '+relative)
            continue
        if path.suffix.lower()=='.json':
            try:json.loads(path.read_text(encoding='utf-8'))
            except (UnicodeDecodeError,json.JSONDecodeError) as exc:
                errors.append('invalid_json %s: %s'%(relative,exc))
    if errors:
        raise RuntimeError('Invalid Windows release payload:\n'+'\n'.join(errors))
    bundle_check=verify_factory_bundle(stage/BUNDLE_NAME)
    if not bundle_check['pass']:raise RuntimeError('Invalid embedded Factory bundle: %s'%bundle_check['errors'])


def _factory_data_ready(stage):
    for relative in REQUIRED_RELEASE_FILES:
        if not relative.startswith(FACTORY_DATA_MARKER):continue
        path=stage/relative
        if not path.is_file() or path.stat().st_size==0:return False
        try:json.loads(path.read_text(encoding='utf-8'))
        except Exception:return False
    return True


def _zip_has_complete_factory_data(candidate):
    available={Path(name).name for name in candidate.namelist() if FACTORY_DATA_MARKER in name.replace('\\','/') and not name.endswith('/') and candidate.getinfo(name).file_size>0}
    return SOURCE_FACTORY_FILES<=available


def _archive_has_factory_data(archive):
    try:
        with zipfile.ZipFile(archive) as candidate:
            return _zip_has_complete_factory_data(candidate)
    except (OSError,zipfile.BadZipFile):return False


def _candidate_archives(explicit=None):
    raw=[]
    if explicit:raw.append(Path(explicit))
    if os.environ.get('PA800_FACTORY_ARCHIVE'):raw.append(Path(os.environ['PA800_FACTORY_ARCHIVE']))
    places=[ROOT,ROOT.parent,ROOT.parent/'prism-uploads',ROOT.parents[1]/'prism-uploads']
    raw.extend(path for place in places if place.exists() for path in place.glob('*.zip'))
    seen=set();result=[]
    for path in raw:
        try:key=str(path.resolve()).lower()
        except OSError:continue
        if key not in seen and path.is_file():seen.add(key);result.append(path)
    return result


def _usable_factory_archive(candidate,temp_dir):
    if _archive_has_factory_data(candidate):return candidate
    try:
        with zipfile.ZipFile(candidate) as outer:
            nested=sorted((name for name in outer.namelist() if name.lower().endswith('.zip')),key=lambda name:(not any(token in name.upper() for token in ('SMART_SOUND_KIT_FX_FULL','FACTORY_ATOMIC','SMART_MAX')),name))
            for index,name in enumerate(nested):
                try:
                    payload=outer.read(name)
                    with zipfile.ZipFile(io.BytesIO(payload)) as inner:
                        if not _zip_has_complete_factory_data(inner):continue
                    target=Path(temp_dir)/('factory-source-%d.zip'%index);target.write_bytes(payload);return target
                except (KeyError,zipfile.BadZipFile,OSError):continue
    except (OSError,zipfile.BadZipFile):pass
    return None


def _hydrate_stage(stage,factory_archive,temp_dir):
    if _factory_data_ready(stage):return None
    usable=None
    for candidate in _candidate_archives(factory_archive):
        usable=_usable_factory_archive(candidate,temp_dir)
        if usable:break
    if usable is None:raise RuntimeError('Factory data placeholders are empty and no valid full-source archive was found. Pass --factory-archive.')
    env={**os.environ,'PYTHONPATH':str(stage)+(os.pathsep+os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '')}
    command=[sys.executable,str(stage/'tools'/'repair_profile_data.py'),'--archive',str(usable)]
    result=subprocess.run(command,cwd=stage,env=env,capture_output=True,text=True)
    if result.returncode or not _factory_data_ready(stage):raise RuntimeError('Staged Factory restore failed:\n'+result.stdout+result.stderr)
    return str(usable)


def build(output=DEFAULT_OUTPUT,factory_archive=None):
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pa800-release-') as tmp:
        stage=Path(tmp)/ROOT.name
        for source in ROOT.rglob('*'):
            relative=source.relative_to(ROOT)
            if _excluded(relative) or not source.is_file():continue
            target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        for source in stage.glob('*.bat.tex'):
            shutil.copy2(source,source.with_suffix(''))
        ci=stage/'CI_RELEASE_MATRIX.yml'
        if ci.is_file():
            target=stage/'.github'/'workflows'/'release.yml';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ci,target)
        restored_from=_hydrate_stage(stage,factory_archive,tmp)
        bundle=create_factory_bundle(stage,stage/BUNDLE_NAME);bundle={**bundle,'path':BUNDLE_NAME}
        _validate_stage(stage)
        if output.exists():output.unlink()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(stage.rglob('*')):
                if source.is_file():archive.write(source,source.relative_to(stage.parent).as_posix())
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    result={'path':str(output),'bytes':output.stat().st_size,'sha256':digest,'factory_bundle':bundle,'factory_restored_from':restored_from}
    print(json.dumps(result,indent=2));return result


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(DEFAULT_OUTPUT));ap.add_argument('--factory-archive');ns=ap.parse_args(argv)
    build(ns.output,ns.factory_archive);return 0


if __name__=='__main__':raise SystemExit(main())