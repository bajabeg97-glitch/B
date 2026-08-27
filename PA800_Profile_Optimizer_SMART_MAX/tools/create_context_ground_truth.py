"""Create a human-editable section/function labeling sheet from real MIDI files."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from pa800_optimizer.analysis.context import build_contexts,detect_content_type_details
from pa800_optimizer.analysis.intent import classify_intents
from pa800_optimizer.analysis.musical_context import analyze_musical_context
from pa800_optimizer.core.midi_io import extract_notes,load_midi
from pa800_optimizer.profiles.registry import ProfileRegistry


def generate(input_folder,output_csv,limit=100):
    folder=Path(input_folder);registry=ProfileRegistry();rows=[];section_rows=[]
    files=sorted([p for p in folder.iterdir() if p.suffix.lower() in ('.mid','.midi','.kar')])[:limit]
    for path in files:
        mid=load_midi(str(path));detection=detect_content_type_details(mid,'auto');contexts=build_contexts(mid,registry,detection['content_type']);notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat);analysis=analyze_musical_context(mid,notes,contexts,detection['content_type'])
        for row in analysis['track_functions']:
            rows.append({'file':path.name,'content_type':detection['content_type'],'track':row['track'],'channel':row['channel'],'role':row['role'],'family':row['family'],'sound':row['sound'],'predicted_function':row['function'],'prediction_confidence':row['confidence'],'evidence_level':row['evidence_level'],'human_function':'','correct_yes_no':'','comments':''})
        for section in analysis['sections']:
            section_rows.append({'file':path.name,'section_index':section['index'],'start_tick':section['start_tick'],'end_tick':section['end_tick'],'start_bar':section.get('start_bar'),'end_bar':section.get('end_bar'),'predicted_section':section['label'],'prediction_confidence':section['confidence'],'human_section':'','correct_yes_no':'','comments':''})
    output=Path(output_csv);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',encoding='utf-8-sig',newline='') as stream:
        fields=list(rows[0]) if rows else ['file','human_function','comments'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    sections_path=output.with_name(output.stem+'_SECTIONS.csv')
    with sections_path.open('w',encoding='utf-8-sig',newline='') as stream:
        fields=list(section_rows[0]) if section_rows else ['file','human_section','comments'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(section_rows)
    manifest=output.with_suffix('.manifest.json');manifest.write_text(json.dumps({'schema':'PA800_CONTEXT_GROUND_TRUTH_TEMPLATE_V1','input_folder':str(folder),'files':len(files),'track_rows':len(rows),'section_rows':len(section_rows),'track_csv':output.name,'section_csv':sections_path.name},indent=2,ensure_ascii=False),encoding='utf-8')
    return output,sections_path


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('input_folder');ap.add_argument('--output',default='MUSICAL_CONTEXT_GROUND_TRUTH.csv');ap.add_argument('--limit',type=int,default=100);ns=ap.parse_args(argv);a,b=generate(ns.input_folder,ns.output,ns.limit);print('TRACK_SHEET:',a);print('SECTION_SHEET:',b)


if __name__=='__main__':main()