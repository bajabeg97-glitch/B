from __future__ import annotations

import ctypes
import json
import os
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _pid_alive(pid):
    try: pid=int(pid)
    except Exception: return False
    if pid<=0:return False
    if os.name=='nt':
        handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle);return True
        return False
    try:
        os.kill(pid,0);return True
    except PermissionError:return True
    except ProcessLookupError:return False
    except OSError:return False


class OutputLock:
    """Cross-process output lock with recovery from dead-owner lock files."""
    def __init__(self,target):
        target=Path(target)
        self.path=target.with_name(target.name+'.lock')
        self.fd=None

    def _remove_if_stale(self):
        try:data=json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:data={}
        if data.get('host') and data.get('host')!=socket.gethostname():return False
        if _pid_alive(data.get('pid')):return False
        try:self.path.unlink();return True
        except FileNotFoundError:return True

    def acquire(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        for attempt in range(2):
            try:
                self.fd=os.open(str(self.path),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                data={'schema':'PA800_OUTPUT_LOCK_V1','pid':os.getpid(),'host':socket.gethostname(),'created_utc':datetime.now(timezone.utc).isoformat()}
                os.write(self.fd,json.dumps(data).encode('utf-8'));os.fsync(self.fd);os.close(self.fd);self.fd=None
                return self
            except FileExistsError:
                if attempt==0 and self._remove_if_stale():continue
                raise RuntimeError('Output is already being processed: %s' % self.path.with_suffix(''))
        raise RuntimeError('Could not acquire output lock: %s' % self.path)

    def release(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
        try:self.path.unlink()
        except FileNotFoundError:pass

    def __enter__(self):return self.acquire()
    def __exit__(self,*_):self.release()


def temp_path_for(target,suffix='.tmp'):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+target.name+'.',suffix=suffix,dir=str(target.parent));os.close(fd)
    return Path(name)


def commit_artifacts(pairs):
    """Commit prebuilt temp files as one rollback-protected artifact group."""
    pairs=[(Path(tmp),Path(target)) for tmp,target in pairs]
    backups=[];installed=[]
    try:
        for _,target in pairs:
            target.parent.mkdir(parents=True,exist_ok=True)
            backup=None
            if target.exists():
                backup=temp_path_for(target,'.backup');backup.unlink();os.replace(target,backup)
            backups.append((target,backup))
        for tmp,target in pairs:
            os.replace(tmp,target);installed.append(target)
        for _,backup in backups:
            if backup and backup.exists():backup.unlink()
    except Exception:
        for target in installed:
            try:target.unlink()
            except FileNotFoundError:pass
        for target,backup in backups:
            if backup and backup.exists():os.replace(backup,target)
        raise
    finally:
        for tmp,_ in pairs:
            try:tmp.unlink()
            except FileNotFoundError:pass
        for _,backup in backups:
            if backup:
                try:backup.unlink()
                except FileNotFoundError:pass