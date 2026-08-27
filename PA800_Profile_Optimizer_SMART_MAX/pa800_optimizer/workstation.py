"""Production session, A/B variant, mixer and crash-journal primitives."""
from __future__ import annotations

from dataclasses import asdict,is_dataclass
from datetime import datetime,timezone
from array import array
import hashlib,json,sys,wave
from pathlib import Path


PHASES=['PREFLIGHT','DOCTOR','COMPATIBILITY','CONTEXT','VOICE_FX','ARTICULATION','MUSICAL_CONTEXT','MIX_FX','PERFORMANCE_SHAPING','VERIFY','COMMIT']


def _utc():return datetime.now(timezone.utc).isoformat()


def _sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def _plain(value):
    if is_dataclass(value):return asdict(value)
    return value


def apply_export_preset(config,preset):
    preset=str(preset or 'auto').lower()
    if preset not in ('auto','song','style','preserve'):raise ValueError('Unknown export preset: '+preset)
    config.export_preset=preset
    if preset=='song':config.content_type='song'
    elif preset=='style':config.content_type='style';config.require_style_import_contract=True
    elif preset=='preserve':
        if hasattr(config,'lock_preserve'):config.lock_preserve()
        else:
            config.mode='preserve';config.autopilot=False;config.velocity_strength=.10;config.velocity_random_strength=.10;config.timing_strength=.05;config.gate_strength=.05;config.velocity_conductor_strength=.20;config.velocity_conductor_max_delta=8
            config.smart_policy_override='suggest';config.apply_high_confidence_sound_changes=False;config.apply_existing_fx_sends=False;config.preserve_controllers=True;config.apply_articulation_triggers=False;config.apply_performance_director=False;config.mix_fx_policy='shadow';config.apply_mix_fx_director=False
    return config


def build_mixer_snapshot(report):
    report=_plain(report);functions={(row['track'],row['channel']):row for row in report.get('musical_context',{}).get('track_functions',[])};velocity={(row['track'],row['channel']):row for row in report.get('velocity_conductor',{}).get('contexts',[])};mix={(row['track'],row['channel']):row for row in report.get('mix_fx_director',{}).get('contexts',[])};voice={(row['track'],row['channel']):row for row in report.get('intelligence',[])};rows=[]
    for context in report.get('contexts',[]):
        key=(context.get('track'),context.get('channel'));function=functions.get(key,{});vel=velocity.get(key,{});fx=mix.get(key,{});sound=voice.get(key,{})
        rows.append({'track':key[0],'channel':key[1],'role':context.get('role'),'function':function.get('function','UNKNOWN'),'family':context.get('family'),'sound':context.get('sound'),'evidence_level':context.get('evidence_level'),'velocity_before':vel.get('normalized_median_before'),'velocity_after':vel.get('normalized_median_after'),'effective_energy_after':vel.get('effective_energy_after'),'fx_events':fx.get('existing_events',0),'fx_changes':fx.get('changes',0),'fx_status':fx.get('apply_status'),'voice_action':sound.get('action'),'voice_status':sound.get('sound_apply_status'),'protected':bool(context.get('conflict'))})
    return {'schema':'PA800_WORKSTATION_MIXER_V1','rows':rows,'summary':{'tracks':len(rows),'velocity_changed_tracks':sum((row.get('velocity_before') is not None and row.get('velocity_before')!=row.get('velocity_after')) for row in rows),'fx_changed_tracks':sum(bool(row.get('fx_changes')) for row in rows),'voice_changed_tracks':sum(str(row.get('voice_status','')).startswith('applied') for row in rows),'protected_tracks':sum(row['protected'] for row in rows),'verifier_pass':bool(report.get('verifier',{}).get('pass'))}}


class WorkstationSession:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.exists():
            try:self.data=json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError,UnicodeDecodeError,json.JSONDecodeError) as exc:
                raise ValueError('Invalid workstation session; existing file was preserved: '+str(self.path)) from exc
            if not isinstance(self.data,dict) or self.data.get('schema')!='PA800_WORKSTATION_SESSION_V1':
                raise ValueError('Invalid workstation session schema; existing file was preserved: '+str(self.path))
        else:self.data={'schema':'PA800_WORKSTATION_SESSION_V1','created_utc':_utc(),'updated_utc':_utc(),'variants':[],'history':[],'history_cursor':0,'batch':None,'audio_references':[],'audition_decisions':[]}
        self.data.setdefault('audition_decisions',[])

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);self.data['updated_utc']=_utc();tmp=self.path.with_suffix(self.path.suffix+'.tmp');tmp.write_text(json.dumps(self.data,indent=2,ensure_ascii=False,sort_keys=True),encoding='utf-8');tmp.replace(self.path);return self.path

    def active_variant(self):
        cursor=int(self.data.get('history_cursor',0));history=self.data.get('history',[])
        if cursor<=0 or cursor>len(history):return None
        variant_id=history[cursor-1];return next((row for row in self.data.get('variants',[]) if row['id']==variant_id),None)

    def record_variant(self,input_path,output_path,report_path=None,config=None,label='optimized',mixer=None):
        input_path=Path(input_path);output_path=Path(output_path);identity={'input_sha256':_sha256(input_path),'output_sha256':_sha256(output_path),'config':_plain(config) or {},'label':str(label)};variant_id=hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()[:20]
        existing=next((row for row in self.data['variants'] if row['id']==variant_id),None)
        if not existing:
            existing={'id':variant_id,'created_utc':_utc(),'label':str(label),'input':str(input_path),'output':str(output_path),'report':str(report_path) if report_path else None,**identity,'mixer':mixer or {}};self.data['variants'].append(existing)
        history=self.data.get('history',[])[:int(self.data.get('history_cursor',0))]
        if not history or history[-1]!=variant_id:history.append(variant_id)
        self.data['history']=history;self.data['history_cursor']=len(history);self.save();return existing

    def undo(self):
        self.data['history_cursor']=max(0,int(self.data.get('history_cursor',0))-1);self.save();return self.active_variant()

    def redo(self):
        self.data['history_cursor']=min(len(self.data.get('history',[])),int(self.data.get('history_cursor',0))+1);self.save();return self.active_variant()

    def _record_audition_decision(self,action,label=None,input_path=None,output_path=None,report_path=None,details=None):
        row={'decided_utc':_utc(),'action':str(action).upper(),'label':None if label is None else str(label),'input':None if input_path is None else str(Path(input_path)),'output':None if output_path is None else str(Path(output_path)),'report':None if report_path is None else str(Path(report_path)),'details':details or {}}
        self.data.setdefault('audition_decisions',[]).append(row);self.save();return row

    def attach_audio(self,audio_path,variant_id=None):
        audio=Path(audio_path);row={'path':str(audio),'sha256':_sha256(audio),'bytes':audio.stat().st_size,'variant_id':variant_id or ((self.active_variant() or {}).get('id')),'attached_utc':_utc()}
        try:
            with wave.open(str(audio),'rb') as stream:
                channels=stream.getnchannels();rate=stream.getframerate();frames=stream.getnframes();width=stream.getsampwidth();raw=stream.readframes(frames);samples=[]
                if width==2:
                    values=array('h');values.frombytes(raw)
                    if sys.byteorder!='little':values.byteswap()
                    samples=[abs(value)/32768.0 for value in values]
                elif width==1:samples=[abs(value-128)/128.0 for value in raw]
                points=min(128,max(1,len(samples)));step=max(1,len(samples)//points);envelope=[round(max(samples[index:index+step] or [0.0]),4) for index in range(0,len(samples),step)][:128]
                row.update({'channels':channels,'sample_rate':rate,'sample_width_bytes':width,'frames':frames,'duration_seconds':round(frames/max(1,rate),4),'waveform_envelope':envelope})
        except Exception as exc:row['wave_metadata_error']=repr(exc)
        if not any(item.get('sha256')==row['sha256'] and item.get('variant_id')==row['variant_id'] for item in self.data['audio_references']):self.data['audio_references'].append(row)
        self.save();return row

    def begin_batch(self,inputs,config=None):
        paths=[str(Path(path)) for path in inputs];signature=hashlib.sha256(json.dumps({'inputs':paths,'config':_plain(config) or {}},sort_keys=True,default=str).encode()).hexdigest()[:20];current=self.data.get('batch')
        if not current or current.get('id')!=signature:
            current={'id':signature,'state':'RUNNING','started_utc':_utc(),'config':_plain(config) or {},'items':[{'input':path,'status':'PENDING','last_phase':None,'phases':[]} for path in paths]};self.data['batch']=current
        else:current['state']='RUNNING'
        self.save();return current

    def record_phase(self,input_path,phase,details=None):
        if phase not in PHASES:raise ValueError('Unknown workstation phase: '+str(phase))
        batch=self.data.get('batch') or {};item=next((row for row in batch.get('items',[]) if row['input']==str(Path(input_path))),None)
        if item is None:return
        item['status']='IN_PROGRESS';item['last_phase']=phase
        if phase not in item['phases']:item['phases'].append(phase)
        if details:item['phase_details']=details
        self.save()

    def finish_file(self,input_path,status,output=None,report=None,error=None):
        batch=self.data.get('batch') or {};item=next((row for row in batch.get('items',[]) if row['input']==str(Path(input_path))),None)
        if item is None:return
        item.update({'status':status,'output':str(output) if output else None,'report':str(report) if report else None,'error':None if error is None else str(error),'finished_utc':_utc()});self.save()

    def pending_inputs(self):
        terminal={'PASS','SKIP_EXISTS'};return [row['input'] for row in (self.data.get('batch') or {}).get('items',[]) if row.get('status') not in terminal]

    def finish_batch(self,cancelled=False):
        if self.data.get('batch'):
            self.data['batch']['state']='CANCELLED' if cancelled else 'COMPLETE';self.data['batch']['finished_utc']=_utc();self.save()
        return self.data.get('batch')