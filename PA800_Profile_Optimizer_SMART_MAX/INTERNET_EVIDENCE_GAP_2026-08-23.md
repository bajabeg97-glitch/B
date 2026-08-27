# Službeni Korg internet dokaz koji runtime još ne koristi potpuno

Datum provjere: 23. august 2026.

Autoritet su službeni Korg Pa800 download portal, Owner's Manual, Advanced
Edit OS 2.0, OS 2.0 Upgrade Guide, OS 2.02 Release Notes i službeni
Pa2X/Pa800 Import/Export SMF tutorial.

## Dokaz koji je sada spojen

1. **Marker-separated Style SMF ugovor.** Pa800 OS 2.x traži SMF Format 0,
   kanale 9--16, lowercase `EnCVn` markere, time signature na početku svakog
   CV segmenta i Bank/Program/Expression header. Novi
   `PA800_STYLE_IMPORT_CONTRACT_V1` provjerava minimum i strogi export ugovor,
   bez automatskog prepravljanja fajla.
2. **Style Record event allowlist.** Auditor prepoznaje Note On/Off, Pitch
   Bend, Channel Aftertouch, CC1, CC2, CC10--13, CC64, CC71, CC74,
   CC80--82, Bank Select i Program Change. Nepodržani događaj se prijavljuje,
   ali se ne briše.
3. **OS/Musical Resources identitet.** Hardware kampanja zahtijeva stvarnu
   OS verziju, Musical Resources verziju, SET identitet i audio-chain ID.
   Službeni portal trenutno nudi Pa800 OS 2.03 i Musical Resources 2.03.
4. **Mjerljivi hardware gate.** Dodani su generator i evaluator za najmanje
   30 Voice A/B po glavnoj familiji, 30 FX A/B po ulozi i svih 23 manualnih
   DNC adresa. UNKNOWN nije PASS, a stuck note/wrong program/lost
   articulation/playback error trajno blokira kampanju.

## Dokaz koji je poznat, ali se namjerno ne pretvara u AUTO

1. **Voice Assign Poly/Mono/Hold/Legato i Single Trigger.** Manual definiše
   ponašanje, ali SMF ne serializira stvarni Sound-programming parametar.
2. **Digital Drawbars.** Manual ih definiše kao posebnu Sound strukturu čiji
   se parametri spremaju u Performance. Sam naziv `Drawbars` nije dovoljan za
   automatsko rekonstruisanje drawbara, percussion modea, noisea ili rotaryja.
3. **Grand Piano damper oscilatori.** Oscilatori 10--15 mogu se čuti samo pod
   damperom. Zato se CC64 i pedal gate čuvaju, ali resonance/sample rezultat
   mora biti potvrđen audio testom.
4. **Drum Kit velocity layers i Single Trigger.** Manual dokazuje da slojevi i
   overlap pravilo postoje, ali MIDI ne otkriva tačan sample/layer mapping.
5. **DNC Cycle/Random i controller triggeri.** Pragovi CC1/CC2=64 i
   Aftertouch=90 jesu dokumentovani. Odabrani OSC/multisample rezultat nije
   dokaziv iz SMF-a; Cycle/Random ostaje preserve.
6. **Insert/Master FX arhitektura.** Korg tutorial dokumentuje signalni tok i
   Wet/Dry/Send postavke, ali ne daje dokazanu SET/SysEx serializacijsku shemu.
   Zato ostaje recommendation-only.

## Sljedeći dokaz

Pokrenuti `tools/create_hardware_campaign.py`, popuniti generisani paket na
fizičkom Pa800 i provjeriti ga sa `tools/evaluate_hardware_campaign.py`.
Prazan template ili UNKNOWN rezultat ne daje E3 autoritet.