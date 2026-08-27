from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass(frozen=True)
class DependencyState:
    import_name: str
    purpose: str
    available: bool
    version: str = ""


OPTIONAL = {
    "numpy": "vector/statistical feature processing",
    "scipy": "distance, distributions, signal/statistical utilities",
    "sklearn": "clustering, anomaly detection, calibration and similarity models",
    "statsmodels": "deeper statistical diagnostics and confidence analysis",
    "networkx": "evidence/provenance/relationship graphs",
    "pydantic": "strict profile and evidence schema validation",
    "jsonschema": "audit/report schema validation",
    "orjson": "fast large JSON/NDJSON serialization",
    "joblib": "safe parallel analysis and cached research jobs",
    "numba": "optional acceleration for numeric hot loops",
    "torch": "optional guarded neural proposal layer",
}

REQUIRED = {"mido": "core Standard MIDI File parsing and writing"}


def probe_required() -> Dict[str, DependencyState]:
    out={}
    for name,purpose in REQUIRED.items():
        try:
            importlib.import_module(name);version=importlib.metadata.version(name)
            out[name]=DependencyState(name,purpose,True,version)
        except Exception:
            out[name]=DependencyState(name,purpose,False,'')
    return out


def probe() -> Dict[str, DependencyState]:
    out: Dict[str, DependencyState] = {}
    for name, purpose in OPTIONAL.items():
        try:
            mod = importlib.import_module(name)
            try:
                version = importlib.metadata.version(name if name != "sklearn" else "scikit-learn")
            except importlib.metadata.PackageNotFoundError:
                version = str(getattr(mod, "__version__", "unknown"))
            out[name] = DependencyState(name, purpose, True, version)
        except Exception:
            out[name] = DependencyState(name, purpose, False, "")
    return out


def capabilities() -> Dict[str, bool]:
    p = probe()
    required=probe_required()
    return {
        "core": all(x.available for x in required.values()),
        "forensics_numeric": p["numpy"].available and p["scipy"].available,
        "ml_analysis": p["sklearn"].available,
        "statistical_diagnostics": p["statsmodels"].available,
        "evidence_graph": p["networkx"].available,
        "strict_validation": p["pydantic"].available and p["jsonschema"].available,
        "fast_json": p["orjson"].available,
        "parallel_analysis": p["joblib"].available,
        "numeric_acceleration": p["numba"].available,
        "neural_proposals": p["torch"].available,
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Show PA800 optional dependency/capability status")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)
    states = probe()
    required=probe_required()
    caps = capabilities()
    if ns.json:
        print(json.dumps({"required": {k: asdict(v) for k,v in required.items()}, "dependencies": {k: asdict(v) for k, v in states.items()}, "capabilities": caps}, indent=2))
        return 0 if caps['core'] else 1
    print("PA800 optional capability status")
    print("=" * 38)
    for st in required.values():
        flag="OK" if st.available else "MISSING"; ver=f" {st.version}" if st.version else ""
        print(f"[{flag}] {st.import_name}{ver}: {st.purpose}")
    for st in states.values():
        flag = "OK" if st.available else "--"
        ver = f" {st.version}" if st.version else ""
        print(f"[{flag}] {st.import_name}{ver}: {st.purpose}")
    print("\nCapabilities")
    for name, enabled in caps.items():
        print(f"[{'ON' if enabled else 'OFF'}] {name}")
    return 0 if caps['core'] else 1


if __name__ == "__main__":
    raise SystemExit(main())