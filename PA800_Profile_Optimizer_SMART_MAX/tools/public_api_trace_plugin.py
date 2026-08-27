"""Pytest plugin that records actually executed public API functions."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

from tools.public_api_stress import ROOT,discover


_HITS=set();_INDEX={}


def _profiler(frame,event,arg):
    if event!='call':return
    code=frame.f_code;key=(str(Path(code.co_filename).resolve()),getattr(code,'co_qualname',code.co_name))
    item=_INDEX.get(key)
    if item:_HITS.add(item)


def pytest_sessionstart(session):
    for row in discover():
        path=str((ROOT/row['path']).resolve());_INDEX[(path,row['qualname'])]=row['module']+':'+row['qualname']
    sys.setprofile(_profiler);threading.setprofile(_profiler)


def pytest_sessionfinish(session,exitstatus):
    sys.setprofile(None);threading.setprofile(None);output=os.environ.get('PA800_PUBLIC_API_TRACE_OUT')
    if output:Path(output).write_text(json.dumps({'schema':'PA800_PUBLIC_API_EXECUTION_TRACE_V1','pytest_exitstatus':exitstatus,'hits':sorted(_HITS)},indent=2)+'\n',encoding='utf-8')