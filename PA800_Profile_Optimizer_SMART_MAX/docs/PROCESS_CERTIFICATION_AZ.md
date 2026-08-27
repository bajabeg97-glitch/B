# A–Z strukturna pokrivenost procesa

`tools/run_process_certification.py` gradi paket pokrivenosti toka, od SMF
preflighta do finalnog authority gatea. Svaka od 26 A–Z faza ima najmanje jedan
pozitivni i jedan negativni MIDI/KAR scenario, te vezan pozitivan i negativan
automatizovani test.

Pokretanje:

```text
python tools/run_process_certification.py PA800_Process_Certification_AZ
```

Paket sadrži 52 deterministička standardna SMF/KAR fajla, bez privatnog
PKL0/pickle dodatka, SHA-256 manifest, A–Z coverage matricu, rezultat pytest
prolaza i Factory release audita. `PASS` dokazuje strukturnu pokrivenost i
registraciju pozitivnih/negativnih testova. Ne dokazuje da je svaki fixture
prošao cijeli optimizer tok i ne zamjenjuje stvarni Windows/Mido, Pa800 DNC/FX
ni audio A/B dokaz.