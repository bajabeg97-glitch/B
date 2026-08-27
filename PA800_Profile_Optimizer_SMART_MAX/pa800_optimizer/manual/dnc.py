from __future__ import annotations
import json
from pathlib import Path

class DncManualRegistry:
    """Exact Pa800 DNC identities and documented behavior from OS 2.0 manuals.

    This registry is device knowledge, not Factory-pattern inference.
    """
    def __init__(self, path=None):
        path=Path(path or Path(__file__).resolve().parents[1]/'profiles/data/pa800_dnc_manual_registry_v1.json')
        self.data=json.loads(path.read_text(encoding='utf-8'))
        self.by_address={(x['msb'],x['lsb'],x['program']):x for x in self.data['sounds']}
        self.by_name={' '.join(x['name'].lower().split()):x for x in self.data['sounds']}
        self.controllers=self.data['controller_semantics']
        self.mechanics=self.data['generic_mechanics']
    def resolve(self, msb, lsb, program):
        return self.by_address.get((msb,lsb,program))
    def is_dnc(self, msb, lsb, program):
        return (msb,lsb,program) in self.by_address
    def controller_ccs(self):
        return {80,81,1,2,64}
    def state_semantics(self, profile, state):
        if not profile:return {}
        caps=set(profile.get('capabilities',[])); out={}
        if 'sc1' in caps: out['sc1_active']=int(state.get('cc80',0))>0
        if 'sc2' in caps: out['sc2_active']=int(state.get('cc81',0))>0
        if 'joystick_y_plus' in caps: out['y_plus_active']=int(state.get('cc1',0))>=64
        if 'joystick_y_minus' in caps: out['y_minus_active']=int(state.get('cc2',0))>=64
        if 'damper' in caps or 'damper_trigger' in caps or 'resonance_halo' in caps: out['damper_active']=int(state.get('cc64',0))>=64
        if 'aftertouch' in caps: out['aftertouch_active']=int(state.get('aftertouch',0))>=90
        return out