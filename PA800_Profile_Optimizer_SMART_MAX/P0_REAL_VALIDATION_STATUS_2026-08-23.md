# P0 Real Validation status — 23. august 2026.

## Okruženje

- Windows 10 build 19045
- Python 3.14.7, 64-bit
- Mido 1.3.3
- Factory release audit: PASS
- Wheel build i package-data provjera: PASS
- Tkinter prozor: PASS

## Drugi P0 prolaz — verzija 0.7.2

- Stvarni korisnički MIDI/KAR fajlovi: **30/30 PASS**.
- Final event verifier: **30/30 PASS**.
- Real-Mido synthetic/runtime slučajevi: svi PASS, uključujući MIDI Doctor, determinism, Voice/FX Director, Velocity Conductor i stress sa 2.400 nota.
- Prethodna tri null-gate FAIL-a su zatvorena.
- Same-tick Drum Note-On/Off događaji su očuvani; Doctor repairs na 30 fajlova: 0.
- AUTO odluke: 26 `natural`, 4 `preserve`.
- SMART odluke: 4 `apply`, 26 `suggest`.
- Automatske promjene Sound adrese: 0.
- Bounded postojeći CC91/CC93 FX event rewrite: 84 događaja u četiri fajla.
- Normalized velocity median poslije obrade: ukupni median 0.97095; raspon 0.9286–1.0000.
- Najtiši AUTO-preserve primjer je poboljšan sa 0.7551 na 0.9286.
- Warning agregacija je smanjila ranijih 2.125 ponovljenih upozorenja na jedan kontekstualni red.
- Prosječna veličina reporta smanjena je sa približno 4,42 MB na 0,52 MB, odnosno 88,3%.

## Pytest status

Svih **76 release testova je izvršeno i prošlo**, ali je proces vratio exit code 1 nakon testova jer je Windows odbio brisanje zajedničkog `%TEMP%/pytest-of-Baja/pytest-current` linka (`WinError 5`). To nije test niti optimizer FAIL. Validator 0.7.3 koristi vlastiti `--basetemp` unutar validation foldera da ukloni ovu infrastrukturnu grešku.

## Šta P0 još nije dokazao

Software/Windows gate je funkcionalno zatvoren. Hardware/audio gate ostaje otvoren dok se na fizičkom Pa800 ne poslušaju `01_ORIGINAL` i `02_OPTIMIZED` parovi i ne popuni `PA800_AB_SCORE_SHEET.csv`.

Posebno treba poslušati četiri SMART apply slučaja zbog 84 CC91/CC93 promjene, četiri AUTO-preserve slučaja zbog jače velocity normalizacije i Drum fajlove sa same-tick Note-Off događajima.