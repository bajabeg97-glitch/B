import os,subprocess,sys
from importlib.resources import files
from pathlib import Path

import pytest


def test_runtime_profile_package_data_present():
    data=files('pa800_optimizer.profiles').joinpath('data')
    assert data.joinpath('factory_sound_profiles_v1.json').is_file()
    assert data.joinpath('factory_velocity_semantics_v2.json').is_file()
    assert data.joinpath('factory_profile_stability_v1.json').is_file()


def test_release_audit_passes():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'tools'/'release_audit.py')],cwd=root,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_build_identity_covers_release_authority_files():
    from tools.build_identity import stable_payload
    paths={row['path'] for row in stable_payload()['release_authority_files']}
    assert {'tools/pc_validation.py','tools/build_windows_revalidation.py','tools/clean_install_smoke.py','tools/sync_ci_workflow.py','tests/test_optimizer.py','test_support/mido.py','RELEASE_TESTS.txt','VALIDATE_ON_PC.bat','RUN_GUI.bat','INSTALL.bat','constraints-core.txt','constraints-validation.txt','CI_RELEASE_MATRIX.yml'}<=paths


def test_release_constraints_and_python_matrix_are_explicit():
    root=Path(__file__).resolve().parents[1]
    core=(root/'constraints-core.txt').read_text(encoding='utf-8');validation=(root/'constraints-validation.txt').read_text(encoding='utf-8');workflow=(root/'CI_RELEASE_MATRIX.yml').read_text(encoding='utf-8')
    assert 'mido==1.3.3' in core
    assert {'pytest==9.1.1','build==1.5.0','setuptools==84.0.0','wheel==0.46.1'}<=set(line.strip() for line in validation.splitlines())
    for version in ('3.10','3.11','3.12','3.13','3.14'):assert "'"+version+"'" in workflow
    assert 'tools/clean_install_smoke.py' in workflow
    assert 'tools/run_complete_stress.py' in workflow


def test_windows_release_builder_creates_bat_and_excludes_private_uploads(tmp_path):
    from tools.build_windows_revalidation import build
    import zipfile
    archive=build(tmp_path/'release.zip')['path']
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        sound_profile=next(name for name in names if name.endswith('/pa800_optimizer/profiles/data/factory_sound_profiles_v1.json'))
    assert any(name.endswith('/VALIDATE_ON_PC.bat') for name in names)
    assert any(name.endswith('/ENSURE_VALIDATION_DEPS.bat') for name in names)
    assert any(name.endswith('/FIX_DATA_AND_RUN_GUI.bat') for name in names)
    assert any(name.endswith('/ENSURE_FACTORY_DATA.bat') for name in names)
    assert any(name.endswith('/PA800_FACTORY_DATA_BUNDLE.zip') and z.getinfo(name).file_size>0 for name in names)
    assert not any(name.endswith('/TRAIN_NEURAL_ENCODER.bat') for name in names)
    assert any(name.endswith('/.github/workflows/release.yml') for name in names)
    assert z.getinfo(sound_profile).file_size>0
    assert not any('/prism-uploads/' in name for name in names)


def test_windows_release_builder_rejects_empty_factory_payload(tmp_path):
    from tools.build_windows_revalidation import REQUIRED_RELEASE_FILES,_validate_stage
    for relative in REQUIRED_RELEASE_FILES:
        path=tmp_path/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('{}' if path.suffix=='.json' else '@echo off',encoding='utf-8')
    (tmp_path/'pa800_optimizer/profiles/data/factory_sound_profiles_v1.json').write_bytes(b'')
    with pytest.raises(RuntimeError,match='empty pa800_optimizer/profiles/data/factory_sound_profiles_v1.json'):
        _validate_stage(tmp_path)


def test_embedded_factory_bundle_restores_empty_runtime_data_without_external_zip(tmp_path):
    from tools.build_windows_revalidation import build
    import zipfile
    archive=build(tmp_path/'release.zip')['path'];install=tmp_path/'install'
    with zipfile.ZipFile(archive) as package:package.extractall(install)
    root=next(path for path in install.iterdir() if path.is_dir());victim=root/'pa800_optimizer'/'profiles'/'data'/'factory_sound_profiles_v1.json';victim.write_bytes(b'')
    env={**os.environ,'PYTHONPATH':str(root)}
    repaired=subprocess.run([sys.executable,str(root/'tools'/'repair_profile_data.py')],cwd=root,env=env,capture_output=True,text=True)
    assert repaired.returncode==0,repaired.stdout+repaired.stderr
    assert victim.stat().st_size>0
    audited=subprocess.run([sys.executable,str(root/'tools'/'release_audit.py')],cwd=root,env=env,capture_output=True,text=True)
    assert audited.returncode==0,audited.stdout+audited.stderr


def test_recorded_build_identity_matches_current_authority_tree():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'tools'/'build_identity.py'),'--check'],cwd=root,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
