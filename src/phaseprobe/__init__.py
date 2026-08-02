"""PhaseProbe: qualitative simulation evidence and executable regressions."""

from phaseprobe.api import (
    run_invariant_check,
    run_parameter_scan,
    run_perturbation,
    run_simulation,
)
from phaseprobe.types import (
    InvariantResult,
    ModelAdapter,
    SimulationTrace,
    TracePoint,
    TrajectoryAdapter,
)

__all__ = [
    "InvariantResult",
    "ModelAdapter",
    "SimulationTrace",
    "TracePoint",
    "TrajectoryAdapter",
    "__version__",
    "run_invariant_check",
    "run_parameter_scan",
    "run_perturbation",
    "run_simulation",
]

__version__ = "0.2.0"
