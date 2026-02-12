import numpy as np
import pandas as pd


def build_zero_curve(curve_df: pd.DataFrame, rate_shift: float = 0.0) -> pd.DataFrame:
    """
    curve_df columns: tenor_months, zero_rate_annual (annual rate in decimals, e.g. 0.03)

    Returns a DataFrame with:
      tenor_months, zero_rate_annual_shifted

    rate_shift is a parallel shock added to all zero rates (e.g. +0.01 for +100bp).
    """
    c = curve_df.copy()
    c = c.sort_values("tenor_months").reset_index(drop=True)
    c["zero_rate_annual_shifted"] = c["zero_rate_annual"] + rate_shift
    return c


def zero_rate_at_month(zero_curve: pd.DataFrame, month: int) -> float:
    """
    Linearly interpolate the zero rate for an integer month.
    """
    tenors = zero_curve["tenor_months"].to_numpy(dtype=float)
    rates = zero_curve["zero_rate_annual_shifted"].to_numpy(dtype=float)

    # Clamp month to curve range
    m = float(month)
    if m <= tenors[0]:
        return float(rates[0])
    if m >= tenors[-1]:
        return float(rates[-1])

    return float(np.interp(m, tenors, rates))


def discount_factor(zero_curve: pd.DataFrame, month: int) -> float:
    """
    Compute discount factor to 'month' using continuous compounding:
      DF(t) = exp(-r * t)
    where t is in years and r is the annual zero rate.

    This is a standard clean approximation for an MVP EVE engine.
    """
    r = zero_rate_at_month(zero_curve, month)
    t_years = month / 12.0
    return float(np.exp(-r * t_years))
