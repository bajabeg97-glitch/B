"""Byte-level SMF container preflight before Mido constructs musical events."""
from __future__ import annotations

from pathlib import Path


def preflight_smf(path,allow_zero_division_repair=False):
    data=Path(path).read_bytes();errors=[];warnings=[];tracks=[]
    if len(data)<14:return {'pass':False,'errors':['truncated_mthd'],'warnings':[],'tracks':[],'bytes':len(data)}
    if data[:4]!=b'MThd':return {'pass':False,'errors':['missing_mthd'],'warnings':[],'tracks':[],'bytes':len(data)}
    header_length=int.from_bytes(data[4:8],'big')
    if header_length<6:errors.append('invalid_mthd_length')
    if 8+header_length>len(data):errors.append('truncated_mthd_payload')
    if errors:return {'pass':False,'errors':errors,'warnings':warnings,'tracks':tracks,'bytes':len(data)}
    fmt=int.from_bytes(data[8:10],'big');declared=int.from_bytes(data[10:12],'big');division=int.from_bytes(data[12:14],'big')
    if fmt not in (0,1,2):errors.append('unsupported_format_%d'%fmt)
    if division==0:
        if allow_zero_division_repair:warnings.append('zero_division_repair_required')
        else:errors.append('zero_division')
    if division&0x8000:errors.append('smpte_division_not_supported')
    pos=8+header_length;track_index=0
    while pos<len(data):
        if pos+8>len(data):errors.append('truncated_chunk_header_at_%d'%pos);break
        chunk=data[pos:pos+4];length=int.from_bytes(data[pos+4:pos+8],'big');body_start=pos+8;body_end=body_start+length
        if body_end>len(data):
            errors.append('truncated_%s_chunk_%d_declared_%d_available_%d'%(chunk.decode('latin1','replace'),track_index,length,max(0,len(data)-body_start)));tracks.append({'track':track_index,'declared_bytes':length,'available_bytes':max(0,len(data)-body_start),'status':'QUARANTINED_TRUNCATED'});break
        if chunk==b'MTrk':tracks.append({'track':track_index,'declared_bytes':length,'available_bytes':length,'status':'READABLE'});track_index+=1
        else:warnings.append('unknown_chunk_%r_preserved_by_strict_parser'%chunk)
        pos=body_end
    if track_index!=declared:errors.append('track_count_mismatch_declared_%d_found_%d'%(declared,track_index))
    if fmt==0 and declared!=1:errors.append('format0_requires_one_track')
    return {'pass':not errors,'errors':errors,'warnings':warnings,'tracks':tracks,'bytes':len(data),'format':fmt,'declared_tracks':declared,'division':division,'header_length':header_length}


def require_valid_smf(path,allow_zero_division_repair=False):
    result=preflight_smf(path,allow_zero_division_repair=allow_zero_division_repair)
    if not result['pass']:raise RuntimeError('UNRECOVERABLE_SMF_PREFLIGHT: '+', '.join(result['errors']))
    return result