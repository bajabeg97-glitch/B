# BAJA MAX 3.5.0-alpha1 — AI Resource Brain

Added a central `AIResourceBrain` compute-governor layer.

- AUTO/ECO/BALANCED/PERFORMANCE resource tiers.
- Cross-platform CPU/RAM detection with psutil + OS fallbacks.
- Per-file workload scoring.
- OMP/MKL/OpenBLAS/NumExpr/PyTorch thread caps.
- Neural timing/gate admission guard under low-memory/high-load conditions.
- Deterministic Factory/Gold fallback when neural inference is deferred.
- Resource decisions and reasons written into workstation/report output.
- GUI `[AI BRAIN]` runtime log line.
- Compute authority is isolated from musical authority: no chord/note/form/BAJA-stage changes from resource pressure.
