# MIDI Doctor 0.5

MIDI Doctor je deterministički repair sloj koji radi nad istim, već učitanim MIDI objektom prije muzičke optimizacije. Ne pokreće drugi optimizer i ne nagađa note, akorde, Sound adrese ili aranžman.

Automatski popravlja samo visoko pouzdane strukturne greške:

- Note-Off bez pripadajućeg Note-On događaja;
- Note-On bez završnog Note-Off događaja;
- notu nulte dužine;
- zaglavljeni sustain pedal na kraju trake;
- nedostajući, dupli ili prerano postavljeni End-of-Track;
- nulti tempo, nulti PPQN i nevalidan brojnik time-signature događaja;
- nevalidne data-byte vrijednosti se ne klipuju; fajl se označava `UNRECOVERABLE` jer bi clipping mogao proizvesti lažne note ili velocity 127.

Tok je:

`strict load -> health scan -> repair -> health rescan -> optimizer -> event verifier -> atomic save -> reload -> final verifier`

Svaki report sadrži `midi_repair.before`, listu pojedinačnih `repairs`, `midi_repair.after` i završni `pass`. Ako se strukturni integritet ne može dokazati, output se ne snima.