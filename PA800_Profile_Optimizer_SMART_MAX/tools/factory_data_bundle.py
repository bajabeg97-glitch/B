"""Create, verify and atomically restore the canonical Factory data bundle."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

BUNDLE_NAME='PA800_FACTORY_DATA_BUNDLE.zip'
MANIFEST_NAME='PA800_FACTORY_DATA_BUNDLE_MANIFEST.json'
SCHEMA='PA800_FACTORY_DATA_BUNDLE_V1'
DATA_PREFIX=PurePosixPath('pa800_optimizer/profiles/data')


def _sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _data_files(root,names=None):
    data=Path(root)/Path(*DATA_PREFIX.parts);allowed=None if names is None else set(names)
    return [path for path in sorted(data.iterdir()) if path.is_file() and path.stat().st_size>0 and path.suffix.lower() in ('.json','.csv') and (allowed is None or path.name in allowed)]


def create_factory_bundle(root,output,names=None):
    """Write a deterministic ZIP containing Factory data and per-file hashes."""
    root=Path(root);output=Path(output);files=_data_files(root,names)
    if not files:raise RuntimeError('No non-empty Factory data files are available for bundling')
    rows=[]
    for path in files:
        payload=path.read_bytes()
        if path.suffix.lower()=='.json':json.loads(payload.decode('utf-8'))
        rows.append({'path':(DATA_PREFIX/path.name).as_posix(),'bytes':len(payload),'sha256':_sha256_bytes(payload)})
    manifest={'schema':SCHEMA,'files':rows}
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=output.name+'.',suffix='.tmp',dir=output.parent);os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME,json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
            for row,path in zip(rows,files):archive.writestr(row['path'],path.read_bytes())
        os.replace(tmp,output)
    finally:
        try:Path(tmp).unlink()
        except FileNotFoundError:pass
    verify_factory_bundle(output);return {'path':str(output),'files':len(rows),'bytes':output.stat().st_size,'sha256':_sha256_bytes(output.read_bytes())}


def verify_factory_bundle(bundle):
    """Validate schema, safe paths, sizes and hashes without extracting files."""
    bundle=Path(bundle);errors=[]
    try:
        with zipfile.ZipFile(bundle) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)):errors.append('duplicate_archive_member')
            try:manifest=json.loads(archive.read(MANIFEST_NAME).decode('utf-8'))
            except Exception as exc:return {'pass':False,'errors':['manifest:'+repr(exc)],'files':0}
            if manifest.get('schema')!=SCHEMA:errors.append('schema')
            rows=manifest.get('files') if isinstance(manifest.get('files'),list) else []
            for row in rows:
                relative=PurePosixPath(str(row.get('path','')))
                if relative.is_absolute() or '..' in relative.parts or relative.parts[:len(DATA_PREFIX.parts)]!=DATA_PREFIX.parts:errors.append('unsafe_path:'+str(relative));continue
                try:payload=archive.read(relative.as_posix())
                except KeyError:errors.append('missing:'+relative.as_posix());continue
                if len(payload)!=int(row.get('bytes',-1)):errors.append('size:'+relative.as_posix())
                if _sha256_bytes(payload)!=row.get('sha256'):errors.append('sha256:'+relative.as_posix())
                if relative.suffix.lower()=='.json':
                    try:json.loads(payload.decode('utf-8'))
                    except Exception:errors.append('json:'+relative.as_posix())
    except (OSError,zipfile.BadZipFile) as exc:return {'pass':False,'errors':['archive:'+repr(exc)],'files':0}
    return {'pass':not errors,'errors':errors,'files':len(rows)}


def restore_factory_bundle(bundle,root,names=None):
    """Atomically restore selected Factory files after full bundle validation."""
    verification=verify_factory_bundle(bundle)
    if not verification['pass']:raise RuntimeError('Invalid Factory data bundle: %s'%verification['errors'])
    root=Path(root);data=root/Path(*DATA_PREFIX.parts);allowed=None if names is None else set(names);restored=[]
    with zipfile.ZipFile(bundle) as archive:
        manifest=json.loads(archive.read(MANIFEST_NAME).decode('utf-8'))
        for row in manifest['files']:
            relative=PurePosixPath(row['path'])
            if allowed is not None and relative.name not in allowed:continue
            target=data/relative.name;target.parent.mkdir(parents=True,exist_ok=True);payload=archive.read(relative.as_posix())
            fd,tmp=tempfile.mkstemp(prefix='.'+target.name+'.',suffix='.restore',dir=target.parent);os.close(fd)
            try:Path(tmp).write_bytes(payload);os.replace(tmp,target);restored.append(target.name)
            finally:
                try:Path(tmp).unlink()
                except FileNotFoundError:pass
    return sorted(restored)