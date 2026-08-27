import struct
from pa800_optimizer.core.smf_preflight import preflight_smf


def valid_smf(track=b'\x00\xff\x2f\x00'):
    return b'MThd'+struct.pack('>IHHH',6,1,1,192)+b'MTrk'+struct.pack('>I',len(track))+track


def test_preflight_accepts_complete_container(tmp_path):
    path=tmp_path/'ok.mid';path.write_bytes(valid_smf());result=preflight_smf(path)
    assert result['pass'] and result['declared_tracks']==1 and result['tracks'][0]['status']=='READABLE'


def test_preflight_quarantines_truncated_track(tmp_path):
    path=tmp_path/'bad.mid';path.write_bytes(valid_smf()[:-2]);result=preflight_smf(path)
    assert not result['pass'] and result['tracks'][0]['status']=='QUARANTINED_TRUNCATED'


def test_preflight_rejects_track_count_mismatch(tmp_path):
    raw=bytearray(valid_smf());raw[10:12]=(2).to_bytes(2,'big');path=tmp_path/'count.mid';path.write_bytes(raw);result=preflight_smf(path)
    assert not result['pass'] and any('track_count_mismatch' in x for x in result['errors'])