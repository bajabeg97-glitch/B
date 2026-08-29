# Status projekta (2026-08-29)

Izvor: union GitHub repo-a [bajabeg97-glitch/B](https://github.com/bajabeg97-glitch/B) i [bajabeg97-glitch/123](https://github.com/bajabeg97-glitch/123), rad na grani `arena/01a04e6d-b`.

Ovaj dokument je **forenzički** — ne pretvara software-only prolaze u hardware/FULL release.

## Šta je projekat

Tri sloja u jednom checkoutu:

| Sloj | Putanja | Namjena |
|---|---|---|
| MIDI core + engine | `core/`, `engine/`, `enhance_my_midi.py` | Lossless MIDI model, I/O, velocity, generatori, auto-enhancer |
| Workstation | `midi_workstation/` | Song analyzer, skeleton, Suno core, dual representation |
| PA800 SMART MAX | `PA800_Profile_Optimizer_SMART_MAX/` | Factory + Gold workstation, GUI, release gateovi |
| Velocity GUI (repo 123) | `midi_velocity_optimizer/` | Samostalni Tk GUI |

## Šta je sada zeleno (ponovljivo lokalno)

Komanda:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests midi_workstation/tests
```

**Rezultat: 39 passed** (uključujući `tests/test_python_syntax.py`).

PA800 safety/optimizer subset (bez GUI, bez fizičkog Pa800, bez complete-stress):

```bash
cd PA800_Profile_Optimizer_SMART_MAX
../.venv/bin/python -m pytest \
  tests/test_verifier.py \
  tests/test_optimizer.py \
  tests/test_rx_guard.py \
  tests/test_config_safety.py \
  tests/test_runtime_safety.py \
  tests/test_preserve_unknown.py \
            tests/test_optional_deps.py \
            tests/test_midi_io_channel_state.py \
            -q
```

**Rezultat: 43 passed.**

CI: `.github/workflows/tests.yml` pokreće core suite i PA800 subset na Python 3.11.

## Šta je dopunjeno u ovom ciklusu

- `core/io.py` — mido `MetaMessage` za `track_name` / `instrument_name` koristi `name=`, ne `text=`.
- `core/models.py` — `MidiProject` ima `active_document`, `ppqn`, `format_type`, `load()`, `save()`.
- Generator/enhancer shimovi: pad `dynamics`, harmony/bass `document`, AutoEnhancer `active_document`.
- `engine/gold_velocity_engine.py` — `corrcoef` samo kad `std > 0`.
- pytest collection: `midi_workstation/tests/test_workstation_core_models.py` (dva `test_core_models.py` se sudaraju).
- `tests/` — modeli, I/O roundtrip, history, analyzer, generatori, velocity, workstation, Hypothesis roundtrip.
- `audit_project.py` — root je direktorij skripte, ne `/workspace`.
- `pa800_optimizer/gui.py` — f-string SyntaxError na PASS log liniji (lomilo `ast.parse` / complete-stress manifest).
- Svi `*.py` u checkoutu sada prolaze `ast.parse` (288 fajlova).

## Šta NIJE zeleno — namjerno ne lažirati

| Gate | Stanje | Zašto |
|---|---|---|
| `tools/release_audit.py` | FAIL | `COMPLETE_STRESS_RESULT.json` je star: `pass=false`, `accounted_functions=69` vs očekivanih 393, `unaccounted_functions=272` vs 0 |
| Complete stress (`tools/run_complete_stress.py`) | nije osvježen | Monolitni run + trace plugin; ne pretvarati lokalni proxy u PASS |
| Hardware / FULL release | BLOCKED / EXTERNAL_REQUIRED | Treba fizički Pa800 A/B (`RESULTS.csv`, campaign folder) |
| Factory ZIP korpusi | nisu u gitu | `factory_sound_profiles_v1.json` (6.4 MB) jeste; ZIP-ovi Factory Styles / Gold DNA ostaju vanjski |
| Širi PA800 pytest (ignore GUI/hardware/complete_stress) | 5 fail | `test_max_completion_audit`, `test_process_certification_runner`, `test_release_audit_passes`, `test_embedded_factory_bundle`, `test_recorded_build_identity` |

Zaključak: **software-certified / safety subset radi.** **HARDWARE_CERTIFIED i FULL release i dalje nisu.**

## Kako nastaviti (sljedeći realni koraci)

1. Pokrenuti `python tools/run_complete_stress.py` na mašini sa vremenom i pytestom (sada GUI parse radi).
2. Ako complete-stress `pass=true` i accounted=total, onda `python tools/release_audit.py`.
3. Hardware: `PA800_HARDWARE_CAMPAIGN` + popunjen `RESULTS.csv` sa fizičkog Pa800 — bez toga gate ostaje BLOCKED.
4. GUI: `PA800_Profile_Optimizer_SMART_MAX/RUN_GUI.bat` (Windows) ili `python -m pa800_optimizer.gui` uz Tk.

## Šta nije rađeno namjerno

- Nije merge-ovan PR #2 as-is (`core/io.py` mora ciljati `core.models`).
- Nije `pip install --user` / `--break-system-packages`.
- Complete-stress i hardware rezultati nisu prepisani da bi audit “prošao”.
