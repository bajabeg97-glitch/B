"""Central AI/resource brain for deterministic PA800 optimization.

The brain owns *compute authority*, not musical authority.  It can cap CPU
threads, defer optional neural inference and trim advisory-only analysis when
resources are scarce, but it never changes the Factory/Gold musical target,
note content, harmony, or the user's explicit BAJA stage mapping.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
import gc
import os
import platform
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResourceSnapshot:
    logical_cpus: int
    total_memory_mb: int
    available_memory_mb: int
    available_ratio: float
    platform: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrainDecision:
    schema: str
    tier: str
    max_cpu_threads: int
    max_batch_workers: int
    neural_allowed: bool
    advisory_level: str
    gc_between_files: bool
    estimated_cost: float
    note_count: int
    context_count: int
    input_bytes: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out['reasons'] = list(self.reasons)
        return out


def _memory_snapshot() -> tuple[int, int, str]:
    """Return total/available MiB using optional psutil, then OS fallbacks."""
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        return max(0, int(vm.total // (1024 * 1024))), max(0, int(vm.available // (1024 * 1024))), 'psutil'
    except Exception:
        pass

    if os.name == 'nt':
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            status = MEMORYSTATUSEX(); status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys // (1024 * 1024)), int(status.ullAvailPhys // (1024 * 1024)), 'windows_api'
        except Exception:
            pass

    try:
        page = int(os.sysconf('SC_PAGE_SIZE')); pages = int(os.sysconf('SC_PHYS_PAGES'))
        total = int(page * pages // (1024 * 1024))
        avail_pages = int(os.sysconf('SC_AVPHYS_PAGES'))
        avail = int(page * avail_pages // (1024 * 1024))
        return total, avail, 'sysconf'
    except Exception:
        return 0, 0, 'unknown'


def resource_snapshot() -> ResourceSnapshot:
    cpus = max(1, int(os.cpu_count() or 1))
    total, available, source = _memory_snapshot()
    ratio = (available / total) if total > 0 else 1.0
    return ResourceSnapshot(cpus, total, available, round(max(0.0, min(1.0, ratio)), 4), platform.system() or os.name, source)


class AIResourceBrain:
    """Adaptive compute governor shared by optimizer and GUI workers."""

    SCHEMA = 'PA800_AI_RESOURCE_BRAIN_V1'

    def __init__(self, policy: str = 'auto'):
        self.policy = str(policy or 'auto').lower()
        if self.policy not in {'auto', 'eco', 'balanced', 'performance'}:
            raise ValueError('Unknown AI resource policy: %s' % policy)

    def decide(self, *, input_path: str | os.PathLike | None = None, note_count: int = 0,
               context_count: int = 0, neural_requested: bool = False,
               snapshot: ResourceSnapshot | None = None) -> BrainDecision:
        snap = snapshot or resource_snapshot()
        size = 0
        if input_path:
            try: size = int(Path(input_path).stat().st_size)
            except OSError: size = 0
        notes = max(0, int(note_count)); contexts = max(0, int(context_count))
        # Normalized workload. MIDI is small by bytes; note/event count dominates.
        cost = (notes / 12000.0) + (contexts / 48.0) + (size / (8 * 1024 * 1024))

        if self.policy == 'auto':
            if (snap.total_memory_mb and snap.total_memory_mb < 4096) or snap.logical_cpus <= 2 or snap.available_ratio < 0.18:
                tier = 'eco'
            elif (snap.total_memory_mb and snap.total_memory_mb < 8192) or snap.logical_cpus <= 4 or snap.available_ratio < 0.32:
                tier = 'balanced'
            else:
                tier = 'performance'
        else:
            tier = self.policy

        if tier == 'eco':
            threads, workers, advisory = 1, 1, 'essential'
        elif tier == 'balanced':
            threads, workers, advisory = max(1, min(2, snap.logical_cpus - 1 if snap.logical_cpus > 1 else 1)), 1, 'standard'
        else:
            threads = max(1, min(4, snap.logical_cpus - 1 if snap.logical_cpus > 1 else 1))
            workers, advisory = max(1, min(2, snap.logical_cpus // 4 or 1)), 'full'

        reasons = [f'policy={self.policy}', f'tier={tier}', f'cpus={snap.logical_cpus}',
                   f'available_memory_mb={snap.available_memory_mb}', f'available_ratio={snap.available_ratio:.3f}',
                   f'estimated_cost={cost:.3f}']

        neural_allowed = bool(neural_requested)
        if neural_requested:
            # Neural inference is optional compute assistance. Preserve deterministic
            # Factory/Gold fallback instead of risking swap/OOM or UI lockups.
            if snap.total_memory_mb and snap.available_memory_mb < 1024:
                neural_allowed = False; reasons.append('neural_deferred_available_memory_below_1024mb')
            elif tier == 'eco' and (notes > 18000 or cost > 2.5):
                neural_allowed = False; reasons.append('neural_deferred_eco_workload_guard')
            elif snap.available_ratio < 0.12:
                neural_allowed = False; reasons.append('neural_deferred_memory_pressure_guard')
            else:
                reasons.append('neural_admitted')
        else:
            reasons.append('neural_not_requested')

        return BrainDecision(self.SCHEMA, tier, threads, workers, neural_allowed, advisory,
                             tier != 'performance', round(cost, 4), notes, contexts, size, tuple(reasons))

    @staticmethod
    def apply_runtime_limits(decision: BrainDecision) -> dict[str, Any]:
        threads = max(1, int(decision.max_cpu_threads))
        applied = {}
        # These libraries honor the variables on import/startup; setting them here
        # still protects lazily imported neural/scientific dependencies.
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            old = os.environ.get(name)
            os.environ[name] = str(threads)
            applied[name] = {'old': old, 'new': str(threads)}
        try:
            import torch  # type: ignore
            torch.set_num_threads(threads)
            try: torch.set_num_interop_threads(max(1, min(2, threads)))
            except RuntimeError: pass
            applied['torch_num_threads'] = threads
        except Exception:
            applied['torch_num_threads'] = 'not_loaded_or_unavailable'
        return applied

    @staticmethod
    def collect_if_needed(decision: BrainDecision) -> bool:
        if not decision.gc_between_files:
            return False
        gc.collect()
        return True


def govern_config(config, decision: BrainDecision):
    """Return a copied config with compute-only resource gates applied."""
    import copy
    cfg = copy.deepcopy(config)
    requested = bool(getattr(cfg, 'apply_trained_rhythm_model', False))
    if requested and not decision.neural_allowed:
        cfg.apply_trained_rhythm_model = False
        cfg.trained_rhythm_only = False
    return cfg
