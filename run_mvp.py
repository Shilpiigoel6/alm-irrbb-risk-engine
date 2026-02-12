import pandas as pd
from src.curves import build_zero_curve, discount_factor, zero_rate_at_month
from src.cashflows import generate_cashflows_for_position
from src.config import load_assumptions


def bucket_label(months: float) -> str:
    """Classic ALM time buckets for repricing gap reports."""
    if months <= 1:
        return "0–1M"
    if months <= 3:
        return "1–3M"
    if months <= 6:
        return "3–6M"
    if months <= 12:
        return "6–12M"
    if months <= 24:
        return "1–2Y"
    if months <= 60:
        return "2–5Y"
    return "5Y+"


def main() -> None:
    # Load inputs
    positions = pd.read_csv("data/positions.csv")
    curve = pd.read_csv("data/curve_base.csv")
    assumptions = load_assumptions("assumptions.yaml")

    # Balance sheet totals (recon)
    total_assets = positions.loc[positions["side"] == "asset", "notional"].sum()
    total_liabs = positions.loc[positions["side"] == "liability", "notional"].sum()

    print("=== Balance Sheet Totals ===")
    print(f"Total Assets     : {total_assets:,.0f}")
    print(f"Total Liabilities: {total_liabs:,.0f}")
    print(f"Assets - Liabs   : {(total_assets - total_liabs):,.0f}")
    print()

    print("=== Curve Preview (first 5 rows) ===")
    print(curve.head())
    print()

    # Time-to-reprice logic (simplified but standard for a first gap view)
    # Floating: next reset date; Fixed: treat as locked until maturity.
    positions["time_to_reprice_months"] = positions.apply(
        lambda r: r["next_reprice_months"] if r["rate_type"] == "floating" else r["maturity_months"],
        axis=1,
    )

    # Bucket mapping
    positions["bucket"] = positions["time_to_reprice_months"].apply(bucket_label)

    # Repricing gap table (notional)
    grouped = positions.pivot_table(
        index="bucket",
        columns="side",
        values="notional",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()

    # Ensure columns exist
    if "asset" not in grouped.columns:
        grouped["asset"] = 0.0
    if "liability" not in grouped.columns:
        grouped["liability"] = 0.0

    grouped["gap_assets_minus_liabs"] = grouped["asset"] - grouped["liability"]

    # Sort buckets in standard order
    bucket_order = ["0–1M", "1–3M", "3–6M", "6–12M", "1–2Y", "2–5Y", "5Y+"]
    grouped["bucket"] = pd.Categorical(grouped["bucket"], categories=bucket_order, ordered=True)
    grouped = grouped.sort_values("bucket")

    print("=== Repricing Gap Report (Notional) ===")
    print(grouped.to_string(index=False))
    print()

    # Save output
    grouped.to_csv("outputs/repricing_gap.csv", index=False)
    print("Saved: outputs/repricing_gap.csv")
    print()



    # Saving Behavioral & Pricing Assumptions Used in CSV file

    print("=== Behavioral & Pricing Assumptions Used ===")
    print(
         f"NMD betas: core={assumptions.nmd_beta_core:.2f}, volatile={assumptions.nmd_beta_volatile:.2f} | "
          f"deposit floor={assumptions.nmd_rate_floor:.2%}"
    )
    print(
        f"NMD monthly decay: core={assumptions.nmd_monthly_decay_core:.3f}, volatile={assumptions.nmd_monthly_decay_volatile:.3f} | "
        f"PV horizon={assumptions.eve_nmd_pv_horizon_months} months"
    )
    print()
    
    pd.DataFrame(
    {
        "core_beta": [assumptions.nmd_beta_core],
        "volatile_beta": [assumptions.nmd_beta_volatile],
        "deposit_floor": [assumptions.nmd_rate_floor],
        "core_decay": [assumptions.nmd_monthly_decay_core],
        "volatile_decay": [assumptions.nmd_monthly_decay_volatile],
    }
    ).to_csv("outputs/model_assumptions_used.csv", index=False)
    print("Saved: outputs/model_assumptions_used.csv")
    print()

    # NII Projection (12M)

    BASE_RATE = 0.03
    shocks = {
        "base": 0.0,
        "+100bp": 0.01,
        "-100bp": -0.01,
        "+300bp": 0.03,
        "-300bp": -0.03,
    }

    def compute_nii(rate_shift: float) -> float:
        total_income = 0.0
        total_expense = 0.0

        for _, row in positions.iterrows():
            notional = row["notional"]

            if row["rate_type"] == "fixed":
                rate = float(row["coupon_rate"])
            else:
                # Floating-rate pricing
                product = str(row["product_type"])
                spread = float(row["spread"])

                # Market/reference rate (MVP proxy)
                market_rate = BASE_RATE + rate_shift

                if product == "nmd_deposit":
                    # Administered deposit rate with beta + floor
                    behavioral = str(row["behavioral_flag"])

                    if behavioral == "core":
                        beta = assumptions.nmd_beta_core
                    else:
                        beta = assumptions.nmd_beta_volatile

                    base_dep_rate = float(row["coupon_rate"])
                    rate = base_dep_rate + beta * rate_shift
                    rate = max(rate, assumptions.nmd_rate_floor)
                else:
                    # Standard floating instruments: market + spread
                    rate = market_rate + spread

            interest = notional * rate

            if row["side"] == "asset":
                total_income += interest
            else:
                total_expense += interest

        return total_income - total_expense


    print("=== Rate Assumptions ===")
    print(f"Base reference rate (proxy): {BASE_RATE:.2%}")
    print("Shocks applied:")
    for name, shift in shocks.items():
        print(f"  {name:>7} : shift {shift:+.2%}")
    print()


    nii_results = []
    for name, shift in shocks.items():
        nii_val = compute_nii(shift)
        nii_results.append({"scenario": name, "rate_shift": shift, "nii": nii_val})


    # Deposit administered rates (beta + floor) for transparency
    dep_rows = []
    core_base = float(positions.loc[positions["id"] == "L1", "coupon_rate"].iloc[0])       # core NMD base rate
    volatile_base = float(positions.loc[positions["id"] == "L2", "coupon_rate"].iloc[0])   # volatile NMD base rate

    for name, shift in shocks.items():
        if name == "base":
            continue

        core_rate = max(core_base + assumptions.nmd_beta_core * shift, assumptions.nmd_rate_floor)
        vol_rate = max(volatile_base + assumptions.nmd_beta_volatile * shift, assumptions.nmd_rate_floor)

        dep_rows.append(
            {"scenario": name, "core_deposit_rate": core_rate, "volatile_deposit_rate": vol_rate}
        )

    print("Deposit pricing parameters:")
    print(
        f"  Core beta: {assumptions.nmd_beta_core:.2f} | "
    )
    print()

    print("Deposit administered rates (beta + floor):")
    for r in dep_rows:
        print(f"  {r['scenario']:>7} : core {r['core_deposit_rate']:.2%} | volatile {r['volatile_deposit_rate']:.2%}")
    print()

    pd.DataFrame(dep_rows).to_csv("outputs/deposit_rates_by_scenario.csv", index=False)
    print("Saved: outputs/deposit_rates_by_scenario.csv")
    print()
    
        
    nii_df = pd.DataFrame(nii_results)
    order = ["base", "+100bp", "-100bp", "+300bp", "-300bp"]
    nii_df["scenario"] = pd.Categorical(nii_df["scenario"], categories=order, ordered=True)
    nii_df = nii_df.sort_values("scenario")
    base_nii = float(nii_df.loc[nii_df["scenario"] == "base", "nii"].iloc[0])
    nii_df["delta_vs_base"] = nii_df["nii"] - base_nii



    print("=== NII Projection (12M) ===")

    for _, r in nii_df.iterrows():
        scen = r["scenario"]
        nii_val = r["nii"]
        dlt = r["delta_vs_base"]
        if scen == "base":
            print(f"NII Base       : {nii_val:,.0f}")
        else:
            print(f"NII {scen:>7}   : {nii_val:,.0f}   Delta: {dlt:,.0f}")
    print()

    nii_df.to_csv("outputs/nii_results.csv", index=False)
    print("Saved: outputs/nii_results.csv")
    print()


    def pv_position(row: pd.Series, rate_shift: float, assumptions) -> float:
        """
        Present value of a single position under a parallel shock.
        Cashflow timing from cashflow engine; discounting from shocked zero curve.

        Interest handling (MVP):
        - Fixed-rate: use coupon_rate
        - Floating-rate: approximate rate as (12M zero rate + shift + spread)
        - NMD deposits: use coupon_rate as administered rate (MVP), principal runoff from behavioral schedule
        """
        shocked_curve = build_zero_curve(curve, rate_shift=rate_shift)

        rate_type = str(row["rate_type"])
        product = str(row["product_type"])
        spread = float(row["spread"])
        coupon = float(row["coupon_rate"])

        # Approximate a short reference rate using the 12M zero rate from the curve
        ref_rate_12m = zero_rate_at_month(shocked_curve, 12)

        if rate_type == "fixed":
            annual_rate = coupon
        else:
            # floating
            annual_rate = ref_rate_12m + spread
            # For NMD deposits, coupon is an administered rate; for MVP we keep coupon as-is (optional tweak)
            if product == "nmd_deposit":
                annual_rate = coupon  # admin rate paid on deposits (simple)

        cfs = generate_cashflows_for_position(row, assumptions)

        pv = 0.0
        for cf in cfs:
            m = int(cf.month)
            df = discount_factor(shocked_curve, m)

            # If cashflow schedule already has interest (mortgages/bullets fixed), use it.
            # If interest=0 (floating bullet or NMD runoff), compute interest payment on outstanding balance proxy.
            interest_cf = float(cf.interest)

            # For bullet schedules, interest exists only on payment dates; for floating we need to compute it.
            if interest_cf == 0.0 and rate_type == "floating":
                # simple approximation: interest payment amount for that period
                # If cf is from bullet schedule, interest occurs on those months only;
                # Here, for floating bullet we treat interest at those pay dates on full notional.
                freq = int(row["payment_freq_months"])
                freq = max(freq, 1)
                interest_cf = float(row["notional"]) * (annual_rate / 12.0) * freq

            # PV of cashflow = DF * (interest + principal)
            pv += df * (interest_cf + float(cf.principal))

        return float(pv)

    def pv_side(rate_shift: float, side: str) -> float:
        subset = positions[positions["side"] == side]
        return float(sum(pv_position(r, rate_shift, assumptions) for _, r in subset.iterrows()))


    eve_shocks = {
        "base": 0.0,
        "+100bp": 0.01,
        "-100bp": -0.01,
        "+300bp": 0.03,
        "-300bp": -0.03,
    }

    eve_rows = []
    for name, shift in eve_shocks.items():
        pv_a = pv_side(shift, "asset")
        pv_l = pv_side(shift, "liability")
        eve = pv_a - pv_l
        eve_rows.append({"scenario": name, "rate_shift": shift, "pv_assets": pv_a, "pv_liabs": pv_l, "eve": eve})

    eve_df = pd.DataFrame(eve_rows)
    base_eve = float(eve_df.loc[eve_df["scenario"] == "base", "eve"].iloc[0])
    eve_df["delta_vs_base"] = eve_df["eve"] - base_eve

    print("=== EVE (PV) under Shocks ===")
    # Print base first, then others
    eve_df_print = eve_df.copy()
    order = ["base", "+100bp", "-100bp", "+300bp", "-300bp"]
    eve_df_print["scenario"] = pd.Categorical(eve_df_print["scenario"], categories=order, ordered=True)
    eve_df_print = eve_df_print.sort_values("scenario")

    for _, r in eve_df_print.iterrows():
        scen = r["scenario"]
        if scen == "base":
            print(f"EVE Base        : {r['eve']:,.0f}")
            print(f"PV Assets (Base): {r['pv_assets']:,.0f}")
            print(f"PV Liabs  (Base): {r['pv_liabs']:,.0f}")
        else:
            print(f"EVE {scen:>7}   : {r['eve']:,.0f}   Delta: {r['delta_vs_base']:,.0f}")
    print()

    eve_df.to_csv("outputs/eve_results.csv", index=False)
    print("Saved: outputs/eve_results.csv")


if __name__ == "__main__":
    main()
