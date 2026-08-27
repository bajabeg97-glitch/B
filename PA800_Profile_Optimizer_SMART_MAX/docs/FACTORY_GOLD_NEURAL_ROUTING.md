# Factory + Gold neural evidence routing

Embedded corpora:

- `corpus/Factory Styles.zip`: 252 PA800 Factory style-export MIDI files.
- `corpus/Gold DNA.zip`: 182 Gold live-performance MIDI files.

Run `BUILD_FACTORY_GOLD_CORPUS.bat` to rebuild and certify
`corpus/FACTORY_GOLD_CORPUS_MANIFEST.json`.

Factory is the PA800 arranger-grammar and safety authority. Gold is Balkan
performance evidence. The neural layer analyzes and ranks candidates only;
deterministic engines apply approved changes and the verifier proves the
invariants. Unknown evidence fails closed.

Velocity is isolated completely: it is neither a neural input nor a neural
output. Newly proposed pattern events carry a musical function label; the
existing deterministic velocity profile engines assign the final velocity.

Feature-specific weights and veto modes are defined in
`pa800_optimizer/neural/corpus_router.py`, not hidden inside model weights.
