"""Versioned physical-Pa800 evidence registry for E3 authority."""
from __future__ import annotations
import json
from pathlib import Path


def _address(value):
    if value is None:return None
    if isinstance(value,str):value=value.split('.')
    try:
        row=tuple(int(x) for x in value)
        return row if len(row)==3 and all(0<=x<=127 for x in row) else None
    except Exception:return None


class HardwareEvidenceRegistry:
    def __init__(self,path=None):
        self.path=str(path) if path else None;self.records=[];self.errors=[]
        if not path:return
        try:data=json.loads(Path(path).read_text(encoding='utf-8'))
        except Exception as exc:self.errors.append('load_error:'+repr(exc));return
        for index,row in enumerate(data.get('records',[])):
            if not isinstance(row,dict):self.errors.append('record_%d_not_object'%index);continue
            kind=str(row.get('kind','')).lower();approval=str(row.get('approval','suggest')).lower();target=_address(row.get('target_address'));source=_address(row.get('source_address'))
            if kind not in ('voice','articulation','fx'):self.errors.append('record_%d_invalid_kind'%index);continue
            if approval not in ('suggest','safe-auto','auto'):self.errors.append('record_%d_invalid_approval'%index);continue
            if kind=='voice' and not target:self.errors.append('record_%d_missing_target'%index);continue
            normalized=dict(row,kind=kind,approval=approval,source_address=source,target_address=target,aesthetic=str(row.get('aesthetic','any')).lower(),family=str(row.get('family','ANY')).upper(),evidence_level='E3')
            self.records.append(normalized)

    @property
    def available(self):return bool(self.records) and not self.errors

    def voice_approval(self,source,target,family,aesthetic):
        source=_address(source);target=_address(target);family=str(family or 'ANY').upper();aesthetic=str(aesthetic or 'original').lower()
        matches=[]
        for row in self.records:
            if row['kind']!='voice' or row['target_address']!=target:continue
            if row['source_address'] and row['source_address']!=source:continue
            if row['family'] not in ('ANY',family):continue
            if row['aesthetic'] not in ('any',aesthetic):continue
            matches.append(row)
        if not matches:return None
        rank={'suggest':0,'safe-auto':1,'auto':2};return max(matches,key=lambda row:rank[row['approval']])

    def articulation_approval(self,address,control,semantic):
        address=_address(address);semantic=str(semantic or '').lower()
        matches=[]
        for row in self.records:
            if row['kind']!='articulation':continue
            if row.get('source_address') not in (None,address):continue
            if row.get('control') is not None and int(row['control'])!=int(control):continue
            if row.get('semantic') and str(row['semantic']).lower()!=semantic:continue
            matches.append(row)
        if not matches:return None
        rank={'suggest':0,'safe-auto':1,'auto':2};return max(matches,key=lambda row:rank[row['approval']])

    def fx_approval(self,address,family,scope='section'):
        address=_address(address);family=str(family or 'ANY').upper();scope=str(scope or 'section').lower();matches=[]
        for row in self.records:
            if row['kind']!='fx':continue
            if row.get('source_address') not in (None,address):continue
            if row.get('family','ANY') not in ('ANY',family):continue
            if str(row.get('scope','any')).lower() not in ('any',scope):continue
            matches.append(row)
        if not matches:return None
        rank={'suggest':0,'safe-auto':1,'auto':2};return max(matches,key=lambda row:rank[row['approval']])

    def summary(self):
        return {'path':self.path,'records':len(self.records),'errors':self.errors,'available':self.available,'by_kind':{kind:sum(row['kind']==kind for row in self.records) for kind in ('voice','articulation','fx')}}