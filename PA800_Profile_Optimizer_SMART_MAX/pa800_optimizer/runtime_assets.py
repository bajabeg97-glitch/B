"""Runtime immutability guard with exact rollback for canonical assets."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile


class _RuntimeAssetGuard:
    def __init__(self,data_dir,active_model=None):
        paths=sorted(Path(data_dir).glob('*.json'))
        if active_model:paths.append(Path(active_model))
        self._paths=tuple(dict.fromkeys(path.resolve() for path in paths))
        self._before={path:self._snapshot(path) for path in self._paths}

    @staticmethod
    def _fingerprint(path):
        try:
            stat=path.stat();return (True,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
        except FileNotFoundError:return (False,0,0,0)

    @classmethod
    def _snapshot(cls,path):
        fingerprint=cls._fingerprint(path)
        return {'fingerprint':fingerprint,'content':path.read_bytes() if fingerprint[0] else None,'mode':path.stat().st_mode if fingerprint[0] else None}

    @staticmethod
    def _restore(path,snapshot):
        content=snapshot['content']
        if content is None:
            try:path.unlink()
            except FileNotFoundError:pass
            return
        path.parent.mkdir(parents=True,exist_ok=True)
        handle=tempfile.NamedTemporaryFile(prefix='.pa800-asset-rollback-',suffix='.tmp',dir=path.parent,delete=False)
        temporary=Path(handle.name)
        try:
            with handle:
                handle.write(content);handle.flush();os.fsync(handle.fileno())
            if snapshot['mode'] is not None:os.chmod(temporary,snapshot['mode'])
            os.replace(temporary,path)
        finally:
            try:temporary.unlink()
            except FileNotFoundError:pass

    def assert_unchanged(self):
        changed=[path for path in self._paths if self._fingerprint(path)!=self._before[path]['fingerprint']]
        if changed:
            restored=[];failed=[]
            for path in changed:
                try:self._restore(path,self._before[path]);restored.append(str(path))
                except Exception as exc:failed.append('%s: %r'%(path,exc))
            detail='; restored='+', '.join(restored)
            if failed:detail+='; rollback_failed='+', '.join(failed)
            raise RuntimeError('RUNTIME_ASSET_IMMUTABILITY_VIOLATION'+detail)
        return {'pass':True,'files':len(self._paths),'canonical_json_read_only':True,'active_neural_model_read_only':True}