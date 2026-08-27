# PA800 Profile Optimizer SMART MAX 3.4.0-alpha2 — BAJA MAX

## Završeno u ovoj reviziji

- `FACTORY + GOLD MAX` je unaprijeđen u **BAJA MAX — FACTORY + GOLD**.
- Explicitni stage defaulti, samo na BAJA MAX buttonu:
  - DRUM → `120.000.004` — Pop Std. Kit RX
  - BASS → `121.016.033` — Finger Bass DNC
  - RHYTHM GUITAR / CH12 → `121.035.025` — Rhythm Guitar DNC
- PERC / Conga / percussion kanal završno se spušta na **40% velocity**; glavni DRUM kit se ne utišava.
- Stage sound rewrite mijenja samo postojeće CC0/CC32/Program događaje; ne izmišlja nove MIDI strukturalne događaje.
- Neuralni model se **ne trenira ponovo**. Postojeći prihvaćeni model ostaje timing/gate pomoćnik.
- Ispravljen neural apply bug: phrase-aware runtime token sada uključuje `off` i potrebni phrase kontekst, pa više ne pada sa `KeyError: off`.
- Chord pattern generator, phrase doctor i pattern advisor ostaju aktivni iz prethodne Work verzije.

## Validacija

Ciljni regression suite: **52 PASS / 0 FAIL**.
Obuhvaćeni su optimizer, verifier, StyleWorks/style import contract, Factory usage, MIDI Doctor, trained neural application, neural event contract, Factory/Gold routing, BAJA stage profile, chord pattern generator, pattern advisor i phrase doctor.

## Autoritet

- Factory: struktura/sigurnost/profili i velocity.
- Gold: Balkan performance evidence gdje je predviđeno.
- Neural: timing/gate samo uz prihvaćen model; bez retreninga u BAJA MAX toku.
- BAJA MAX: eksplicitni korisnički stage defaulti imaju zadnju riječ za tri navedena sounda i PERC 40%.
