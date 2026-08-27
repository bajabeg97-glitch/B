#!/usr/bin/env python3
"""Create a blank, versioned Pa800 physical A/B campaign package."""
import argparse,csv,hashlib,json
from pathlib import Path

from pa800_optimizer.analysis.hardware_campaign import MAJOR_FX_ROLES,MAJOR_VOICE_FAMILIES,campaign_template
from pa800_optimizer.profiles.registry import ProfileRegistry


def generate(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);data=campaign_template();data['protocol']['strict_case_ids']=True;registry=ProfileRegistry();dnc=registry.dnc_manual.data['sounds']
    (output/'CAMPAIGN.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    fields=['kind','case_id','blind_order','operator','session_utc','input_midi_sha256','reference_output_sha256','optimized_output_sha256','family','role','address','top1_correct','top3_correct','false_positive','preference','mud_failure','status','stuck_note','wrong_program','lost_articulation','playback_error','comments'];rows=[]
    def case_row(case_id,**values):return {'case_id':case_id,'blind_order':'A_REFERENCE_B_OPTIMIZED' if int(hashlib.sha256(case_id.encode()).hexdigest()[-1],16)%2==0 else 'A_OPTIMIZED_B_REFERENCE',**values}
    for family in MAJOR_VOICE_FAMILIES:
        for index in range(1,31):rows.append(case_row('VOICE_%s_%02d'%(family,index),kind='voice',family=family))
    for role in MAJOR_FX_ROLES:
        for index in range(1,31):rows.append(case_row('FX_%s_%02d'%(role,index),kind='fx',role=role))
    for index,entry in enumerate(dnc,1):
        rows.append(case_row('DNC_%02d'%index,kind='dnc',family=entry.get('family',''),address='%s.%s.%s'%(entry.get('msb'),entry.get('lsb'),entry.get('program')),status='UNKNOWN'))
    with (output/'RESULTS.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    (output/'READ_ME_FIRST.txt').write_text('PA800 HARDWARE A/B CAMPAIGN — 383 SLUCAJA\n\n1. Popuni device identitet u CAMPAIGN.json.\n2. Za svaki red koristi zadani blind_order; slusalac ne smije znati koji je optimized.\n3. Mixer, master FX, kablovi, gain i audio chain moraju ostati identicni.\n4. Popuni operator, session_utc i SHA-256 ulaznog, reference i optimized MIDI fajla.\n5. Popuni rezultate; ne mijenjaj case_id. UNKNOWN nije PASS.\n6. Pokreni EVALUATE_HARDWARE_CAMPAIGN.bat. Kritican playback kvar trajno blokira AUTO.\n',encoding='utf-8')
    return output


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='PA800_HARDWARE_CAMPAIGN');args=parser.parse_args();print(generate(args.output))


if __name__=='__main__':main()