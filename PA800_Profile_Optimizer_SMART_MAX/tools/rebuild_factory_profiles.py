"""Rebuild the NO-DNA Factory profile registry from a Factory Styles ZIP.

This wrapper reuses the pinned research scripts bundled in tools/research, but
runs them inside a temporary workspace so their original /mnt/data research
paths never leak into the installed project.
"""
from __future__ import print_function
import argparse, csv, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from collections import defaultdict, Counter

HERE=Path(__file__).resolve().parent
RESEARCH=HERE/'research'
DATA=HERE.parent/'pa800_optimizer'/'profiles'/'data'

SCRIPTS=[
    'factory_deep_analyze.py',
    'factory_controls_analyze.py',
    'build_factory_profiles.py',
    'build_drum_key_profiles.py',
    'factory_profile_stability.py',
    'factory_element_stability.py',
    'factory_arranger_atoms.py',
]

def patched(src, work, zip_path):
    text=src.read_text(encoding='utf-8')
    # Original research scripts were intentionally frozen against /mnt/data.
    # First relocate generic outputs, then restore the explicit ZIP path.
    text=text.replace('/mnt/data/', str(work).replace('\\','/') + '/')
    text=re.sub(r"^ZIP=.*$", "ZIP=%r" % str(zip_path), text, count=1, flags=re.M)
    return text

def make_summaries(profile_json, outdir):
    raw=json.load(open(str(profile_json),encoding='utf-8'))
    profs=raw['profiles']
    byaddr=defaultdict(set)
    for p in profs:
        i=p['identity']; byaddr[(i['msb'],i['lsb'],i['program'])].add(i['sound'])
    with open(str(outdir/'factory_address_name_conflicts_v1.csv'),'w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerow(['msb','lsb','program','names','status'])
        for a,names in sorted(byaddr.items()):
            if len(names)>1:w.writerow([a[0],a[1],a[2],' | '.join(sorted(names)),'IDENTITY_CONFLICT'])
    fam=defaultdict(lambda:{'profiles':0,'notes':0,'strong':0,'good':0,'rx':0})
    for p in profs:
        i=p['identity']; s=p['support']; d=fam[i.get('org_family','UNKNOWN')]; d['profiles']+=1; d['notes']+=s.get('notes',0); d['strong']+=s.get('grade')=='STRONG'; d['good']+=s.get('grade')=='GOOD'; d['rx']+=bool(i.get('rx_named'))
    with open(str(outdir/'factory_family_summary_v1.csv'),'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['family','profiles','notes','strong','good','rx'])
        for k,v in sorted(fam.items(),key=lambda kv:kv[1]['notes'],reverse=True):w.writerow([k,v['profiles'],v['notes'],v['strong'],v['good'],v['rx']])
    cols=['msb','lsb','program','sound','role','family','notes','styles','grade','v_workmin','v_idealmin','v_center','v_idealmax','v_workmax','key_workmin','key_center','key_workmax','special_pitch_candidates']
    with open(str(outdir/'factory_rx_profiles_v1.csv'),'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for p in profs:
            i=p['identity'];
            if not i.get('rx_named'):continue
            s=p['support'];v=p.get('velocity') or {};k=p.get('key') or {}
            w.writerow({'msb':i['msb'],'lsb':i['lsb'],'program':i['program'],'sound':i['sound'],'role':i.get('role'),'family':i.get('org_family'),'notes':s.get('notes'),'styles':s.get('styles'),'grade':s.get('grade'),'v_workmin':v.get('working_min'),'v_idealmin':v.get('ideal_min'),'v_center':v.get('ideal_center'),'v_idealmax':v.get('ideal_max'),'v_workmax':v.get('working_max'),'key_workmin':k.get('working_min'),'key_center':k.get('ideal_center'),'key_workmax':k.get('working_max'),'special_pitch_candidates':json.dumps(p.get('special_pitch_candidates',[]),separators=(',',':'))})

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('factory_zip', nargs='?', default=str(HERE.parent/'corpus'/'Factory Styles.zip'))
    ap.add_argument('--keep-records',action='store_true')
    ns=ap.parse_args(argv)
    z=Path(ns.factory_zip).resolve()
    if not z.exists():raise SystemExit('Factory ZIP not found: %s' % z)
    DATA.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pa800_factory_') as td:
        work=Path(td)
        for name in SCRIPTS:
            src=RESEARCH/name; dst=work/name; dst.write_text(patched(src,work,z),encoding='utf-8')
            print('[RUN]',name); subprocess.check_call([sys.executable,str(dst)],cwd=str(work))
        # Build the deeper velocity semantic layer from the same retained raw records.
        sem_script=RESEARCH/'build_velocity_semantic_profiles.py'
        sem_out=work/'factory_velocity_semantics_v2.json'
        print('[RUN] build_velocity_semantic_profiles.py')
        subprocess.check_call([sys.executable,str(sem_script),'--records',str(work/'factory_records.ndjson'),'--out',str(sem_out)],cwd=str(work))
        # factory_atomic_max resolves the canonical runtime profile path. Make
        # the freshly rebuilt preliminary products visible before invoking it;
        # otherwise a release containing placeholder files cannot self-heal.
        preliminary=['factory_sound_profiles_v1.json','factory_sound_profiles_v1.csv','factory_drum_key_profiles_v1.json','factory_drum_key_profiles_v1.csv','factory_controller_profiles.json','factory_profile_stability_v1.json','factory_element_profile_stability_v1.json','factory_arranger_atoms_v1.json','factory_velocity_semantics_v2.json']
        for name in preliminary:
            p=work/name
            if p.exists():shutil.copy2(str(p),str(DATA/name))
        atomic_out=work/'research_max'
        print('[RUN] factory_atomic_max.py')
        subprocess.check_call([sys.executable,str(RESEARCH/'factory_atomic_max.py'),'--records',str(work/'factory_records.ndjson'),'--zip',str(z),'--outdir',str(atomic_out)],cwd=str(work))
        outputs=['factory_sound_profiles_v1.json','factory_sound_profiles_v1.csv','factory_drum_key_profiles_v1.json','factory_drum_key_profiles_v1.csv','factory_controller_profiles.json','factory_profile_stability_v1.json','factory_element_profile_stability_v1.json','factory_deep_summary.json','factory_arranger_atoms_v1.json','factory_velocity_semantics_v2.json']
        for name in outputs:
            p=work/name
            if p.exists():shutil.copy2(str(p),str(DATA/name))
        make_summaries(DATA/'factory_sound_profiles_v1.json',DATA)
        runtime_atomic=['factory_atomic_max_summary.json','factory_control_forensics_max.json','factory_technique_candidates_max.csv','factory_analysis_coverage_max.csv']
        for name in runtime_atomic:
            p=atomic_out/name
            if p.exists():shutil.copy2(str(p),str(DATA/name))
        research_dest=HERE.parent/'research_max'
        if research_dest.exists():shutil.rmtree(str(research_dest))
        shutil.copytree(str(atomic_out),str(research_dest))
        if ns.keep_records and (work/'factory_records.ndjson').exists():shutil.copy2(str(work/'factory_records.ndjson'),str(DATA/'factory_records.ndjson'))
    subprocess.check_call([sys.executable,str(HERE/'build_profile_completeness.py')],cwd=str(HERE.parent))
    subprocess.check_call([sys.executable,str(HERE/'build_neural_instrument_profiles.py')],cwd=str(HERE.parent))
    subprocess.check_call([sys.executable,str(HERE/'release_audit.py'),'--write-manifest'],cwd=str(HERE.parent))
    print('Rebuild complete:',DATA)

if __name__=='__main__':main()
