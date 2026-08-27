# Voice & FX Director

## Instrument change gate

Automatska promjena instrumenta prolazi samo ako su istovremeno ispunjeni svi uslovi: trenutna adresa je exact i jednoznačna, kandidat ostaje u dozvoljenoj porodici/ulozi, kandidat je GOOD ili STRONG u najmanje pet Factory stilova, stability je STABLE ili MODERATE, kandidat nije RX/DNC niti konfliktan, te njegov score nadmašuje trenutni Sound za najmanje šest bodova uz dovoljan confidence i margin.

Score kombinuje registar, pitch overlap, velocity centar, trajanje, ulogu, support, Drum Kit key coverage i podudaranje ekspresivnih kontrolera. Bank/Program rewrite se radi samo kada postoji tačno jedan CC0, jedan CC32 i jedan Program Change na kontekstu.

## Contextual FX

FX koristi porodicu Sounda kao početnu tačku, zatim target prilagođava stvarnoj MIDI izvedbi: gustini nota, median trajanju, polifoniji, ulozi, pitch-bendu i aftertouchu. Mijenjaju se samo postojeći CC91 i CC93 događaji. Automation contour ostaje sačuvan, a svaki događaj se može pomjeriti najviše deset vrijednosti.

Factory Style korpus nema CC91/CC93 događaje, zato numerički FX target nije lažno predstavljen kao Factory-naučen. Factory controller baza koristi se za expression/controller affinity pri izboru Sounda, dok je FX target transparentno označen kao expert-rule plus observed-context odluka.