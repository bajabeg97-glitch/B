from pa800_optimizer.agents import _AGENT_SPECS,_run_agent_mesh,_valid_agent_mesh
from pa800_optimizer.config import OptimizeConfig


def _mesh():
    return _run_agent_mesh(OptimizeConfig.for_mode('live'),{'summary':{'sections':2}},{'observations':[],'uncertainties':[]},{'summary':{'sections':2}},{'summary':{'protected_rows':0}},{'summary':{'unknown_tracks':0}})


def test_codex_and_chatgpt_agents_are_analysis_only_and_deterministic():
    first=_mesh();second=_mesh()
    assert {row['agent_id'] for row in _AGENT_SPECS}=={'codex_song_auditor','chatgpt_musical_critic'}
    assert first==second and _valid_agent_mesh(first)
    assert first['authority_granted'] is False and first['mutations']==0 and first['applied_actions']==0
    assert all(row['allowed_mutation_classes']==[] and row['requested_action'] in ('SUGGEST','PRESERVE') for row in first['proposals'])


def test_agent_mesh_rejects_hidden_mutation_authority():
    mesh=_mesh();mesh['proposals'][0]['authority_granted']=True
    assert not _valid_agent_mesh(mesh)