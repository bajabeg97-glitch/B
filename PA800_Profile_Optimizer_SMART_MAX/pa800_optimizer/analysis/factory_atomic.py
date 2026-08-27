from __future__ import annotations
import csv, json
from pathlib import Path

class FactoryAtomicKnowledge:
    """Read-only access to the Factory ATOMIC MAX research layer.

    This is empirical arranger knowledge. It must never be interpreted as an
    undocumented RX/DNC oscillator mapping.
    """
    def __init__(self, data_dir=None):
        self.data_dir=Path(data_dir or Path(__file__).resolve().parents[1]/'profiles/data')
        self.load_errors=[]
        sp=self.data_dir/'factory_atomic_max_summary.json'
        cp=self.data_dir/'factory_control_forensics_max.json'
        self.summary=self._safe_json(sp)
        self.controls=self._safe_json(cp)
        self.techniques=[]
        tp=self.data_dir/'factory_technique_candidates_max.csv'
        if tp.exists() and tp.stat().st_size:
            try:
                with tp.open(encoding='utf-8-sig',newline='') as f:self.techniques=list(csv.DictReader(f))
            except Exception as exc:self.load_errors.append('%s: %s' % (tp.name,exc))
    def _safe_json(self,path):
        if not path.exists() or path.stat().st_size==0:
            self.load_errors.append('%s: missing_or_empty' % path.name);return {}
        try:return json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:self.load_errors.append('%s: %s' % (path.name,exc));return {}
    @property
    def available(self):return bool(self.summary)
    def corpus(self):
        return {'styles':self.summary.get('styles',0),'notes':self.summary.get('records',0),'segments':self.summary.get('segments',0)}
    def element(self,name):return (self.summary.get('element_stats') or {}).get(name)
    def variation_progression(self,transition,role):
        return (self.summary.get('variation_progression_summary') or {}).get(f'{transition}|{role}')
    def cross_role(self,element,role_a,role_b):
        return (self.summary.get('cross_role_summary') or {}).get(f'{element}|{role_a}|{role_b}')
    def controller_count(self,cc):return int((self.controls.get('global_counts') or {}).get(f'cc:{int(cc)}',0))
    def pitchbend_count(self):return int((self.controls.get('global_counts') or {}).get('pb',0))
    def techniques_for(self,family=None,role=None,element=None):
        out=[]
        for r in self.techniques:
            if family and r.get('family')!=family:continue
            if role and r.get('role')!=role:continue
            if element and r.get('element')!=element:continue
            out.append(r)
        return out