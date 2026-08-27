import json

from tools.final_release_gate import evaluate_final_gate


def _write(root,name,data):(root/name).write_text(json.dumps(data),encoding='utf-8')


def test_final_gate_distinguishes_software_from_physical_hardware(tmp_path):
    _write(tmp_path,'BUILD_ID.json',{'build_id':'abc'});_write(tmp_path,'FACTORY_RELEASE_MANIFEST.json',{'errors':[]});_write(tmp_path,'COMPLETE_STRESS_RESULT.json',{'pass':True});_write(tmp_path,'NEURAL_FORENSIC_REGRESSION_RESULT.json',{'pass':True,'cases':14,'model_acceptance':{'allowed_outputs':['timing','gate'],'authority_granted':False}})
    pending=evaluate_final_gate(tmp_path);assert pending['pass'] and pending['release_class']=='SOFTWARE_CERTIFIED_HARDWARE_PENDING' and not pending['hardware_auto_authority']
    hardware=tmp_path/'hardware.json';_write(tmp_path,'hardware.json',{'pass':True,'gates':{'all':True}});complete=evaluate_final_gate(tmp_path,hardware);assert complete['release_class']=='HARDWARE_CERTIFIED' and complete['hardware_auto_authority']