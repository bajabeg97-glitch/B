import json,os
from pathlib import Path
from unittest.mock import patch

import pytest

from pa800_optimizer.runtime_safety import OutputLock,commit_artifacts,temp_path_for


def test_stale_lock_is_recovered(tmp_path):
    target=tmp_path/'out.mid';lock=target.with_name(target.name+'.lock')
    lock.write_text(json.dumps({'pid':99999999,'host':__import__('socket').gethostname()}),encoding='utf-8')
    with OutputLock(target):assert lock.exists()
    assert not lock.exists()


def test_live_lock_blocks_duplicate_process(tmp_path):
    target=tmp_path/'out.mid'
    with OutputLock(target):
        with pytest.raises(RuntimeError):OutputLock(target).acquire()


def test_artifact_group_rolls_back_on_second_replace(tmp_path):
    a=tmp_path/'a.mid';b=tmp_path/'a.json';a.write_text('old-a');b.write_text('old-b')
    ta=temp_path_for(a);tb=temp_path_for(b);ta.write_text('new-a');tb.write_text('new-b')
    import pa800_optimizer.runtime_safety as rs
    real=rs.os.replace;calls={'n':0}
    def failing(src,dst):
        calls['n']+=1
        if calls['n']==4:raise OSError('simulated second-artifact failure')
        return real(src,dst)
    with patch.object(rs.os,'replace',side_effect=failing):
        with pytest.raises(OSError):commit_artifacts([(ta,a),(tb,b)])
    assert a.read_text()=='old-a';assert b.read_text()=='old-b'


def test_artifact_group_commits_together(tmp_path):
    a=tmp_path/'a.mid';b=tmp_path/'a.json';ta=temp_path_for(a);tb=temp_path_for(b)
    ta.write_text('new-a');tb.write_text('new-b');commit_artifacts([(ta,a),(tb,b)])
    assert a.read_text()=='new-a';assert b.read_text()=='new-b'