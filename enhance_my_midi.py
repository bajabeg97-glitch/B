"""
BRZI TEST: AUTO ENHANCER
Učitaj jednostavan MIDI i pretvori ga u full bend.
"""

from engine.auto_enhancer import run_auto_enhance
import os

# Kreiraj lažni jednostavni MIDI za test ako ne postoji
def create_dummy_input():
    from core.models import MidiProject, MidiDocument, MidiTrack, ProgramEvent, NoteEvent
    
    project = MidiProject()
    doc = MidiDocument(ppqn=480)
    project.document = doc  # Postavi aktivni document
    
    # Track 1: Jednostavna melodija (Solo)
    track = MidiTrack(track_index=0)
    track.name = "Solo Melody"
    track.channel = 0
    doc.add_track(track)
    
    # Dodaj Program Change ručno kao event
    pc_event = ProgramEvent(absolute_tick=0, channel=0, program=80)
    track.add_event(pc_event)
    
    # Dodaj nekoliko nota (C major arpeggio) - ručno kreiraj NoteEvent
    notes = [60, 64, 67, 72, 67, 64]
    tick = 0
    for note in notes:
        note_on = NoteEvent(
            absolute_tick=tick,
            channel=0,
            pitch=note,
            velocity=90,
            duration_ticks=480
        )
        note_on.track_index = 0
        track.add_event(note_on)
        tick += 480
        
    project.active_document = doc
    project.save("test_simple_solo.mid")
    print("✅ Kreiran testni fajl: test_simple_solo.mid (samo solo melodija)")

if __name__ == "__main__":
    input_file = "test_simple_solo.mid"
    output_file = "test_full_band_result.mid"
    
    if not os.path.exists(input_file):
        print("🛠️  Kreiram jednostavan testni MIDI...")
        create_dummy_input()
    
    print("\n🚀 POKREĆEM AUTO ENHANCER NA TVOM FAJLU...")
    print("="*40)
    
    try:
        run_auto_enhance(input_file, output_file)
        print("\n" + "="*40)
        print(f"🎉 USPJEH! Otvori '{output_file}' i slušaj razliku!")
        print("Sada imaš Solo + Harmoniju + Gitaru + Pad + Fill-ove.")
    except Exception as e:
        print(f"\n❌ GREŠKA: {e}")
        print("Provjeri da li su svi generatori ispravno implementirani.")
