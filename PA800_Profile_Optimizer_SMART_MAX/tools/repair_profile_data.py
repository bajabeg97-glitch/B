"""Restore empty/corrupt runtime profile files from a nearby original/full ZIP."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
try:from tools.factory_data_bundle import BUNDLE_NAME,restore_factory_bundle,verify_factory_bundle
except ModuleNotFoundError:from factory_data_bundle import BUNDLE_NAME,restore_factory_bundle,verify_factory_bundle

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'pa800_optimizer'/'profiles'/'data'
EXPECTED={
    'factory_sound_profiles_v1.json','factory_drum_key_profiles_v1.json','factory_drum_key_profiles_v1.csv',
    'factory_velocity_semantics_v2.json','factory_profile_stability_v1.json',
    'factory_element_profile_stability_v1.json','factory_atomic_max_summary.json',
    'factory_control_forensics_max.json','factory_controller_profiles.json',
    'factory_arranger_atoms_v1.json','factory_technique_candidates_max.csv',
    'factory_analysis_coverage_max.csv','pa800_dnc_manual_registry_v1.json',
}

def valid(path):
    if not path.exists() or path.stat().st_size==0:return False
    if path.suffix.lower()=='.json':
        try:json.loads(path.read_text(encoding='utf-8'))
        except Exception:return False
    return True

def candidates(explicit=None):
    seen=set();out=[]
    places=[ROOT,ROOT.parent,ROOT.parent/'prism-uploads',Path.home()/'Desktop',Path.home()/'Downloads']
    raw=([Path(explicit)] if explicit else [])+[p for base in places if base.exists() for p in base.glob('*.zip')]
    preferred=(BUNDLE_NAME.upper().removesuffix('.ZIP'),'SMART_SOUND_KIT_FX_FULL','SMART_MAX','FACTORY_ATOMIC')
    for p in sorted(raw,key=lambda x:(not any(k in x.name.upper() for k in preferred),x.name)):
        try:key=str(p.resolve()).lower()
        except Exception:continue
        if key not in seen and p.is_file():seen.add(key);out.append(p)
    return out

def restore_from(archive,broken):
    if Path(archive).name==BUNDLE_NAME or verify_factory_bundle(archive).get('pass'):
        return restore_factory_bundle(archive,ROOT,broken)
    restored=[]
    with zipfile.ZipFile(archive) as z:
        members={Path(n).name:n for n in z.namelist() if '/pa800_optimizer/profiles/data/' in n.replace('\\','/') and not n.endswith('/')}
        for name in broken:
            member=members.get(name)
            if not member:continue
            blob=z.read(member)
            if not blob:continue
            if name.lower().endswith('.json'):
                try:json.loads(blob.decode('utf-8'))
                except Exception:continue
            target=DATA/name;target.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix='.'+name+'.',suffix='.repair',dir=str(target.parent));os.close(fd)
            try:Path(tmp).write_bytes(blob);os.replace(tmp,target);restored.append(name)
            finally:
                try:Path(tmp).unlink()
                except FileNotFoundError:pass
    return restored

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--archive');ns=ap.parse_args(argv)
    # Completeness and neural routing catalogs are deterministic derivatives;
    # they are regenerated below and must never make source-archive recovery
    # fail merely because an older archive does not contain them.
    files=sorted(EXPECTED)
    broken=[name for name in files if not valid(DATA/name)]
    bundle_restore=False
    if broken:
        print('[REPAIR] Invalid/empty files:',', '.join(broken),flush=True)
        for archive in candidates(ns.archive):
            try:
                bundle_check=verify_factory_bundle(archive)
                if bundle_check.get('pass'):
                    restored=restore_factory_bundle(archive,ROOT);bundle_restore=True
                else:restored=restore_from(archive,broken)
            except (zipfile.BadZipFile,OSError):continue
            if restored:
                print('[RESTORED]',len(restored),'files from',archive,flush=True)
                broken=[name for name in broken if not valid(DATA/name)]
                if not broken:break
        if broken:
            print('[ERROR] Could not restore:',', '.join(broken))
            print('Pass --archive with the matching PA800 full-source ZIP.')
            return 1
    else:print('[OK] Source Factory profile data is valid.',flush=True)
    commands=[[sys.executable,str(ROOT/'tools'/'release_audit.py'),'--write-manifest']] if bundle_restore else [
        [sys.executable,str(ROOT/'tools'/'build_profile_completeness.py')],
        [sys.executable,str(ROOT/'tools'/'build_neural_instrument_profiles.py')],
        [sys.executable,str(ROOT/'tools'/'release_audit.py'),'--write-manifest']]
    env={**os.environ,'PYTHONPATH':str(ROOT)+(os.pathsep+os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '')}
    for command in commands:
        result=subprocess.call(command,cwd=ROOT,env=env)
        if result:return result
    return 0

if __name__=='__main__':raise SystemExit(main())