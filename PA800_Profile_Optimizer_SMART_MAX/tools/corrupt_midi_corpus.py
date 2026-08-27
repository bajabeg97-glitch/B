"""Generate 80 deterministic MID/KAR container corruption fixtures."""
from __future__ import annotations
import json,struct
from pathlib import Path
from pa800_optimizer.core.smf_preflight import preflight_smf


def _base(body=None,fmt=1,tracks=1,division=192):
    body=body if body is not None else b'\x00\xff\x2f\x00'+b'X'*36
    return b'MThd'+struct.pack('>IHHH',6,fmt,tracks,division)+b'MTrk'+struct.pack('>I',len(body))+body


def generate(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);cases=[];base=_base()
    for cut in range(14):cases.append((f'truncated_header_{cut:02d}',base[:cut]))
    for missing in range(1,21):cases.append((f'truncated_track_payload_{missing:02d}',base[:-missing]))
    for count in range(2,10):cases.append((f'declared_track_count_{count:02d}',_base(tracks=count)))
    for fmt in range(3,8):cases.append((f'unsupported_format_{fmt:02d}',_base(fmt=fmt)))
    cases.extend([('zero_division',_base(division=0)),('smpte_division',_base(division=0xE728)),('format0_multiple_tracks',_base(fmt=0,tracks=2))])
    for index in range(10):
        damaged=bytearray(base);damaged[index%4]=(damaged[index%4]+index+1)%256;cases.append((f'kar_missing_magic_{index:02d}',bytes(damaged)))
    for length in range(6):
        damaged=bytearray(base);damaged[4:8]=length.to_bytes(4,'big');cases.append((f'invalid_header_length_{length:02d}',bytes(damaged)))
    for tail in range(1,8):cases.append((f'truncated_extra_chunk_header_{tail:02d}',base+b'JUNKDATA'[:tail]))
    for extra in range(1,8):
        damaged=bytearray(base);declared=int.from_bytes(damaged[18:22],'big');damaged[18:22]=(declared+extra).to_bytes(4,'big');cases.append((f'track_length_overclaim_{extra:02d}',bytes(damaged)))
    rows=[]
    for name,data in cases:
        extension='.kar' if name.startswith('kar_') else '.mid';path=output/(name+extension);path.write_bytes(data);result=preflight_smf(path);rows.append({'name':name,'file':path.name,'sha256':__import__('hashlib').sha256(data).hexdigest(),'pass':result['pass'],'errors':result['errors']})
    (output/'CORRUPT_MIDI_MANIFEST.json').write_text(json.dumps({'schema':'PA800_CORRUPT_MIDI_GOLDEN_V2','cases':rows},indent=2),encoding='utf-8');return rows


if __name__=='__main__':generate(Path(__file__).resolve().parents[1]/'corrupt_midi_golden')