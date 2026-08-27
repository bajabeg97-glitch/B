import re
from collections import defaultdict
from ..core.midi_io import STYLE_ROLE_BY_CHANNEL, collect_channel_state
from ..models import SoundIdentity, TrackContext
from ..intelligence.sound_fx import normalize_family

GM_FAMILY={
    range(0,8):'PIANO', range(8,16):'CHROMATIC_PERC', range(16,24):'ORGAN', range(24,32):'GUITAR',
    range(32,40):'BASS', range(40,48):'STRINGS', range(48,56):'ENSEMBLE', range(56,64):'BRASS',
    range(64,72):'REED', range(72,80):'PIPE', range(80,88):'SYNTH_LEAD', range(88,96):'SYNTH_PAD',
    range(96,104):'SYNTH_FX', range(104,112):'ETHNIC', range(112,120):'PERCUSSIVE', range(120,128):'SFX'
}

def gm_family(program):
    if program is None: return 'UNKNOWN'
    for r,f in GM_FAMILY.items():
        if program in r:return f
    return 'UNKNOWN'

def style_role_for(ch, track_name):
    up=(track_name or '').upper()
    for key in ('DRUM','PERC','BASS','ACC1','ACC2','ACC3','ACC4','ACC5'):
        if key in up: return 'DRUM' if key=='DRUM' else key
    return STYLE_ROLE_BY_CHANNEL.get(ch,'UNKNOWN')

# Backward-compatible name used by the Factory/velocity analysis layer, whose
# input is explicitly Pa Style material.
def role_for(ch, track_name):
    return style_role_for(ch,track_name)

def song_role_for(ch, track_name, program=None):
    """Infer Song roles without applying Pa Style channel semantics."""
    up=(track_name or '').upper()
    if ch==9 or any(x in up for x in ('DRUM','KIT')): return 'DRUM'
    if any(x in up for x in ('PERC','CONGA','BONGO','SHAKER')): return 'PERC'
    if 'BASS' in up or (program is not None and 32<=program<=39): return 'BASS'
    return 'SONG'

def parse_element(text):
    s=(text or '').lower()
    pats=[('Variation 1',r'variation\s*1|var\s*1'),('Variation 2',r'variation\s*2|var\s*2'),('Variation 3',r'variation\s*3|var\s*3'),('Variation 4',r'variation\s*4|var\s*4'),('Intro 1',r'intro\s*1'),('Intro 2',r'intro\s*2'),('Intro 3',r'intro\s*3'),('Fill 1',r'fill\s*1'),('Fill 2',r'fill\s*2'),('Break',r'break'),('Ending 1',r'ending\s*1'),('Ending 2',r'ending\s*2'),('Ending 3',r'ending\s*3')]
    for name,p in pats:
        if re.search(p,s): return name
    return None

def parse_cv(text):
    m=re.search(r'\bcv\s*([1-6])\b',(text or '').lower()); return int(m.group(1)) if m else None

def detect_content_type_details(mid, requested='auto'):
    requested=(requested or 'auto').lower()
    if requested not in ('auto','style','song'):
        raise ValueError('Unknown content type: %s' % requested)
    if requested!='auto':
        return {'content_type':requested,'confidence':1.0,'ambiguous':False,'reasons':['explicit_user_selection']}
    states=collect_channel_state(mid)
    texts=[st.get('track_name','') for st in states.values()]
    elements=sum(parse_element(x) is not None for x in texts)
    cvs=sum(parse_cv(x) is not None for x in texts)
    accs=sum(bool(re.search(r'\bACC[1-5]\b',(x or '').upper())) for x in texts)
    if elements or cvs:
        return {'content_type':'style','confidence':0.99,'ambiguous':False,'reasons':[f'element_markers={elements}',f'cv_markers={cvs}',f'acc_markers={accs}']}
    if accs>=2:
        return {'content_type':'style','confidence':0.92,'ambiguous':False,'reasons':[f'acc_markers={accs}']}
    if accs==1:
        return {'content_type':'style','confidence':0.65,'ambiguous':True,'reasons':['single_acc_marker_without_element_or_cv']}
    named=sum(bool((x or '').strip()) for x in texts)
    confidence=0.82 if named else 0.65
    return {'content_type':'song','confidence':confidence,'ambiguous':confidence<0.75,'reasons':[f'named_contexts={named}','no_style_element_cv_or_acc_markers']}

def detect_content_type(mid, requested='auto'):
    return detect_content_type_details(mid,requested)['content_type']

def build_contexts(mid, registry, content_type='auto'):
    content_type=detect_content_type(mid,content_type)
    states=collect_channel_state(mid); out={}
    for (ti,ch),st in states.items():
        role=(style_role_for(ch,st['track_name']) if content_type=='style' else song_role_for(ch,st['track_name'],st['program']))
        p,status=registry.resolve_identity(st['msb'],st['lsb'],st['program'],role)
        manual_dnc=registry.resolve_manual_dnc(st['msb'],st['lsb'],st['program']) if hasattr(registry,'resolve_manual_dnc') else None
        if p:
            ii=p['identity']; name=ii.get('sound'); fam=normalize_family(ii.get('org_family','UNKNOWN'),name); rx=ii.get('rx_named',False); dnc=bool(ii.get('dnc_named',False) or manual_dnc)
            if manual_dnc:
                name=manual_dnc['name']; fam=manual_dnc.get('family',fam)
        elif manual_dnc:
            name=manual_dnc['name']; fam=normalize_family(manual_dnc.get('family','UNKNOWN'),name); rx=False; dnc=True; status='MANUAL_DNC_EXACT'
        else:
            fam='DRUM_KIT' if role in ('DRUM','PERC') else gm_family(st['program']); name=None; rx=dnc=False
        ident=SoundIdentity(st['msb'],st['lsb'],st['program'],name,fam,rx,dnc,status.startswith('IDENTITY_CONFLICT') or st.get('multi_program',False))
        element=parse_element(st['track_name']) if content_type=='style' else None
        cv=parse_cv(st['track_name']) if content_type=='style' else None
        out[(ti,ch)]=TrackContext(ti,ch,role,ident,element,cv,fam,st['track_name'],content_type,status)
    return out