import hashlib

from tools.compatibility_matrix import evaluate


BUILD='a'*64


def report(file_name='real_song.mid',digest='b'*64,content='song',version='9.9.9',build=BUILD,platform='Windows-10-10.0.19045',python='3.10.14'):
    return {'schema':'PA800_PC_VALIDATION_V2','project':{'version':version,'build_version':version,'build_id':build,'build_matches_project':True},'system':{'platform':platform,'python':python,'mido':'1.3.3'},'checks':{'release_audit':{'returncode':0},'build_identity':{'returncode':0},'pytest':{'returncode':0},'wheel':{'pass':True},'real_mido':[{'pass':True}],'user_midis':{'requested':True,'results':[{'file':file_name,'input_sha256':digest,'content_type':content,'pass':True}]}}}


def entry(data,source='report.json'):
    raw=repr(data).encode();return {'source':source,'digest':hashlib.sha256(raw).hexdigest(),'report':data}


def test_current_real_report_is_eligible_but_matrix_stays_external_until_quota():
    result=evaluate([entry(report())],BUILD,'9.9.9')
    assert result['reports_eligible']==1 and result['counts']['song']==1
    assert result['status']=='EXTERNAL_REQUIRED'


def test_old_build_fixture_and_duplicate_are_rejected():
    old=report(file_name='TEST_fixture.mid',version='2.2.4',build='c'*64)
    first=report();second=report(file_name='copy.mid')
    result=evaluate([entry(old,'old.zip'),entry(first,'one.zip'),entry(second,'two.zip')],BUILD,'9.9.9')
    assert not result['rows'][0]['eligible'] and {'wrong_version','wrong_build_id','fixture_name'}<=set(result['rows'][0]['reasons'])
    assert result['reports_eligible']==1 and result['unique_input_hashes']==1


def test_only_windows_10_11_and_supported_python_minors_count():
    bad=report(platform='Linux-x86_64',python='3.9.18')
    result=evaluate([entry(bad)],BUILD,'9.9.9')
    assert not result['rows'][0]['eligible']
    assert {'unsupported_python','not_windows_10_or_11'}<=set(result['rows'][0]['reasons'])


def test_full_unique_cross_version_matrix_can_pass():
    entries=[];serial=0
    kinds=['song']*100+['style']*100+['kar']*30
    for index,python in enumerate(('3.10.14','3.11.9','3.12.8','3.13.5','3.14.0')):
        data=report(platform='Windows-10-10.0' if index<3 else 'Windows-11-10.0',python=python)
        batch=[]
        for kind in kinds[index::5]:
            serial+=1;digest=f'{serial:064x}';suffix='.kar' if kind=='kar' else '.mid'
            batch.append({'file':f'real_{kind}_{serial}{suffix}','input_sha256':digest,'content_type':kind if kind!='kar' else 'song','pass':True})
        data['checks']['user_midis']['results']=batch;entries.append(entry(data,f'pc_{python}.zip'))
    result=evaluate(entries,BUILD,'9.9.9')
    assert result['status']=='PASS' and result['reports_eligible']==5
    assert result['counts']=={'song':100,'style':100,'kar':30}
    assert result['windows_generations']==['Windows 10','Windows 11']