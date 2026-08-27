import json, csv, statistics
from pathlib import Path
from collections import defaultdict
from ..manual import DncManualRegistry
from ..analysis.factory_atomic import FactoryAtomicKnowledge

class ProfileRegistry:
    _JSON_CACHE={}
    _INSTANCE_CACHE={}
    def __new__(cls,data_dir=None):
        key=str(Path(data_dir or Path(__file__).resolve().parent/'data').resolve())
        if key not in cls._INSTANCE_CACHE:cls._INSTANCE_CACHE[key]=super().__new__(cls)
        return cls._INSTANCE_CACHE[key]

    def __init__(self, data_dir=None):
        if getattr(self,'_initialized',False):return
        self.data_dir=Path(data_dir or Path(__file__).resolve().parent/'data')
        raw=self._required_json('factory_sound_profiles_v1.json')
        self.profiles=raw['profiles']
        self.by_address=defaultdict(list)
        self.by_family=defaultdict(list)
        for p in self.profiles:
            i=p['identity']; self.by_address[(i['msb'],i['lsb'],i['program'])].append(p); self.by_family[i.get('org_family','UNKNOWN')].append(p)
        self.velocity_family_profiles=self._build_velocity_family_profiles()
        dr=self._required_json('factory_drum_key_profiles_v1.json')
        self.drum_by_key={}
        for dp in dr.get('profiles',[]):
            k=dp['kit']; self.drum_by_key[(k['msb'],k['lsb'],k['program'],dp['key'])]=dp
        self.dnc_manual=DncManualRegistry()
        self.controller_by_address={}
        cprof=self.data_dir/'factory_controller_profiles.json'
        if cprof.exists() and cprof.stat().st_size:
            try:
                for row in json.loads(cprof.read_text(encoding='utf-8')):
                    key=(row.get('msb'),row.get('lsb'),row.get('program'))
                    old=self.controller_by_address.get(key)
                    if old is None or int(row.get('score',0))>int(old.get('score',0)):self.controller_by_address[key]=row
            except Exception:
                self.controller_by_address={}
        self.velocity_semantics_parent=None
        self.velocity_semantics_context=None
        self.velocity_semantics_path=self.data_dir/'factory_velocity_semantics_v2.json'
        self.factory_atomic=FactoryAtomicKnowledge(self.data_dir)
        self.stability={}
        sr=self._required_json('factory_profile_stability_v1.json')
        for row in sr.get('profiles',[]):
            i=row.get('identity',{})
            key=(i.get('msb'),i.get('lsb'),i.get('program'),self._norm_sound_name(i.get('sound')))
            self.stability[key]=row.get('stability','UNKNOWN')
        self.instrument_positive_models={}
        positive_path=self.data_dir/'instrument_family_positive_models_v1.json'
        if positive_path.exists() and positive_path.stat().st_size:
            positive=json.loads(positive_path.read_text(encoding='utf-8'))
            for row in positive.get('allowed',[]):
                address=tuple(row.get('address') or ())
                for model in row.get('models',[]):self.instrument_positive_models[(str(row.get('family')).upper(),address,str(model))]=row
        completeness=self._required_json('factory_profile_completeness_v1.json')
        self.profile_completeness_cards=completeness.get('cards',[])
        self.profile_completeness_by_key={};self.manual_only_profile_cards=[]
        for row in self.profile_completeness_cards:
            identity=row.get('identity',{});key=(identity.get('msb'),identity.get('lsb'),identity.get('program'),self._norm_sound_name(identity.get('sound')),identity.get('role'))
            self.profile_completeness_by_key[key]=row
            if row.get('origin')=='OFFICIAL_MANUAL_ONLY':self.manual_only_profile_cards.append(row)
        self.arranger_atoms={}
        ap=self.data_dir/'factory_arranger_atoms_v1.json'
        if ap.exists(): self.arranger_atoms=json.loads(ap.read_text(encoding='utf-8'))
        self.conflicts=set()
        cpath=self.data_dir/'factory_address_name_conflicts_v1.csv'
        if cpath.exists():
            with cpath.open(encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    try: self.conflicts.add((int(row['msb']),int(row['lsb']),int(row['program'])))
                    except Exception: pass
        self._initialized=True

    def _required_json(self,name):
        path=self.data_dir/name
        if not path.exists() or path.stat().st_size==0:
            raise RuntimeError('Factory profile %s is missing/empty. Run REPAIR_AND_VALIDATE.bat.' % name)
        key=(str(path.resolve()),path.stat().st_size,path.stat().st_mtime_ns)
        if key in self._JSON_CACHE:return self._JSON_CACHE[key]
        try:
            value=json.loads(path.read_text(encoding='utf-8'));self._JSON_CACHE[key]=value;return value
        except Exception as exc:raise RuntimeError('Factory profile %s is invalid (%s). Run REPAIR_AND_VALIDATE.bat.' % (name,exc)) from exc

    @staticmethod
    def _norm_sound_name(name):
        return ' '.join((name or '').strip().lower().split())

    @staticmethod
    def _velocity_family(identity):
        family=str(identity.get('org_family','UNKNOWN')).upper();name=str(identity.get('sound','')).lower()
        if family=='ACCORDION_REED':
            if 'harmonica' in name:return 'HARMONICA'
            if any(x in name for x in ('accordion','musette','bandoneon','bayan')):return 'ACCORDION'
            return 'REED'
        return family

    def _build_velocity_family_profiles(self):
        fields=('p05','working_min','ideal_min','ideal_center','ideal_max','working_max','p95');buckets=defaultdict(lambda:defaultdict(list))
        for profile in self.profiles:
            support=profile.get('support',{});velocity=profile.get('velocity') or {}
            if support.get('grade') not in ('STRONG','GOOD') or not velocity:continue
            identity=profile.get('identity',{});family=self._velocity_family(identity);role=identity.get('role');weight=max(1,min(10,int(support.get('styles',1))))
            for key in ((family,None),(family,role)):
                for field in fields:
                    if velocity.get(field) is not None:buckets[key][field].extend([float(velocity[field])]*weight)
        result={}
        for key,values in buckets.items():
            result[key]={'velocity':{field:round(statistics.median(vals),3) for field,vals in values.items() if vals},'_velocity_basis':'FACTORY_FAMILY_AGGREGATE'}
        return result

    def velocity_family_profile(self,family,role=None):
        family=str(family or 'UNKNOWN').upper()
        return self.velocity_family_profiles.get((family,role)) or self.velocity_family_profiles.get((family,None))

    def resolve_identity_with_name(self, msb, lsb, program, sound_name=None, role=None):
        """Resolve exact address, using an explicit Factory-export Sound label to
        disambiguate address/name conflicts.  This is not heuristic guessing: a
        supplied name must exactly match (case/whitespace normalized) a profile
        name at the same address.
        """
        addr=(msb,lsb,program)
        lst=self.by_address.get(addr,[])
        if not lst:
            return None, 'NO_EXACT_PROFILE'
        n=self._norm_sound_name(sound_name)
        if n:
            named=[p for p in lst if self._norm_sound_name(p['identity'].get('sound'))==n]
            if role and len(named)>1:
                rr=[p for p in named if p['identity'].get('role')==role or role in dict(p.get('roles',[]))]
                if rr: named=rr
            if named:
                named=sorted(named,key=lambda p:(p['support'].get('styles',0),p['support'].get('notes',0)),reverse=True)
                return named[0], 'EXACT_ADDRESS_NAME'
        return self.resolve_identity(msb,lsb,program,role)

    def resolve_identity(self, msb, lsb, program, role=None):
        addr=(msb,lsb,program)
        lst=self.by_address.get(addr,[])
        if not lst: return None, 'NO_EXACT_PROFILE'
        if addr in self.conflicts:
            # role may disambiguate, but never guess between names
            names=sorted(set(x['identity']['sound'] for x in lst))
            return None, 'IDENTITY_CONFLICT:' + '/'.join(names)
        if role:
            same=[p for p in lst if p['identity'].get('role')==role or role in dict(p.get('roles',[]))]
            if len(same)==1: return same[0], 'EXACT_ROLE'
            if same: lst=same
        # Same address/name sometimes appears as multiple role cells; choose strongest support as parent.
        lst=sorted(lst,key=lambda p:(p['support'].get('styles',0),p['support'].get('notes',0)),reverse=True)
        return lst[0], 'EXACT_ADDRESS'

    def choose_element_profile(self, profile, element):
        if not profile or not element: return profile
        e=profile.get('elements',{}).get(element)
        if not e or e.get('notes',0)<100: return profile
        merged=dict(profile)
        for k in ('velocity','key'):
            if k in e: merged[k]=e[k]
        merged['_element_override']=element
        return merged

    def resolve_drum_key(self, msb, lsb, program, note):
        if (msb,lsb,program) in self.conflicts:
            return None
        return self.drum_by_key.get((msb,lsb,program,note))


    def resolve_manual_dnc(self, msb, lsb, program):
        return self.dnc_manual.resolve(msb,lsb,program)

    def controller_profile(self,msb,lsb,program):
        return self.controller_by_address.get((msb,lsb,program))

    def profile_stability(self, profile):
        if not profile:return 'UNKNOWN'
        i=profile.get('identity',{})
        return self.stability.get((i.get('msb'),i.get('lsb'),i.get('program'),self._norm_sound_name(i.get('sound'))),'UNKNOWN')

    def instrument_positive_model_allowed(self,family,address,model):
        return (str(family or 'UNKNOWN').upper(),tuple(address or ()),str(model)) in self.instrument_positive_models

    def profile_completeness(self,profile):
        if not profile:return None
        identity=profile.get('identity',{});key=(identity.get('msb'),identity.get('lsb'),identity.get('program'),self._norm_sound_name(identity.get('sound')),identity.get('role'))
        return self.profile_completeness_by_key.get(key)

    def manual_only_profiles(self):
        return list(self.manual_only_profile_cards)

    def auto_candidate_allowed(self, profile):
        if not profile:return False,'missing_profile'
        i=profile.get('identity',{}); addr=(i.get('msb'),i.get('lsb'),i.get('program'))
        if i.get('rx_named') or i.get('dnc_named'):return False,'sensitive_rx_dnc_target'
        if addr in self.conflicts:return False,'target_identity_conflict'
        support=profile.get('support',{}); grade=support.get('grade')
        if grade not in ('STRONG','GOOD'):return False,'support_grade_'+str(grade)
        if int(support.get('styles',0))<5:return False,'insufficient_style_diversity'
        stability=self.profile_stability(profile)
        if stability not in ('STABLE','MODERATE'):return False,'stability_'+stability
        return True,'supported_stable_candidate'

    def resolve_velocity_semantics(self, msb, lsb, program, sound_name=None, role=None, element=None, cv=None):
        self._load_velocity_semantics()
        n=self._norm_sound_name(sound_name)
        if role and element and cv is not None:
            p=self.velocity_semantics_context.get((msb,lsb,program,n,role,element,int(cv or 0)))
            if p:return p,'EXACT_SOUND_ROLE_ELEMENT_CV'
        p=self.velocity_semantics_parent.get((msb,lsb,program,n))
        if p:return p,'EXACT_SOUND_PARENT'
        # If caller has no exported name and address is unambiguous, reuse the canonical Factory name.
        lst=self.by_address.get((msb,lsb,program),[])
        if len({self._norm_sound_name(x['identity'].get('sound')) for x in lst})==1 and lst:
            nn=self._norm_sound_name(lst[0]['identity'].get('sound'))
            if role and element and cv is not None:
                q=self.velocity_semantics_context.get((msb,lsb,program,nn,role,element,int(cv or 0)))
                if q:return q,'EXACT_ADDRESS_ROLE_ELEMENT_CV'
            q=self.velocity_semantics_parent.get((msb,lsb,program,nn))
            if q:return q,'EXACT_ADDRESS_PARENT'
        return None,'NO_VELOCITY_SEMANTICS'

    def _load_velocity_semantics(self):
        if self.velocity_semantics_parent is not None:return
        self.velocity_semantics_parent={}; self.velocity_semantics_context={}
        if not self.velocity_semantics_path.exists():return
        vr=self._required_json(self.velocity_semantics_path.name)
        for vp in vr.get('parent_profiles',[]):
            k=vp['key']; self.velocity_semantics_parent[(k['msb'],k['lsb'],k['program'],self._norm_sound_name(k.get('sound')))]=vp
        for vp in vr.get('context_profiles',[]):
            k=vp['key']; self.velocity_semantics_context[(k['msb'],k['lsb'],k['program'],self._norm_sound_name(k.get('sound')),k.get('role'),k.get('element'),int(k.get('cv') or 0))]=vp


    def arranger_element_role(self, element, role):
        if not self.arranger_atoms:return None
        return (self.arranger_atoms.get('element_role') or {}).get(f'{element}|{role}')

    def arranger_variation_progression(self):
        return (self.arranger_atoms.get('variation_progression') or {}) if self.arranger_atoms else {}

    def family_fallback(self, family, role=None):
        # Deliberately disabled for mutation: choosing a different exact Sound
        # would be guessing. Family data may be used for analysis/reporting only.
        return None