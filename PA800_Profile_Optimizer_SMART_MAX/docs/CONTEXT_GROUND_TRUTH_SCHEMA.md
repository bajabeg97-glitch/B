# Context Ground Truth — annotation protocol

This file defines the manual evidence required by roadmap phase 2.3. It does
not authorize MIDI mutation.

## Dataset gate

- at least 100 Song, 100 Style and 30 KAR files;
- source stored as a private local identifier or SHA-256, never mandatory MIDI
  content in a validation package;
- every active track/channel receives exactly one function label;
- section ranges are ordered, non-empty and use absolute MIDI ticks;
- ambiguous functions are labeled `UNKNOWN`, not guessed;
- genre, meter and tempo strata must be reported separately.

Allowed track functions are `FOUNDATION_DRUM`, `FOUNDATION_PERC`,
`FOUNDATION_BASS`, `LEAD`, `COUNTER_LINE`, `HARMONIC_COMP`, `PAD_BACKGROUND`,
`RIFF_OSTINATO`, `ORNAMENT_FX` and `UNKNOWN`.

Use `context_ground_truth_template.json` for one file, then run:

```text
python tools/evaluate_context_ground_truth.py REPORT.json TRUTH.json
```

The roadmap gate remains track-function accuracy at least 0.90 and section
boundary F1 at least 0.85. A valid evaluator with no labeled corpus is only
infrastructure; it is not a musical validation result.