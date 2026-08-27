# Velocity Conductor 0.7

Velocity Conductor ne postavlja svim instrumentima isti MIDI velocity. Za svaki Sound, Drum Kit key ili poznatu GM porodicu određuje vlastiti normalni centar iz Factory profila.

Tok je:

`exact Sound/Element/CV ili Kit+Key profil -> ideal velocity center -> normalized note ratio -> context median correction -> p05/p95 safety -> audit`

Time Piano može imati normalni centar 89, drugi Bass ili Brass drugačiji centar, a Drum Kit svaki ključ vlastiti centar. Fajlovi se ne porede međusobno: svi se nezavisno dovode prema istom dokaznom profilu instrumenta, pa tihi i preglasni ulazi završavaju u sličnom perceptivnom koridoru.

Korekcija pomjera cijeli dinamički oblik konteksta, umjesto da sve note postavi na jednu vrijednost. RX/DNC zaštićene note, identitetni konflikti i potpuno nepoznati instrumenti ostaju netaknuti.