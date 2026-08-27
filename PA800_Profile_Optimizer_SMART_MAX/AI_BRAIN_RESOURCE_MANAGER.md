# PA800 AI Brain / Resource Manager

`pa800_optimizer.ai_brain.AIResourceBrain` is the central compute governor for BAJA MAX.

## What it controls

- Detects logical CPU count and total/available RAM on Windows/Linux/macOS using `psutil` when present and OS fallbacks otherwise.
- Classifies the machine/workload into `eco`, `balanced`, or `performance`.
- Caps scientific/neural library thread counts (`OMP`, `MKL`, `OpenBLAS`, `NumExpr`, PyTorch).
- Admits or defers optional trained-neural timing/gate inference when free RAM or workload is unsafe.
- Keeps batch concurrency bounded and records the recommended worker limit.
- Runs garbage collection between files on constrained tiers.
- Writes the complete decision, reasons, workload estimate and hardware snapshot into every optimization report.

## Musical safety contract

The Brain owns **compute authority only**. It does not lower velocity/timing/gate strengths, change chords, notes, arrangement, Factory/Gold authority, RX/DNC guards, or BAJA stage sound mappings because a PC is weak. If neural inference is deferred, the deterministic Factory/Gold path remains active.

Default policy is `auto`. `OptimizeConfig.ai_resource_policy` also accepts `eco`, `balanced`, and `performance` for controlled testing.
