"""One-command real-PC validation. Produces a ZIP intended to be sent back."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import statistics
import traceback
import tracemalloc
import zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def run(cmd,cwd=ROOT,timeout=900,env=None):
    started=time.perf_counter()
    p=subprocess.run(cmd,cwd=str(cwd),capture_output=True,text=True,timeout=timeout,env=env)
    return {'command':[str(x) for x in cmd],'returncode':p.returncode,'seconds':round(time.perf_counter()-started,3),'stdout':p.stdout,'stderr':p.stderr}


def release_test_command(basetemp=None):
    manifest=ROOT/'RELEASE_TESTS.txt'
    tests=[line.strip() for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
    missing=[path for path in tests if not (ROOT/path).is_file()]
    if missing:raise RuntimeError('Missing release tests: '+', '.join(missing))
    command=[sys.executable,'-m','pytest','-q']
    if basetemp:command+=['--basetemp',str(basetemp)]
    return [*command,*tests]


def make_midi(path,style=False,tracks=1,notes_per_track=24):
    import mido
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    for ti in range(tracks):
        tr=mido.MidiTrack();mid.tracks.append(tr);ch=ti%16
        name=('Variation 2 ACC%d CV1' % ((ti%5)+1)) if style else ('Song Piano %d' % (ti+1))
        tr.append(mido.MetaMessage('track_name',name=name,time=0))
        tr.append(mido.Message('control_change',channel=ch,control=0,value=121,time=0))
        tr.append(mido.Message('control_change',channel=ch,control=32,value=3,time=0))
        tr.append(mido.Message('program_change',channel=ch,program=0,time=0))
        tr.append(mido.Message('control_change',channel=ch,control=91,value=20,time=0))
        for i in range(notes_per_track):
            tr.append(mido.Message('note_on',channel=ch,note=48+(i%24),velocity=45+(i*7)%78,time=0 if i==0 else 48))
            tr.append(mido.Message('note_off',channel=ch,note=48+(i%24),velocity=0,time=36))
    mid.save(path)


def real_mido_optimizer_checks(work):
    import mido
    from pa800_optimizer.config import OptimizeConfig
    from pa800_optimizer.optimizer import Optimizer
    results=[]
    style=work/'style_fixture.mid';song=work/'song_fixture.mid';make_midi(style,True);make_midi(song,False)
    cases=[('style_auto',style,'auto','max'),('song_explicit',song,'song','natural'),('preserve',song,'song','preserve')]
    for name,src,content,mode in cases:
        out=work/(name+'.mid');report=work/(name+'.report.json');cfg=OptimizeConfig.for_mode(mode);cfg.content_type=content
        started=time.perf_counter();rep=Optimizer(cfg).optimize(src,out,report)
        results.append({'case':name,'pass':rep.verifier.get('pass'),'seconds':round(time.perf_counter()-started,3),'content_type':rep.content_type,'content_detection':rep.content_detection,'changes':len(rep.changes),'warnings':len(rep.warnings),'output_bytes':out.stat().st_size})
    cfg=OptimizeConfig.for_mode('live');cfg.content_type='song';a=work/'det_a.mid';b=work/'det_b.mid'
    Optimizer(cfg).optimize(song,a);Optimizer(cfg).optimize(song,b)
    results.append({'case':'deterministic_bytes','pass':a.read_bytes()==b.read_bytes(),'bytes':a.stat().st_size})
    broken=work/'broken_fixture.mid';fixed=work/'doctor_fixed.mid'
    mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.append(mido.MetaMessage('track_name',name='Broken Song',time=0));tr.append(mido.Message('note_off',channel=0,note=40,velocity=0,time=0));tr.append(mido.Message('note_on',channel=0,note=60,velocity=90,time=24));tr.append(mido.Message('control_change',channel=0,control=64,value=127,time=48));mid.save(broken)
    cfg=OptimizeConfig.for_mode('gentle');cfg.content_type='song';rep=Optimizer(cfg).optimize(broken,fixed)
    from pa800_optimizer.midi_doctor import scan_midi_health
    health=scan_midi_health(mido.MidiFile(fixed))
    results.append({'case':'midi_doctor_broken_input','pass':bool(rep.midi_repair.get('pass') and health.get('pass') and rep.midi_repair.get('repair_count',0)>=3),'repairs':rep.midi_repair.get('repair_count'),'health':health})
    voice=work/'voice_fx_fixture.mid';voice_out=work/'voice_fx_out.mid';mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr);ch=11
    tr.append(mido.MetaMessage('track_name',name='Variation 2 ACC1 CV1',time=0));tr.append(mido.Message('control_change',channel=ch,control=0,value=121,time=0));tr.append(mido.Message('control_change',channel=ch,control=32,value=8,time=0));tr.append(mido.Message('program_change',channel=ch,program=24,time=0));tr.append(mido.Message('control_change',channel=ch,control=91,value=60,time=0));tr.append(mido.Message('control_change',channel=ch,control=93,value=40,time=0))
    for i in range(24):tr.append(mido.Message('note_on',channel=ch,note=60+(i%7),velocity=75,time=0 if i==0 else 4));tr.append(mido.Message('note_off',channel=ch,note=60+(i%7),velocity=0,time=116))
    mid.save(voice);voice_whitelist=work/'voice_whitelist.json';voice_whitelist.write_text('{"approved_targets":[{"address":[121,15,24]}]}',encoding='utf-8');voice_cfg=OptimizeConfig.for_mode('auto');voice_cfg.voice_hardware_whitelist_path=str(voice_whitelist);rep=Optimizer(voice_cfg).optimize(voice,voice_out);row=(rep.intelligence or [{}])[0]
    results.append({'case':'voice_fx_director','pass':bool(rep.verifier.get('pass') and row.get('sound_apply_status')=='applied' and tuple(row.get('candidate_address') or ())==(121,15,24) and row.get('fx_send_changes')==2),'automation':rep.automation_decision,'decision':row})
    safe=work/'safe_voice_fixture.mid';safe_out=work/'safe_voice_out.mid';mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.append(mido.MetaMessage('track_name',name='Song Nylon Guitar',time=0));tr.append(mido.Message('control_change',channel=0,control=0,value=0,time=0));tr.append(mido.Message('control_change',channel=0,control=0,value=121,time=120));tr.append(mido.Message('control_change',channel=0,control=32,value=0,time=0));tr.append(mido.Message('control_change',channel=0,control=0,value=121,time=0));tr.append(mido.Message('control_change',channel=0,control=32,value=0,time=0));tr.append(mido.Message('program_change',channel=0,program=24,time=0));tr.append(mido.Message('control_change',channel=0,control=32,value=0,time=120))
    for i in range(24):tr.append(mido.Message('note_on',channel=0,note=66+(i%7),velocity=70,time=0 if i==0 else 4));tr.append(mido.Message('note_off',channel=0,note=66+(i%7),velocity=0,time=116))
    mid.save(safe);cfg=OptimizeConfig.for_mode('auto');cfg.content_type='song';rep=Optimizer(cfg).optimize(safe,safe_out);row=(rep.intelligence or [{}])[0];after=mido.MidiFile(safe_out);bank=[m.value for t in after.tracks for m in t if m.type=='control_change' and m.control==32]
    results.append({'case':'safe_gm_voice_upgrade_redundant_bank','pass':bool(rep.verifier.get('pass') and row.get('action')=='SAFE_GM_UPGRADE' and row.get('sound_apply_status')=='applied_redundant_bank_sequence' and tuple(row.get('candidate_address') or ())==(121,15,24) and bank and set(bank)=={15}),'automation':rep.automation_decision,'decision':row,'cc32_after':bank})
    def velocity_fixture(path,velocities):
        vm=mido.MidiFile(type=1,ticks_per_beat=192);vt=mido.MidiTrack();vm.tracks.append(vt);vt.append(mido.MetaMessage('track_name',name='Song Piano',time=0));vt.append(mido.Message('control_change',channel=0,control=0,value=121,time=0));vt.append(mido.Message('control_change',channel=0,control=32,value=3,time=0));vt.append(mido.Message('program_change',channel=0,program=0,time=0))
        for i,value in enumerate(velocities):vt.append(mido.Message('note_on',channel=0,note=60+i,velocity=value,time=0 if i==0 else 96));vt.append(mido.Message('note_off',channel=0,note=60+i,velocity=0,time=72))
        vm.save(path)
    low=work/'velocity_low.mid';high=work/'velocity_high.mid';low_out=work/'velocity_low_out.mid';high_out=work/'velocity_high_out.mid';velocity_fixture(low,[20,30,40,50,60,70,80,90]);velocity_fixture(high,[70,80,90,100,110,120,125,127])
    cfg=OptimizeConfig.for_mode('live');cfg.content_type='song';cfg.enable_sound_kit_selector=False;cfg.enable_fx_intelligence=False;cfg.enable_timing=False;cfg.enable_gate=False
    lr=Optimizer(cfg).optimize(low,low_out);hr=Optimizer(cfg).optimize(high,high_out)
    def output_median(path):return statistics.median(msg.velocity for track in mido.MidiFile(path).tracks for msg in track if msg.type=='note_on' and msg.velocity>0)
    lm=output_median(low_out);hm=output_median(high_out);results.append({'case':'velocity_conductor_cross_file','pass':bool(abs(lm-hm)<=8 and lr.velocity_conductor.get('pass') and hr.velocity_conductor.get('pass')),'low_median':lm,'high_median':hm,'low_audit':lr.velocity_conductor,'high_audit':hr.velocity_conductor})
    dnc=work/'dnc_articulation.mid';dnc_out=work/'dnc_articulation_out.mid';mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.append(mido.MetaMessage('track_name',name='Nylon Guitar DNC',time=0));tr.append(mido.Message('control_change',channel=0,control=0,value=121,time=0));tr.append(mido.Message('control_change',channel=0,control=32,value=18,time=0));tr.append(mido.Message('program_change',channel=0,program=24,time=0));tr.append(mido.Message('note_on',channel=0,note=60,velocity=82,time=0));tr.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=96));tr.append(mido.Message('note_on',channel=0,note=63,velocity=86,time=2));tr.append(mido.Message('note_off',channel=0,note=63,velocity=0,time=96));mid.save(dnc)
    cfg=OptimizeConfig.for_mode('natural');cfg.content_type='song';cfg.apply_articulation_triggers=True;rep=Optimizer(cfg).optimize(dnc,dnc_out);pulses=[(msg.control,msg.value) for track in mido.MidiFile(dnc_out).tracks for msg in track if msg.type=='control_change' and msg.control==80]
    results.append({'case':'articulation_director_cc80_roundtrip','pass':bool(rep.verifier.get('pass') and rep.articulations.get('applied_triggers')==1 and pulses==[(80,127),(80,0)]),'pulses':pulses,'audit':rep.articulations})
    preserve_out=work/'dnc_articulation_preserve.mid';cfg=OptimizeConfig.for_mode('preserve');cfg.content_type='song';cfg.apply_articulation_triggers=True;rep=Optimizer(cfg).optimize(dnc,preserve_out);preserve_pulses=[(msg.control,msg.value) for track in mido.MidiFile(preserve_out).tracks for msg in track if msg.type=='control_change' and msg.control==80]
    results.append({'case':'articulation_preserve_blocks_cc80_apply','pass':bool(rep.verifier.get('pass') and rep.articulations.get('applied_triggers')==0 and not preserve_pulses),'pulses':preserve_pulses,'audit':rep.articulations})
    tracemalloc.start();stress=work/'stress.mid';make_midi(stress,False,tracks=8,notes_per_track=300)
    out=work/'stress_out.mid';cfg=OptimizeConfig.for_mode('natural');cfg.content_type='song';cfg.enable_sound_kit_selector=False;cfg.enable_fx_intelligence=False
    started=time.perf_counter();rep=Optimizer(cfg).optimize(stress,out);current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    results.append({'case':'stress_2400_notes','pass':rep.verifier.get('pass'),'seconds':round(time.perf_counter()-started,3),'peak_mib':round(peak/1048576,2),'output_bytes':out.stat().st_size})
    for pattern in ('*.mid','*.report.json','voice_whitelist.json'):
        for path in work.glob(pattern):
            try:path.unlink()
            except OSError:pass
    return results


def validate_user_midis(folder,work,max_files):
    if not folder:return {'requested':False}
    from pa800_optimizer.config import OptimizeConfig
    from pa800_optimizer.optimizer import Optimizer
    folder=Path(folder)
    if not folder.is_dir():return {'requested':True,'folder':str(folder),'files_found':0,'results':[],'pass':False,'error':'Input folder does not exist.'}
    files=sorted([p for p in folder.iterdir() if p.suffix.lower() in ('.mid','.midi','.kar')])[:max_files]
    ab=work/'PA800_AB_PACK';originals=ab/'01_ORIGINAL';optimized=ab/'02_OPTIMIZED';reports=ab/'03_REPORTS'
    for path in (originals,optimized,reports):path.mkdir(parents=True,exist_ok=True)
    def sha256(path):
        h=hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        return h.hexdigest()
    rows=[];score_rows=[];cfg=OptimizeConfig.for_mode('auto');cfg.content_type='auto'
    for i,src in enumerate(files,1):
        stem='%03d_%s' % (i,src.stem);original_copy=originals/(stem+src.suffix.lower());out=optimized/(stem+'_OPTIMIZED.mid');report_path=reports/(stem+'.report.json')
        shutil.copy2(src,original_copy)
        try:
            started=time.perf_counter();rep=Optimizer(cfg).optimize(str(src),str(out),str(report_path));seconds=round(time.perf_counter()-started,3)
            intelligence=rep.intelligence or [];sound_changes=sum(1 for row in intelligence if str(row.get('sound_apply_status','')).startswith('applied'));safe_voice_changes=sum(1 for row in intelligence if row.get('action')=='SAFE_GM_UPGRADE' and str(row.get('sound_apply_status','')).startswith('applied'));hardware_voice_changes=sum(1 for row in intelligence if row.get('action')=='AUTO_CANDIDATE' and str(row.get('sound_apply_status','')).startswith('applied'));voice_suggestions=sum(1 for row in intelligence if row.get('action')=='SUGGEST_ONLY');fx_changes=sum(int(row.get('fx_send_changes') or 0) for row in intelligence)
            pilot=rep.automation_decision or {};doctor=rep.midi_repair or {};velocity=rep.velocity_conductor or {}
            articulation=rep.articulations or {}
            row={'case_id':i,'file':src.name,'pass':bool(rep.verifier.get('pass')),'seconds':seconds,'content_type':rep.content_type,'content_confidence':(rep.content_detection or {}).get('confidence'),'auto_mode':pilot.get('mode'),'smart_policy':pilot.get('effective_smart_policy'),'repairs':doctor.get('repair_count',0),'velocity_before':velocity.get('global_normalized_median_before'),'velocity_after':velocity.get('global_normalized_median_after'),'sound_changes':sound_changes,'safe_voice_changes':safe_voice_changes,'hardware_voice_changes':hardware_voice_changes,'voice_suggestions':voice_suggestions,'fx_event_changes':fx_changes,'articulation_contexts':articulation.get('exact_dnc_contexts',0),'articulation_triggers':articulation.get('applied_triggers',0),'musical_changes':len(rep.changes),'warnings':len(rep.warnings),'input_sha256':sha256(original_copy),'output_sha256':sha256(out),'original_file':str(original_copy.relative_to(work)),'optimized_file':str(out.relative_to(work)),'report_file':str(report_path.relative_to(work))}
        except Exception as exc:
            row={'case_id':i,'file':src.name,'pass':False,'error':repr(exc),'stage':getattr(exc,'stage',None),'diagnostics':getattr(exc,'diagnostics',None),'traceback':traceback.format_exc(),'input_sha256':sha256(original_copy),'original_file':str(original_copy.relative_to(work))}
        rows.append(row)
        score_rows.append({**{key:row.get(key,'') for key in ('case_id','file','pass','content_type','auto_mode','smart_policy','repairs','velocity_before','velocity_after','sound_changes','fx_event_changes')},'pa800_os':'','set_name':'','timing_1_5':'','dynamics_1_5':'','rx_dnc_preserved_1_5':'','sound_fit_1_5':'','fx_fit_1_5':'','stuck_note_yes_no':'','clipping_yes_no':'','preference_original_optimized_same':'','comments':''})
    fields=list(score_rows[0]) if score_rows else ['case_id','file','pass','comments']
    with (ab/'PA800_AB_SCORE_SHEET.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(score_rows)
    (ab/'PA800_AB_MANIFEST.json').write_text(json.dumps({'schema':'PA800_AB_PACK_V1','created_utc':datetime.now(timezone.utc).isoformat(),'source_folder':str(folder),'cases':rows},indent=2,ensure_ascii=False),encoding='utf-8')
    passed=sum(bool(row.get('pass')) for row in rows);summary={'schema':'PA800_FINAL_REAL_MIDI_SUMMARY_V1','files':len(rows),'passed':passed,'failed':len(rows)-passed,'total_repairs':sum(int(row.get('repairs') or 0) for row in rows),'safe_voice_changes':sum(int(row.get('safe_voice_changes') or 0) for row in rows),'hardware_voice_changes':sum(int(row.get('hardware_voice_changes') or 0) for row in rows),'voice_suggestions':sum(int(row.get('voice_suggestions') or 0) for row in rows),'fx_event_changes':sum(int(row.get('fx_event_changes') or 0) for row in rows),'all_verifiers_pass':passed==len(rows) and bool(rows)}
    (ab/'FINAL_REAL_MIDI_SUMMARY.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (ab/'READ_ME_FIRST.txt').write_text('PA800 REAL A/B PACK\n\n1. Na Pa800 pusti 01_ORIGINAL i odgovarajuci 02_OPTIMIZED fajl sa istim SET/OS/mixer uslovima.\n2. Popuni PA800_AB_SCORE_SHEET.csv.\n3. Ne mijenjaj 03_REPORTS; oni dokazuju event promjene i verifier.\n4. SEND_ME ZIP po defaultu ne sadrzi MIDI fajlove. Privatni MIDI sadrzaj ukljucuje se samo eksplicitnom opcijom --include-private-midis.\n\nKriticni FAIL: stuck note, pogresan Sound, nestala RX/DNC artikulacija, promijenjena forma/tempo ili clipping.\n',encoding='utf-8')
    return {'requested':True,'folder':str(folder),'files_found':len(files),'ab_pack':str(ab.relative_to(work)),'results':rows,'pass':all(row.get('pass') for row in rows) if rows else False}


def wheel_check(work):
    out=work/'wheel';out.mkdir()
    result=run([sys.executable,'-m','build','--wheel','--outdir',str(out)],timeout=600)
    wheels=list(out.glob('*.whl'));result['wheels']=[x.name for x in wheels]
    required=['factory_sound_profiles_v1.json','factory_drum_key_profiles_v1.json','factory_velocity_semantics_v2.json']
    install_dir=work/'wheel_install'
    if wheels:
        with zipfile.ZipFile(wheels[0]) as z:names=z.namelist()
        result['package_data']={name:any(x.endswith('/profiles/data/'+name) for x in names) for name in required}
        result['install']=run([sys.executable,'-m','pip','install','--no-deps','--target',str(install_dir),str(wheels[0])],cwd=work,timeout=600)
        smoke_env={**os.environ,'PYTHONPATH':str(install_dir)}
        smoke="import pa800_optimizer; from pa800_optimizer.profiles.registry import ProfileRegistry; r=ProfileRegistry(); assert len(r.profiles)==542; print(pa800_optimizer.__version__,len(r.profiles))"
        result['installed_smoke']=run([sys.executable,'-c',smoke],cwd=work,timeout=300,env=smoke_env)
        result['pass']=result['returncode']==0 and all(result['package_data'].values()) and result['install']['returncode']==0 and result['installed_smoke']['returncode']==0
    else:result['package_data']={};result['pass']=False
    shutil.rmtree(out,ignore_errors=True)
    shutil.rmtree(install_dir,ignore_errors=True)
    shutil.rmtree(ROOT/'build',ignore_errors=True)
    for path in ROOT.glob('*.egg-info'):shutil.rmtree(path,ignore_errors=True)
    return result


def tkinter_check():
    try:
        import tkinter as tk
        tcl=tk.Tcl();result={'import':True,'tcl_patchlevel':str(tcl.call('info','patchlevel')),'tk_version':tk.TkVersion}
        try:
            root=tk.Tk();root.withdraw();root.update_idletasks();root.destroy();result['window']=True
        except Exception as exc:result['window']=False;result['window_error']=repr(exc)
        return result
    except Exception as exc:return {'import':False,'error':repr(exc)}


def pick_input_folder():
    """Open a native folder picker so double-click validation tests real files."""
    import tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw();root.attributes('-topmost',True);root.update_idletasks()
    try:return filedialog.askdirectory(title='Izaberi folder sa stvarnim MIDI/KAR fajlovima za PA800 A/B test') or None
    finally:root.destroy()


def create_support_archive(out,archive_base,include_private_midis=False):
    """Create a support ZIP that is privacy-safe unless explicitly overridden."""
    excluded_prefixes=('PA800_AB_PACK/01_ORIGINAL/','PA800_AB_PACK/02_OPTIMIZED/','PA800_AB_PACK/03_REPORTS/')
    with zipfile.ZipFile(str(archive_base)+'.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob('*')):
            if not path.is_file():continue
            relative=path.relative_to(out).as_posix()
            if not include_private_midis and relative.startswith(excluded_prefixes):continue
            archive.write(path,relative)
    return str(archive_base)+'.zip'


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--input-folder');ap.add_argument('--pick-folder',action='store_true');ap.add_argument('--require-user-midis',action='store_true');ap.add_argument('--max-files',type=int,default=30);ap.add_argument('--include-private-midis',action='store_true',help='Explicitly include original, optimized and detailed MIDI reports in SEND_ME ZIP');ns=ap.parse_args(argv)
    if not ns.input_folder and ns.pick_folder:
        try:ns.input_folder=pick_input_folder()
        except Exception as exc:print('[ERROR] Folder picker failed:',repr(exc));return 2
    if ns.require_user_midis and not ns.input_folder:
        print('[CANCELLED] Nije izabran folder sa MIDI/KAR fajlovima. Validacija stvarnih pjesama nije pokrenuta.')
        return 2
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f');base=ROOT/'validation_results';base.mkdir(exist_ok=True)
    from pa800_optimizer.runtime_safety import OutputLock
    validation_lock=OutputLock(base/'PC_VALIDATION_ACTIVE');validation_lock.acquire()
    out=base/('PA800_PC_VALIDATION_'+stamp);out.mkdir()
    try:
        import tomllib
        project_version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    except Exception:project_version=None
    try:
        build_identity=json.loads((ROOT/'BUILD_ID.json').read_text(encoding='utf-8'))
    except Exception:build_identity={}
    report={'schema':'PA800_PC_VALIDATION_V2','created_utc':datetime.now(timezone.utc).isoformat(),'project':{'version':project_version,'build_id':build_identity.get('build_id'),'build_version':build_identity.get('version'),'build_matches_project':bool(project_version and build_identity.get('version')==project_version)},'system':{'platform':platform.platform(),'python':sys.version,'executable':sys.executable,'machine':platform.machine(),'processor':platform.processor()},'checks':{}}
    try:report['system']['mido']=importlib.metadata.version('mido')
    except Exception:report['system']['mido']=None
    report['checks']['dependencies']=run([sys.executable,'-m','pa800_optimizer.optional_deps','--json'])
    report['checks']['release_audit']=run([sys.executable,str(ROOT/'tools'/'release_audit.py')])
    report['checks']['build_identity']=run([sys.executable,str(ROOT/'tools'/'build_identity.py'),'--check'])
    report['checks']['pytest']=run(release_test_command(out/'pytest_tmp'),timeout=1200)
    report['checks']['tkinter']=tkinter_check()
    if report['system']['mido']:
        try:report['checks']['real_mido']=real_mido_optimizer_checks(out)
        except Exception as exc:report['checks']['real_mido']={'pass':False,'error':repr(exc),'traceback':traceback.format_exc()}
        finally:
            for pattern in ('*.mid','*.report.json'):
                for path in out.glob(pattern):
                    try:path.unlink()
                    except OSError:pass
    else:report['checks']['real_mido']={'pass':False,'error':'Installed Mido distribution was not detected.'}
    report['checks']['wheel']=wheel_check(out)
    try:report['checks']['user_midis']=validate_user_midis(ns.input_folder,out,ns.max_files)
    except Exception as exc:report['checks']['user_midis']={'requested':True,'pass':False,'error':repr(exc),'traceback':traceback.format_exc()}
    json_path=out/'PC_VALIDATION_REPORT.json';json_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['PA800 SMART MAX PC VALIDATION',f'Created: {report["created_utc"]}',f'Version: {project_version}',f'Build ID: {report["project"].get("build_id")}',f'Platform: {report["system"]["platform"]}',f'Python: {sys.version.split()[0]}',f'Mido: {report["system"]["mido"]}','']
    for key,value in report['checks'].items():
        if isinstance(value,dict) and 'returncode' in value:status='PASS' if value['returncode']==0 else 'FAIL'
        elif key=='real_mido':status='PASS' if isinstance(value,list) and all(x.get('pass') for x in value) else 'FAIL'
        elif key=='tkinter':status='PASS' if value.get('import') and value.get('window') else 'WARN'
        elif key=='wheel':status='PASS' if value.get('pass') else 'FAIL'
        elif key=='user_midis':status='SKIP' if not value.get('requested') else ('PASS' if value.get('results') and all(x.get('pass') for x in value.get('results',[])) else 'FAIL')
        else:status='INFO'
        lines.append(f'{key}: {status}')
    if report['checks'].get('user_midis',{}).get('requested'):lines+=['',f'A/B pack: {report["checks"]["user_midis"].get("ab_pack") or "NOT CREATED"}']
    privacy='FULL_PRIVATE_MIDI_INCLUDED' if ns.include_private_midis else 'SAFE_NO_MIDI_CONTENT'
    lines+=['',f'Privacy mode: {privacy}','Pošalji generisani SEND_ME_*.zip. Originalni i optimizovani MIDI sadržaj nije uključen osim uz --include-private-midis.']
    (out/'PC_VALIDATION_SUMMARY.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    archive=create_support_archive(out,base/('SEND_ME_PA800_VALIDATION_'+stamp),ns.include_private_midis)
    print('\n'.join(lines));print('REPORT_FOLDER:',out);print('SEND_THIS_ZIP:',archive)
    user_check=report['checks'].get('user_midis',{});user_ok=(not ns.require_user_midis) or bool(user_check.get('requested') and user_check.get('results') and all(x.get('pass') for x in user_check.get('results',[])))
    critical=[report['project']['build_matches_project'],report['checks']['dependencies']['returncode']==0,report['checks']['release_audit']['returncode']==0,report['checks']['build_identity']['returncode']==0,report['checks']['pytest']['returncode']==0,report['checks']['wheel'].get('pass',False),isinstance(report['checks']['real_mido'],list) and all(x.get('pass') for x in report['checks']['real_mido']),user_ok]
    validation_lock.release()
    return 0 if all(critical) else 1

if __name__=='__main__':raise SystemExit(main())