from pa800_optimizer.analysis.context_ground_truth import evaluate_context_prediction,validate_ground_truth


def truth():
    return {'schema':'PA800_CONTEXT_GROUND_TRUTH_V1','content_type':'song','tracks':[{'track':0,'channel':1,'function':'LEAD'},{'track':1,'channel':10,'function':'FOUNDATION_DRUM'}],'sections':[{'start_tick':0,'end_tick':768,'label':'INTRO'},{'start_tick':768,'end_tick':1536,'label':'VERSE'}]}


def report(second_function='FOUNDATION_DRUM',boundary=768):
    return {'musical_context':{'track_functions':[{'track':0,'channel':1,'function':'LEAD','confidence':.9},{'track':1,'channel':10,'function':second_function,'confidence':.9}],'sections':[{'start_tick':0,'end_tick':boundary,'label':'INTRO'},{'start_tick':boundary,'end_tick':1536,'label':'VERSE'}]}}


def test_valid_ground_truth_and_perfect_prediction_pass():
    assert validate_ground_truth(truth())['pass']
    result=evaluate_context_prediction(report(),truth(),boundary_tolerance_ticks=24)
    assert result['pass'] and result['track_function']['accuracy']==1.0 and result['section_boundaries']['f1']==1.0


def test_wrong_function_and_boundary_fail_roadmap_gates():
    result=evaluate_context_prediction(report('HARMONIC_COMP',1200),truth(),boundary_tolerance_ticks=24)
    assert not result['pass']
    assert result['track_function']['accuracy']==.5
    assert result['section_boundaries']['f1']==0.0


def test_invalid_labels_are_rejected_without_guessing():
    bad=truth();bad['tracks'][0]['function']='MAGIC_SOLO';bad['sections'][0]['end_tick']=0
    validation=validate_ground_truth(bad)
    assert not validation['pass'] and len(validation['errors'])==2