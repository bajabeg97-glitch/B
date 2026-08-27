import json
from pathlib import Path

import pytest

from tools.factory_data_bundle import create_factory_bundle,restore_factory_bundle,verify_factory_bundle


def _data(root):
    path=Path(root)/'pa800_optimizer'/'profiles'/'data';path.mkdir(parents=True)
    (path/'one.json').write_text(json.dumps({'profiles':[1,2,3]}),encoding='utf-8')
    (path/'two.csv').write_text('name,value\na,1\n',encoding='utf-8')
    return path


def test_factory_bundle_roundtrip_is_hash_verified_and_atomic(tmp_path):
    data=_data(tmp_path);bundle=tmp_path/'PA800_FACTORY_DATA_BUNDLE.zip';created=create_factory_bundle(tmp_path,bundle)
    assert created['files']==2 and verify_factory_bundle(bundle)['pass']
    (data/'one.json').write_bytes(b'');(data/'two.csv').unlink()
    restored=restore_factory_bundle(bundle,tmp_path)
    assert restored==['one.json','two.csv']
    assert json.loads((data/'one.json').read_text(encoding='utf-8'))['profiles']==[1,2,3]


def test_corrupt_factory_bundle_is_rejected_before_restore(tmp_path):
    data=_data(tmp_path);bundle=tmp_path/'PA800_FACTORY_DATA_BUNDLE.zip';create_factory_bundle(tmp_path,bundle);bundle.write_bytes(b'not-a-zip')
    assert not verify_factory_bundle(bundle)['pass']
    with pytest.raises(RuntimeError,match='Invalid Factory data bundle'):restore_factory_bundle(bundle,tmp_path)