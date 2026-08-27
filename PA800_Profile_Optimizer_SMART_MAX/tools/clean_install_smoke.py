"""Build, install and import the wheel without seeing the source checkout."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def run(command,cwd,env=None):
    result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,env=env)
    return {'command':[str(x) for x in command],'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}


def smoke():
    with tempfile.TemporaryDirectory(prefix='pa800-clean-install-') as tmp_name:
        tmp=Path(tmp_name);dist=tmp/'dist';target=tmp/'site';dist.mkdir();target.mkdir()
        build=run([sys.executable,'-m','build','--wheel','--no-isolation','--outdir',str(dist)],ROOT)
        wheels=sorted(dist.glob('*.whl'))
        install=run([sys.executable,'-m','pip','install','--no-deps','--target',str(target),str(wheels[0])],tmp) if wheels else {'returncode':1,'stdout':'','stderr':'wheel_missing'}
        code="import json,pa800_optimizer; from pa800_optimizer.profiles.registry import ProfileRegistry; r=ProfileRegistry(); print(json.dumps({'version':pa800_optimizer.__version__,'profiles':len(r.profiles),'drum_keys':len(r.drum_keys)})); assert len(r.profiles)==542 and len(r.drum_keys)>0"
        env={**os.environ,'PYTHONPATH':str(target),'PYTHONNOUSERSITE':'1'}
        imported=run([sys.executable,'-I','-c',"import sys;sys.path.insert(0,%r);%s"%(str(target),code)],tmp,env) if install['returncode']==0 else {'returncode':1,'stdout':'','stderr':'install_failed'}
        package_files=sorted(str(path.relative_to(target)).replace('\\','/') for path in target.rglob('*') if path.is_file())
        required=('factory_sound_profiles_v1.json','factory_drum_key_profiles_v1.json','factory_velocity_semantics_v2.json')
        data={name:any(path.endswith('/profiles/data/'+name) for path in package_files) for name in required}
        result={'schema':'PA800_CLEAN_INSTALL_SMOKE_V1','build':build,'wheel':wheels[0].name if wheels else None,'install':install,'import':imported,'package_data':data}
        result['pass']=build['returncode']==0 and bool(wheels) and install['returncode']==0 and imported['returncode']==0 and all(data.values())
    shutil.rmtree(ROOT/'build',ignore_errors=True)
    for path in ROOT.glob('*.egg-info'):shutil.rmtree(path,ignore_errors=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--json');args=parser.parse_args(argv);result=smoke();payload=json.dumps(result,indent=2,ensure_ascii=False)
    if args.json:Path(args.json).write_text(payload,encoding='utf-8')
    print(payload);return 0 if result['pass'] else 1


if __name__=='__main__':raise SystemExit(main())