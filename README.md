# PA800 Profile Optimizer + MIDI Workstation

Cijeli projekat preuzet sa GitHuba:

- [bajabeg97-glitch/B](https://github.com/bajabeg97-glitch/B) — PA800 optimizer, MIDI core, engine, workstation
- [bajabeg97-glitch/123](https://github.com/bajabeg97-glitch/123) — MIDI Velocity Optimizer GUI

## Struktura

| Putanja | Opis |
|---|---|
| `PA800_Profile_Optimizer_SMART_MAX/` | Glavni PA800 Factory + Gold neural workstation (SMART MAX) |
| `core/` | MIDI I/O, modeli, history, instrument i velocity profili |
| `engine/` | Analyzer, velocity engine, auto-enhancer, generatori (bass, gitara, fill, solo, strings) |
| `midi_workstation/` | Song analyzer, dual representation, skeleton engine, Suno core, demo MIDI |
| `midi_velocity_optimizer/` | Samostalni GUI optimizer (repo `123`) |
| `enhance_my_midi.py` | Brzi CLI za enhancement |
| `audit_project.py` | Audit projekta |

## PA800 — brzi start (Windows)

1. Otvori `PA800_Profile_Optimizer_SMART_MAX/`
2. Prvi put: `INSTALL.bat`
3. Zatim: `RUN_GUI.bat`

Arhiva: [PA800 Profile Optimizer BAJA MAX AUTONOMOUS PREMIUM R13 CHECKPOINT](PA800_Profile_Optimizer_BAJA_MAX_AUTONOMOUS_PREMIUM_R13_CHECKPOINT%20%281%29.zip)

Detaljna dokumentacija: [`PA800_Profile_Optimizer_SMART_MAX/README.md`](PA800_Profile_Optimizer_SMART_MAX/README.md)

## MIDI Velocity Optimizer GUI

```bat
cd midi_velocity_optimizer
install.bat
gui.bat
```
