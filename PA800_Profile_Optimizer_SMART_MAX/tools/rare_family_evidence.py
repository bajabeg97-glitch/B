"""Compute the fail-closed evidence conclusion for rare instrument families."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pa800_optimizer.instruments.policies import policy_for


ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'pa800_optimizer'/'profiles'/'data'
RARE_FAMILIES=('SYNTH_LEAD','CHROMATIC_PERC','MALLET','PLUCK','ETHNIC','OTHER_ACC','OTHER')
PERMANENT_PRESERVE=('SFX','SYNTH_FX')


def _norm(value):return ' '.join(str(value or '').lower().split())


def evaluate(sound_data=None,stability_data=None):
    if sound_data is None:sound_data=json.loads((DATA/'factory_sound_profiles_v1.json').read_text(encoding='utf-8'))
    if stability_data is None:stability_data=json.loads((DATA/'factory_profile_stability_v1.json').read_text(encoding='utf-8'))
    stability={}
    for row in stability_data.get('profiles',[]):
        identity=row.get('identity',{});key=(identity.get('msb'),identity.get('lsb'),identity.get('program'),_norm(identity.get('sound')));stability[key]=str(row.get('stability','UNKNOWN')).upper()
    counts=Counter();eligible=[]
    for profile in sound_data.get('profiles',[]):
        identity=profile.get('identity',{});family=str(identity.get('org_family') or 'UNKNOWN').upper()
        if family not in RARE_FAMILIES:continue
        support=profile.get('support',{});grade=str(support.get('grade','UNKNOWN')).upper();key=(identity.get('msb'),identity.get('lsb'),identity.get('program'),_norm(identity.get('sound')));state=stability.get(key,'UNKNOWN')
        counts[family]+=1
        if grade in ('GOOD','STRONG') and state in ('STABLE','MODERATE'):
            eligible.append({'family':family,'address':[identity.get('msb'),identity.get('lsb'),identity.get('program')],'sound':identity.get('sound'),'grade':grade,'stability':state,'styles':support.get('styles'),'notes':support.get('notes')})
    policy_checks={family:bool(policy_for(family).get('exact_only')) for family in RARE_FAMILIES}
    preserve_checks={family:bool(policy_for(family).get('protected')) and not any(policy_for(family).get(name) for name in ('velocity','timing','gate')) for family in PERMANENT_PRESERVE}
    closed=not eligible and all(policy_checks.values()) and all(preserve_checks.values())
    return {
        'schema':'PA800_RARE_FAMILY_EVIDENCE_V1',
        'authority_granted':False,
        'profile_counts':{family:counts.get(family,0) for family in RARE_FAMILIES},
        'eligible_auto_profiles':eligible,
        'exact_only_policy_checks':policy_checks,
        'permanent_preserve_checks':preserve_checks,
        'status':'CLOSED_PRESERVE_NO_ELIGIBLE_PROFILE' if closed else 'OPEN_REVIEW_REQUIRED',
        'warning':'Eligibility is a software evidence precondition, not audible Pa800 quality proof.',
    }


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(DATA/'rare_family_evidence_v1.json'));args=parser.parse_args(argv)
    report=evaluate();Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(report,indent=2,ensure_ascii=False));return 0 if report['status']=='CLOSED_PRESERVE_NO_ELIGIBLE_PROFILE' else 1


if __name__=='__main__':raise SystemExit(main())