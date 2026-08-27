"""Static release guard against reintroducing known direct mutation bypasses."""
from pathlib import Path

FORBIDDEN_OPTIMIZER_SNIPPETS={
    'direct_doctor_repair':'repair_midi(mid)',
    'direct_legacy_fx_apply':'apply_fx_sends(mid,ctx,rec',
    'direct_mix_fx_director':'run_mix_fx_director(mid,',
    'direct_velocity_projector':'def _project_cumulative_velocity_budget',
}

def audit_optimizer_transaction_bypasses(path=None):
    path=Path(path) if path else Path(__file__).with_name('optimizer.py')
    text=path.read_text(encoding='utf-8')
    hits=[{'id':key,'snippet':snippet} for key,snippet in FORBIDDEN_OPTIMIZER_SNIPPETS.items() if snippet in text]
    return {'schema':'PA800_TRANSACTION_BYPASS_GUARD_V1','path':str(path),'forbidden':len(FORBIDDEN_OPTIMIZER_SNIPPETS),'hits':hits,'pass':not hits}
