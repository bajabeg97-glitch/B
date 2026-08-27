"""Write a content-addressed build identity for the exact source/profile tree."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tomllib


ROOT=Path(__file__).resolve().parents[1]


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def command(*args):
    try:return subprocess.check_output(args,cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except Exception:return ''


def stable_payload():
    project=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']
    source_paths=sorted((ROOT/'pa800_optimizer').rglob('*.py'))
    source_rows=[{'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':sha256(path)} for path in source_paths]
    authority_paths=[]
    for pattern in ('tools/**/*.py','tests/test_*.py','test_support/*.py'):
        authority_paths.extend(ROOT.glob(pattern))
    for name in ('RELEASE_TESTS.txt','requirements-validation.txt','constraints-core.txt','constraints-validation.txt','CI_RELEASE_MATRIX.yml'):
        path=ROOT/name
        if path.is_file():authority_paths.append(path)
    authority_paths.extend(ROOT.glob('*.bat'))
    authority_rows=[{'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':sha256(path)} for path in sorted(set(authority_paths))]
    return {
        'schema':'PA800_BUILD_ID_V1',
        'version':project['version'],
        'git_commit':command('git','rev-parse','HEAD'),
        'source_files':source_rows,
        'release_authority_files':authority_rows,
        'pyproject_sha256':sha256(ROOT/'pyproject.toml'),
        'factory_manifest_sha256':sha256(ROOT/'FACTORY_RELEASE_MANIFEST.json'),
    }


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ns=ap.parse_args(argv)
    stable=stable_payload()
    build_id=hashlib.sha256(json.dumps(stable,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    if ns.check:
        try:recorded=json.loads((ROOT/'BUILD_ID.json').read_text(encoding='utf-8'))
        except Exception as exc:
            print(json.dumps({'pass':False,'error':repr(exc),'computed_build_id':build_id},indent=2));return 1
        passed=recorded.get('build_id')==build_id and recorded.get('version')==stable['version']
        print(json.dumps({'pass':passed,'recorded_build_id':recorded.get('build_id'),'computed_build_id':build_id,'version':stable['version']},indent=2))
        return 0 if passed else 1
    payload={**stable,'build_id':build_id,'created_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'git_tracked_dirty':bool(command('git','status','--porcelain','--untracked-files=no'))}
    (ROOT/'BUILD_ID.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'build_id':build_id,'version':stable['version'],'source_files':len(stable['source_files']),'release_authority_files':len(stable['release_authority_files'])},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
