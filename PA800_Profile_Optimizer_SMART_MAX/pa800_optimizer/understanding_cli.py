"""Analysis-only command that explains music without creating an output MIDI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis.context import build_contexts,detect_content_type_details
from .analysis.intent import classify_intents
from .analysis.musical_context import analyze_musical_context
from .analysis.musical_understanding import analyze_musical_understanding
from .analysis.instrument_intent import analyze_instrument_intent
from .analysis.family_intent import analyze_family_intents
from .analysis.section_narrative import analyze_section_narrative
from .core.midi_io import extract_notes,load_midi
from .profiles.registry import ProfileRegistry


def analyze_file(path,content_type='auto'):
    mid=load_midi(path);registry=ProfileRegistry();detection=detect_content_type_details(mid,content_type);resolved=detection['content_type'];contexts=build_contexts(mid,registry,resolved)
    for ctx in contexts.values():
        _profile,status=registry.resolve_identity(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.role);ctx.resolution_status=status
    notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat);context=analyze_musical_context(mid,notes,contexts,resolved);understanding=analyze_musical_understanding(mid,notes,contexts,context);section=analyze_section_narrative(mid,notes,contexts,context,understanding);family=analyze_family_intents(mid,notes,contexts,context,section);intent=analyze_instrument_intent(mid,notes,contexts,context,understanding,family,section)
    return {'schema':'PA800_MUSIC_ANALYSIS_REPORT_V1','input_file':str(path),'content_detection':detection,'musical_context':context,'musical_understanding':understanding,'section_narrative':section,'family_intent':family,'instrument_intent':intent,'mutations':0}


def render_markdown(result):
    """Render a musician-facing explanation without implying edit authority."""
    understanding=result['musical_understanding'];lines=[
        '# Muzičko razumijevanje',
        '',
        f"**Ulaz:** `{Path(result['input_file']).name}`  ",
        f"**Tip sadržaja:** {understanding.get('content_type') or 'UNKNOWN'}  ",
        '**Autoritet:** analiza i prijedlozi; nema MIDI mutacija.',
        '',
        '## Sažetak',
        '',
        understanding.get('musician_summary') or 'Nema dovoljno dokaza za sažetak.',
        '',
        '## Ko nosi muziku?',
        '',
    ]
    narratives=understanding.get('track_narratives',[])
    if narratives:
        for row in narratives:
            lines.append(f"- Track {row['track']}, kanal {row['channel']}: **{row['function']}** — {row['sound']} ({row['family']}); confidence {row['function_confidence']:.2f}. {row['interpretation']}")
    else:lines.append('- UNKNOWN: nisu pronađene muzičke dionice.')
    lines.extend(['','## Melodijski narativ',''])
    melody=understanding.get('melody',{}).get('tracks',[])
    if melody:
        for row in melody:
            motif=', '.join('/'.join(str(value) for value in item['intervals'])+f" ×{item['occurrences']}" for item in row.get('repeated_interval_motifs',[])) or 'nije pouzdano pronađen'
            lines.append(f"- Track {row['track']}, kanal {row['channel']}: {row['contour'].lower().replace('_',' ')}, raspon {row['range_semitones']} polutonova, koraci {row['stepwise_ratio']:.0%}, veliki skokovi {row['large_leap_ratio']:.0%}; ponovljeni motiv: {motif}.")
    else:lines.append('- UNKNOWN: nema dovoljno pouzdane foreground melodije.')
    lines.extend(['','## Harmonija i voice-leading',''])
    harmony=understanding.get('harmony',{});chords=harmony.get('simultaneous_chords',[])
    if chords:
        lines.append('- Opaženi akordi/klasteri: '+', '.join(f"{row['label']}@{row['tick']}" for row in chords[:16])+'.')
    else:lines.append('- UNKNOWN: nema dovoljno simultanih ili blisko arpeđiranih tonova za akordsku oznaku.')
    center=harmony.get('tonal_center',{})
    lines.append(f"- Tonalni centar: **{center.get('name') if center.get('status')=='CANDIDATE' else 'UNKNOWN'}**.")
    voice=harmony.get('voice_leading',[])
    if voice:
        lines.append('- Voice-leading: '+', '.join(f"{row['from_label']}→{row['to_label']} ({row['relationship'].lower()})" for row in voice[:12])+'.')
    lines.extend(['','## Groove',''])
    groove=understanding.get('groove',{}).get('relationships',[])
    if groove:
        for row in groove:lines.append(f"- Bass track {row['bass']['track']} / Drum track {row['drum']['track']}: **{row['relationship']}**, blizu anchoru {row['near_anchor_ratio']:.0%}, median offset {row['median_offset_ticks']} tickova.")
    else:lines.append('- UNKNOWN: nije pronađen dokaziv Drum/Bass odnos.')
    lines.extend(['','## Interakcija i prostor',''])
    relations=understanding.get('interaction',{}).get('relationships',[])
    if relations:
        for row in relations:lines.append(f"- Track {row['a']['track']} ↔ {row['b']['track']}: **{row['relationship']}**, overlap {row['overlap_ratio']:.0%}, alternacija {row['alternation_ratio']:.0%}.")
    else:lines.append('- UNKNOWN: nema dovoljno foreground parova za procjenu prostora ili call–response odnosa.')
    lines.extend(['','## Forma i napetost',''])
    sections=understanding.get('arrangement',{}).get('sections',[])
    if sections:
        for row in sections:lines.append(f"- {row.get('label') or 'Section '+str(row.get('section_index'))}: tension proxy {row.get('tension_proxy',0):.2f}, {row.get('trajectory_from_previous','UNKNOWN').lower()}, {row.get('active_tracks',0)} aktivnih trackova.")
    else:lines.append('- UNKNOWN: sekcijska forma nije pouzdano izdvojena.')
    section_v3=result.get('section_narrative',{})
    lines.extend(['','## Section & Narrative V3',''])
    for row in section_v3.get('sections',[]):lines.append(f"- Sekcija {row['index']}: **{row['label']}**, taktovi {row.get('start_bar') or '?'}–{row.get('end_bar') or '?'}, dokaz {row['evidence_level']}.")
    if not section_v3.get('sections'):lines.append('- UNKNOWN: nema dokazive sekcijske strukture.')
    for row in section_v3.get('transitions',[]):
        if row['relationship']!='START':lines.append(f"- Prijelaz {row['from_section']}→{row['to_section']}: **{row['relationship']}**.")
    lines.extend(['','## Prijedlozi bez AUTO autoriteta',''])
    suggestions=understanding.get('suggestions',[])
    if suggestions:
        for row in suggestions:lines.append(f"- **{row['action']}** — {row['reason']} (confidence {row['confidence']:.2f}).")
    else:lines.append('- Nema prijedloga koji prelaze prag dokaza.')
    lines.extend(['','## Namjera instrumenata V3',''])
    intent=result.get('instrument_intent',{})
    for row in intent.get('track_intents',[]):lines.append(f"- Track {row['track']}, kanal {row['channel']}: **{row['label']}**, confidence {row['confidence']:.2f}; dozvoljeno: {', '.join(row['allowed_actions'])}.")
    if not intent.get('track_intents'):lines.append('- UNKNOWN: nema track namjera.')
    lines.extend(['','## Specijalizirana namjera po porodici',''])
    family=result.get('family_intent',{});family_summary=family.get('summary',{})
    if family_summary.get('classified_notes'):
        for name,count in family_summary.get('by_family',{}).items():lines.append(f'- **{name}**: {count} nota dobilo je specijaliziranu, analyzer-only oznaku.')
        lines.append(f"- Zaštićene zavisnosti: {family_summary.get('protected_rows',0)} redova; primijenjene akcije: 0.")
    else:lines.append('- UNKNOWN: nema podržane Drum/Bass/Guitar/Piano porodice ili nema dovoljno nota.')
    lines.extend(['','## UNKNOWN i granice dokaza',''])
    unknown=understanding.get('uncertainties',[])
    for row in unknown:lines.append(f"- {row['domain']}: {row['reason']}; potrebno: {row['required_action']}.")
    for limit in understanding.get('limits',[]):lines.append(f'- {limit}')
    return '\n'.join(lines)+'\n'


def main(argv=None):
    ap=argparse.ArgumentParser(description='Explain musical structure without modifying MIDI');ap.add_argument('input');ap.add_argument('--content-type',default='auto',choices=['auto','song','style']);ap.add_argument('--report',help='Write complete JSON evidence report');ap.add_argument('--markdown',help='Write readable musician-facing Markdown report');ns=ap.parse_args(argv)
    result=analyze_file(ns.input,ns.content_type);print(result['musical_understanding']['musician_summary'])
    for row in result['musical_understanding']['observations']:print('[%s %.2f] %s'%(row['evidence_level'],row['confidence'],row['statement']))
    for row in result['musical_understanding']['uncertainties']:print('[UNKNOWN]',row['domain'],row['reason'])
    if ns.report:
        Path(ns.report).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print('Report:',ns.report)
    if ns.markdown:
        Path(ns.markdown).write_text(render_markdown(result),encoding='utf-8');print('Musician report:',ns.markdown)
    return 0


if __name__=='__main__':raise SystemExit(main())