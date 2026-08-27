# Autonomous Premium R11 — Encoder Runtime Admission

R11 promotes the supplied accepted self-supervised encoder unchanged into `models/encoder.json` and separates historical training acceptance from runtime proposal admission.

## Runtime admission
- confidence >= 0.65: `ALLOW_WITH_FACTORY_VERIFY`
- 0.45 <= confidence < 0.65: `ADVISOR_ONLY`
- confidence < 0.45 or unaccepted/invalid authority flag: `REJECT_TO_FACTORY_GOLD`
- confidence is explicitly an evidence/admission score, not a calibrated probability.
- neural mutation authority is always false.
- allowed outputs: timing, gate only.
- forbidden outputs: velocity, pitch, voice, sound/kit, articulation, FX.

## Bundled model
- source: `encoder_20260826_063405_635129_UTC.json`
- active: `models/encoder.json`
- model digest: `13f5ab0f446212e6a745a452352c70894080c2d3f49d082adce4dd5e3692b28f`
- file SHA256: `02f701bfeff31ff8cdca04dfd0d5d68d9a5f897e63a01fa2d1329ffae22ba0d7`
- runtime confidence: `0.696373`
- runtime mode: `ALLOW_WITH_FACTORY_VERIFY`
- retrained: no
- weights modified: no

## BAJA MAX integration
`enable_autonomous_baja_max()` enables the bundled neural advisor. Normal non-autonomous presets still keep neural application disabled by default. The optimizer resolves the portable bundled model path at runtime.

Every admitted neural timing/gate proposal is routed through Factory/Gold evidence. The `ADVISOR_ONLY` band is additionally attenuated. The model never becomes final mutation authority.

## Regression
Focused combined R11 regression: 87 passed / 0 failed.

Fresh complete-stress evidence is still a separate release gate and is not claimed here.
