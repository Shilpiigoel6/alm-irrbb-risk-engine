from __future__ import annotations

from src.config import Assumptions

import math
from dataclasses import dataclass
from typing import List, Dict, Any

import pandas as pd


@dataclass
class Cashflow:
    month: int
    interest: float
    principal: float


def _level_payment_amort_schedule(
    notional: float,
    annual_rate: float,
    maturity_months: int,
) -> List[Cashflow]:
    """
    Standard level-payment amortization (like a mortgage):
      payment = P * r_m / (1 - (1+r_m)^-n)

    Returns monthly interest + principal cashflows for months 1..n.
    """
    if maturity_months <= 0:
        return []

    r_m = annual_rate / 12.0
    n = maturity_months

    if abs(r_m) < 1e-12:
        payment = notional / n
    else:
        payment = notional * r_m / (1.0 - (1.0 + r_m) ** (-n))

    bal = notional
    cfs: List[Cashflow] = []
    for m in range(1, n + 1):
        interest = bal * r_m
        principal = payment - interest
        # Guard tiny negative rounding at end
        principal = min(principal, bal)
        bal -= principal
        cfs.append(Cashflow(month=m, interest=float(interest), principal=float(principal)))

        if bal <= 1e-6:
            break

    return cfs


def _bullet_schedule(
    notional: float,
    annual_rate: float,
    maturity_months: int,
    payment_freq_months: int,
) -> List[Cashflow]:
    """
    Bullet instrument:
      - interest paid every payment_freq_months
      - principal repaid at maturity
    """
    if maturity_months <= 0:
        return []

    freq = max(int(payment_freq_months), 1)
    r_m = annual_rate / 12.0

    cfs: List[Cashflow] = []
    for m in range(1, maturity_months + 1):
        interest = 0.0
        principal = 0.0

        if m % freq == 0:
            # Interest for the last 'freq' months on full notional (simple MVP)
            interest = notional * r_m * freq

        if m == maturity_months:
            principal = notional

        if (interest != 0.0) or (principal != 0.0):
            cfs.append(Cashflow(month=m, interest=float(interest), principal=float(principal)))

    return cfs

def _nmd_runoff_schedule(
    notional: float,
    behavioral_flag: str,
    assumptions: Assumptions,
) -> List[Cashflow]:
    """
    Behavioral runoff for non-maturity deposits (NMD):
    We model "principal cashflows" as balance runoff (liability decreasing over time).

    Core vs volatile decay rates come from assumptions.yaml.
    """
    if behavioral_flag == "core":
        monthly_decay = assumptions.nmd_monthly_decay_core
    else:
        monthly_decay = assumptions.nmd_monthly_decay_volatile

    horizon_months = assumptions.eve_nmd_pv_horizon_months

    bal = notional
    cfs: List[Cashflow] = []
    for m in range(1, horizon_months + 1):
        runoff = bal * monthly_decay
        runoff = min(runoff, bal)
        bal -= runoff
        cfs.append(Cashflow(month=m, interest=0.0, principal=float(runoff)))

        if bal <= 1e-6:
            break

    return cfs



def generate_cashflows_for_position(row: pd.Series, assumptions: Assumptions) -> List[Cashflow]:
    """
    Generate cashflows for a position (contractual + simple behavioral where applicable).
    Interest rates are handled outside (in EVE calc) to allow scenario shocking.

    For EVE, we need timing of:
      - principal flows (amortization / bullet / runoff)
      - interest payment dates (we approximate using cashflow schedules)

    Returns list of Cashflow(month, interest, principal).
    """
    notional = float(row["notional"])
    maturity_months = int(row["maturity_months"])
    payment_freq_months = int(row["payment_freq_months"])

    product = str(row["product_type"])
    behavioral = str(row["behavioral_flag"])

    # Mortgages: amortizing level-payment schedule
    if product == "fixed_mortgage":
        # Use coupon_rate as contractual mortgage rate
        annual_rate = float(row["coupon_rate"])
        return _level_payment_amort_schedule(notional, annual_rate, maturity_months)

    # NMD deposits: behavioral runoff schedule (principal only)
    if product == "nmd_deposit":
        # No contractual maturity; we set a long horizon for PV purposes
        return _nmd_runoff_schedule(notional, behavioral_flag=behavioral, assumptions=assumptions)

    # Everything else treated as bullet for MVP
    # Rate passed later; we set interest placeholders to 0 here and compute interest timing via frequency.
    # We'll generate interest+principal timing assuming bullet schedule.
    # For floating, the "annual_rate" here is not used; interest is computed later.
    annual_rate = float(row["coupon_rate"]) if str(row["rate_type"]) == "fixed" else 0.0
    return _bullet_schedule(notional, annual_rate, maturity_months, payment_freq_months)
