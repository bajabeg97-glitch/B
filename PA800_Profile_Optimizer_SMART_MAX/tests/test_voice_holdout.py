from tools.voice_holdout import evaluate


def test_voice_holdout_is_explicit_proxy_and_has_family_metrics():
    result=evaluate()
    assert result['schema']=='PA800_VOICE_FACTORY_PROXY_HOLDOUT_V1'
    assert 'not hardware' in result['warning'].lower()
    assert result['profiles']>0 and result['families']
    assert 0<=result['overall_top1_accuracy']<=1
    assert 0<=result['overall_top3_accuracy']<=1