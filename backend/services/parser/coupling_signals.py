"""Cross-file coupling signal extraction.

Derives CrossFileSignals from import relationships between files: fan-in/fan-out
coupling, circular import indicators, direction violations, and hub files.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from config.constants import (
    HIGH_COUPLING_FAN_IN_THRESHOLD,
    HIGH_COUPLING_FAN_OUT_THRESHOLD,
)
from shared.types.enums import CouplingType
from shared.types.pcr_types import (
    CouplingSignal,
    CrossFileSignals,
    DirectionViolation,
    FileAnalysis,
)


def extract_cross_file_signals(file_analyses: list[FileAnalysis]) -> CrossFileSignals:
    """Derive import relationship signals across all analyzed files."""
    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)

    path_set = {f.path for f in file_analyses}

    for fa in file_analyses:
        local_imports = [i for i in fa.import_list if _looks_local(i, path_set)]
        fan_out[fa.path] = len(local_imports)
        for imp in local_imports:
            fan_in[imp] += 1

    high_coupling: list[CouplingSignal] = []
    hub_files: list[str] = []

    for path in path_set:
        fi = fan_in.get(path, 0)
        fo = fan_out.get(path, 0)
        high_fi = fi > HIGH_COUPLING_FAN_IN_THRESHOLD
        high_fo = fo > HIGH_COUPLING_FAN_OUT_THRESHOLD

        if high_fi and high_fo:
            coupling_type = CouplingType.BOTH
        elif high_fi:
            coupling_type = CouplingType.HIGH_FAN_IN
        elif high_fo:
            coupling_type = CouplingType.HIGH_FAN_OUT
        else:
            continue

        high_coupling.append(CouplingSignal(
            file_path=path,
            fan_in=fi,
            fan_out=fo,
            coupling_type=coupling_type,
        ))

        if high_fi:
            hub_files.append(path)

    cycles = _detect_cycle_indicators(file_analyses, path_set)
    violations = _detect_direction_violations(file_analyses)

    return CrossFileSignals(
        high_coupling_files=high_coupling,
        dependency_direction_violations=violations,
        import_cycle_indicators=cycles,
        hub_files=hub_files,
    )


def _looks_local(import_text: str, path_set: set[str]) -> bool:
    if import_text.startswith("."):
        return True
    parts = import_text.split()
    if len(parts) >= 2 and parts[0] in ("from", "import"):
        module = parts[1].split(".")[0]
        return any(p.startswith(module + "/") or p == module + ".py"
                   for p in path_set)
    return False


def _detect_cycle_indicators(
    file_analyses: list[FileAnalysis],
    path_set: set[str],
) -> list[str]:
    import_map: dict[str, set[str]] = {}
    for fa in file_analyses:
        import_map[fa.path] = set(fa.import_list)

    cycles: set[str] = set()
    paths = list(import_map.keys())
    for i, path_a in enumerate(paths):
        for path_b in paths[i + 1:]:
            a_imports_b = any(path_b in imp or Path(path_b).stem in imp
                              for imp in import_map.get(path_a, set()))
            b_imports_a = any(path_a in imp or Path(path_a).stem in imp
                              for imp in import_map.get(path_b, set()))
            if a_imports_b and b_imports_a:
                cycles.add(path_a)
                cycles.add(path_b)

    return sorted(cycles)


def _detect_direction_violations(
    file_analyses: list[FileAnalysis],
) -> list[DirectionViolation]:
    violations: list[DirectionViolation] = []
    layer_order = ["domain", "infrastructure", "application", "api", "presentation"]

    for fa in file_analyses:
        importer_layer = _infer_layer(fa.path, layer_order)
        if importer_layer is None:
            continue
        for imp in fa.import_list:
            imported_layer = _infer_layer(imp, layer_order)
            if imported_layer is None:
                continue
            if layer_order.index(imported_layer) < layer_order.index(importer_layer):
                violations.append(DirectionViolation(
                    importer_path=fa.path,
                    imported_path=imp,
                    violation_description=(
                        f"'{importer_layer}' layer imports from '{imported_layer}' layer "
                        f"(lower-level dependency direction violated)"
                    ),
                ))
    return violations


def _infer_layer(path: str, layer_order: list[str]) -> str | None:
    lower = path.lower()
    for layer in layer_order:
        if layer in lower:
            return layer
    return None
