import csv
from pathlib import Path

from tests.helpers import make_mid
from tools.pc_validation import create_support_archive,release_test_command,validate_user_midis


def test_user_validation_creates_persistent_single_pass_ab_pack(tmp_path):
    source=tmp_path/'source';source.mkdir();make_mid(str(source/'song.mid'),msb=121,lsb=3,program=0,channel=0)
    work=tmp_path/'result';work.mkdir();result=validate_user_midis(str(source),work,10)
    assert result['pass'] is True
    ab=work/'PA800_AB_PACK'
    assert len(list((ab/'01_ORIGINAL').glob('*.mid')))==1
    assert len(list((ab/'02_OPTIMIZED').glob('*.mid')))==1
    assert len(list((ab/'03_REPORTS').glob('*.json')))==1
    rows=list(csv.DictReader((ab/'PA800_AB_SCORE_SHEET.csv').open(encoding='utf-8-sig')))
    assert len(rows)==1 and rows[0]['pass']=='True'
    assert (ab/'PA800_AB_MANIFEST.json').exists()


def test_release_test_manifest_lists_every_current_test_module():
    command=release_test_command('isolated_pytest_tmp')
    root=Path(__file__).resolve().parents[1]
    expected={str(path.relative_to(root)).replace('\\','/') for path in (root/'tests').glob('test_*.py')}
    listed={item for item in command if str(item).startswith('tests/test_')}
    assert listed==expected
    assert '--basetemp' in command and 'isolated_pytest_tmp' in command


def test_missing_user_folder_is_not_a_pass():
    result=validate_user_midis(None,Path('.'),10)
    assert result=={'requested':False}


def test_support_archive_excludes_private_midi_content_by_default(tmp_path):
    out=tmp_path/'result';private=out/'PA800_AB_PACK'/'01_ORIGINAL';private.mkdir(parents=True)
    (private/'song.mid').write_bytes(b'private-midi');(out/'PC_VALIDATION_SUMMARY.txt').write_text('safe',encoding='utf-8')
    archive=create_support_archive(out,tmp_path/'send')
    import zipfile
    with zipfile.ZipFile(archive) as z:names=z.namelist()
    assert 'PC_VALIDATION_SUMMARY.txt' in names
    assert not any(name.endswith('.mid') for name in names)


def test_support_archive_requires_explicit_private_opt_in(tmp_path):
    out=tmp_path/'result';private=out/'PA800_AB_PACK'/'01_ORIGINAL';private.mkdir(parents=True)
    (private/'song.mid').write_bytes(b'private-midi')
    archive=create_support_archive(out,tmp_path/'send_full',include_private_midis=True)
    import zipfile
    with zipfile.ZipFile(archive) as z:assert 'PA800_AB_PACK/01_ORIGINAL/song.mid' in z.namelist()