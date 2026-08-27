"""Aggregate only current-build, real-Mido, non-fixture PC validation evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
REQUIRED={'song':100,'style':100,'kar':30,'python_versions':5,'windows_generations':2}
FIXTURE_TOKENS=('test_','fixture','synthetic','dummy','sample_test')


def _json_bytes(raw):
    try:return json.loads(raw.decode('utf-8-sig'))
    except Exception:return None


def collect_reports(paths):
    reports=[];seen=set()
    for item in map(Path,paths):
        if not item.exists():continue
        candidates=[item] if item.is_file() else list(item.rglob('PC_VALIDATION_REPORT.json'))+list(item.rglob('SEND_ME*.zip'))
        for path in candidates:
            if path.suffix.lower()=='.zip':
                try:
                    with zipfile.ZipFile(path) as archive:
                        for name in archive.namelist():
                            if not name.endswith('PC_VALIDATION_REPORT.json'):continue
                            raw=archive.read(name);digest=hashlib.sha256(raw).hexdigest()
                            if digest in seen:continue
                            seen.add(digest);data=_json_bytes(raw)
                            if isinstance(data,dict):reports.append({'source':path.as_posix()+'!'+name,'digest':digest,'report':data})
                except (OSError,zipfile.BadZipFile):continue
            elif path.name=='PC_VALIDATION_REPORT.json':
                try:raw=path.read_bytes()
                except OSError:continue
                digest=hashlib.sha256(raw).hexdigest()
                if digest in seen:continue
                seen.add(digest);data=_json_bytes(raw)
                if isinstance(data,dict):reports.append({'source':path.as_posix(),'digest':digest,'report':data})
    return reports


def _returncode_pass(checks,name):return isinstance(checks.get(name),dict) and checks[name].get('returncode')==0


def _version(value):
    match=re.search(r'\b(3\.(?:10|11|12|13|14))\b',str(value or ''))
    return match.group(1) if match else None


def _windows_generation(value):
    text=str(value or '').lower()
    if 'windows-11' in text or 'windows 11' in text:return 'Windows 11'
    if 'windows-10' in text or 'windows 10' in text:return 'Windows 10'
    return None


def _fixture_name(name):
    lowered=Path(str(name or '')).name.lower()
    return any(token in lowered for token in FIXTURE_TOKENS)


def evaluate(entries,expected_build_id,expected_version):
    rows=[];hashes=set();counts={'song':0,'style':0,'kar':0};versions=set();windows=set()
    for entry in entries:
        report=entry.get('report',{});project=report.get('project',{});system=report.get('system',{});checks=report.get('checks',{});reasons=[]
        if report.get('schema')!='PA800_PC_VALIDATION_V2':reasons.append('wrong_schema')
        if project.get('version')!=expected_version or project.get('build_version')!=expected_version:reasons.append('wrong_version')
        if project.get('build_id')!=expected_build_id:reasons.append('wrong_build_id')
        if project.get('build_matches_project') is not True:reasons.append('project_build_mismatch')
        python_version=_version(system.get('python'));windows_generation=_windows_generation(system.get('platform'))
        if not python_version:reasons.append('unsupported_python')
        if not windows_generation:reasons.append('not_windows_10_or_11')
        if not system.get('mido'):reasons.append('missing_mido_distribution')
        for name in ('release_audit','build_identity','pytest'):
            if not _returncode_pass(checks,name):reasons.append(name+'_failed')
        wheel=checks.get('wheel',{});real=checks.get('real_mido');user=checks.get('user_midis',{})
        if not isinstance(wheel,dict) or wheel.get('pass') is not True:reasons.append('wheel_failed')
        if not isinstance(real,list) or not real or not all(row.get('pass') is True for row in real):reasons.append('real_mido_failed')
        results=user.get('results') if isinstance(user,dict) else None
        if not user.get('requested') or not isinstance(results,list) or not results:reasons.append('missing_real_user_batch');results=[]
        accepted_files=[];file_rejections=[];base_valid=not reasons
        for result in results:
            file_name=str(result.get('file') or '');digest=str(result.get('input_sha256') or '').lower();kind='kar' if file_name.lower().endswith('.kar') else str(result.get('content_type') or '').lower()
            file_reasons=[]
            if result.get('pass') is not True:file_reasons.append('verifier_fail')
            if _fixture_name(file_name):file_reasons.append('fixture_name')
            if not re.fullmatch(r'[0-9a-f]{64}',digest):file_reasons.append('missing_input_hash')
            if kind not in ('song','style','kar'):file_reasons.append('unknown_content_type')
            if base_valid and digest in hashes:file_reasons.append('duplicate_input')
            if base_valid and not file_reasons:
                hashes.add(digest);counts[kind]+=1;accepted_files.append({'file':file_name,'kind':kind,'input_sha256':digest})
            elif file_reasons:file_rejections.append({'file':file_name,'reasons':file_reasons})
        if not accepted_files:
            reasons.append('no_unique_real_files')
            reasons.extend(reason for row in file_rejections for reason in row['reasons'])
        eligible=not reasons
        if eligible:
            versions.add(python_version);windows.add(windows_generation)
        rows.append({'source':entry.get('source'),'report_sha256':entry.get('digest'),'eligible':eligible,'reasons':sorted(set(reasons)),'python_version':python_version,'windows_generation':windows_generation,'accepted_files':accepted_files if eligible else [],'file_rejections':file_rejections})
    passed=counts['song']>=REQUIRED['song'] and counts['style']>=REQUIRED['style'] and counts['kar']>=REQUIRED['kar'] and len(versions)>=REQUIRED['python_versions'] and len(windows)>=REQUIRED['windows_generations']
    return {'schema':'PA800_COMPATIBILITY_MATRIX_V1','expected_build_id':expected_build_id,'expected_version':expected_version,'status':'PASS' if passed else 'EXTERNAL_REQUIRED','reports_seen':len(entries),'reports_eligible':sum(row['eligible'] for row in rows),'counts':counts,'python_versions':sorted(versions),'windows_generations':sorted(windows),'unique_input_hashes':len(hashes),'required':REQUIRED,'rows':rows}


def current_identity():
    data=json.loads((ROOT/'BUILD_ID.json').read_text(encoding='utf-8'));return data.get('build_id'),data.get('version')


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('paths',nargs='*');parser.add_argument('--output',default=str(ROOT/'COMPATIBILITY_MATRIX.json'));args=parser.parse_args(argv)
    paths=args.paths or [str(ROOT/'validation_results'),str(ROOT/'prism-uploads')];build_id,version=current_identity();report=evaluate(collect_reports(paths),build_id,version);Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({key:value for key,value in report.items() if key!='rows'},indent=2,ensure_ascii=False));return 0 if report['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())