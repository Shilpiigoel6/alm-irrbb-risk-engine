from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class Assumptions:
    raw: Dict[str, Any]

    @property
    def nmd_monthly_decay_core(self) -> float:
        return float(self.raw["nmd"]["monthly_decay_core"])

    @property
    def nmd_monthly_decay_volatile(self) -> float:
        return float(self.raw["nmd"]["monthly_decay_volatile"])

    @property
    def nmd_beta_core(self) -> float:
        return float(self.raw["nmd"]["beta_core"])

    @property
    def nmd_beta_volatile(self) -> float:
        return float(self.raw["nmd"]["beta_volatile"])

    @property
    def nmd_rate_floor(self) -> float:
        return float(self.raw["nmd"]["rate_floor"])

    @property
    def eve_nmd_pv_horizon_months(self) -> int:
        return int(self.raw["eve"]["nmd_pv_horizon_months"])

    @property
    def rates_fallback_ref_rate(self) -> float:
        return float(self.raw["rates"]["fallback_ref_rate"])


def load_assumptions(path: str = "assumptions.yaml") -> Assumptions:
    """
    Load assumptions from YAML into a typed Assumptions object.

    YAML is used because:
    - easy to read/edit without touching code
    - mirrors how ALM teams manage assumption governance
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Assumptions(raw=data)
