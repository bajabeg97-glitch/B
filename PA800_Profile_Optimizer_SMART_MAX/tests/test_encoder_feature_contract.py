import copy

from pa800_optimizer.neural.self_supervised_encoder import BASE_FEATURES,PHRASE_FEATURES,validate_encoder_feature_contract


def _model():
    width=len(BASE_FEATURES);hidden=4
    return {'feature_names':list(BASE_FEATURES),'hidden_size':hidden,
            'x_mean':[0.0]*(width*3),'x_std':[1.0]*(width*3),
            'y_mean':[0.0]*width,'y_std':[1.0]*width,
            'w1':[[0.0]*hidden for _ in range(width*3)],'b1':[0.0]*hidden,
            'w2':[[0.0]*width for _ in range(hidden)],'b2':[0.0]*width}


def test_velocity_free_model_shape_is_accepted():
    assert validate_encoder_feature_contract(_model())['pass'] is True


def test_hierarchical_whole_phrase_model_shape_is_accepted():
    model=_model();extra=len(PHRASE_FEATURES);hidden=model['hidden_size']
    model.update({'context':'HIERARCHICAL_WHOLE_PHRASE','phrase_feature_names':list(PHRASE_FEATURES)})
    model['x_mean'] += [0.0]*extra;model['x_std'] += [1.0]*extra;model['w1'] += [[0.0]*hidden for _ in range(extra)]
    audit=validate_encoder_feature_contract(model)
    assert audit['pass'] is True and audit['input_width']==51 and audit['phrase_aware'] is True


def test_stale_36_dimension_model_is_rejected_before_broadcast():
    model=copy.deepcopy(_model());model['x_mean'] += [0.0]*3;model['x_std'] += [1.0]*3
    audit=validate_encoder_feature_contract(model)
    assert audit['pass'] is False and any(row.startswith('x_mean:36!=33') for row in audit['errors'])
