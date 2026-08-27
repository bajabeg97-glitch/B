from pa800_optimizer.neural.corpus_router import build_corpus_manifest, route_authority, validate_corpus_manifest


def test_embedded_factory_gold_corpora_are_complete_and_velocity_isolated():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    manifest = build_corpus_manifest(root/'corpus'/'Factory Styles.zip', root/'corpus'/'Gold DNA.zip')
    audit = validate_corpus_manifest(manifest)
    assert audit['pass'] and audit['counts'] == {'FACTORY': 252, 'GOLD': 182}
    assert route_authority('velocity')['mode'] == 'PROFILE_ONLY'
    assert route_authority('guitar_mode')['factory'] == .90
    assert route_authority('solo_phrase')['gold'] == .85


def test_unknown_feature_fails_closed():
    assert route_authority('invented_feature')['status'] == 'NO_EVIDENCE_NO_CHANGE'
