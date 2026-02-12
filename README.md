# IRRBB / ALM Mini Engine (Repricing Gap + NII + EVE)

I built this project to better understand Asset Liability Management (ALM) and IRRBB concepts by implementing a small working “engine”.

It is not meant to be a production-grade bank model, but a structured learning exercise to see how repricing mismatch, deposit behaviour, and discounting mechanics affect NII and EVE under interest rate shocks.

---

## What this does

Given a simplified banking book (assets + liabilities) and a basic zero curve, the script produces:

- **Repricing gap report** (bucketed by time-to-reprice)
- **12M NII sensitivity** under parallel shocks (base, ±100bp, ±300bp)
- **EVE (PV) sensitivity** under the same shocks using monthly cashflows and curve discounting
- Behavioral deposit modelling (beta + floor for NII, decay for EVE)

---

## Inputs

- `data/positions.csv`  
  Dummy banking book including:
  - Fixed-rate mortgages (amortizing)
  - Floating loan
  - Bond portfolio
  - Non-maturity deposits (core + volatile)
  - Term deposit
  - Wholesale funding

- `data/curve_base.csv`  
  Base zero curve (`tenor_months`, `zero_rate_annual`)

- `assumptions.yaml`  
  Behavioral and pricing assumptions:
  - Deposit beta (core vs volatile)
  - Deposit rate floor
  - Monthly deposit decay (for EVE effective maturity)

---

## Outputs (generated in `outputs/`)

- `repricing_gap.csv`
- `nii_results.csv`
- `deposit_rates_by_scenario.csv`
- `eve_results.csv`
- `model_assumptions_used.csv`
- Sensitivity charts (PNG)

---

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_mvp.py
```

# Sensitivity Charts
NII vs Parallel Shock
EVE vs Parallel Shock

# What I observed from the results
	•	The short repricing bucket is liability-heavy, so NII compresses when rates rise.
	•	NII improves when rates fall, but not symmetrically for large shocks.
	•	Under -300bp, volatile deposits hit the rate floor, which caps the funding benefit. This creates visible asymmetry in the NII chart.
	•	EVE declines under positive shocks because asset PV is more rate-sensitive than liability PV (duration mismatch).
	•	The EVE curve looks close to linear because the model currently applies parallel shocks without optionality on assets.

# Simplifications (MVP scope)
	•	Floating rate pricing uses a short-rate proxy rather than full forward curve modelling
	•	No mortgage prepayment (only scheduled amortization)
	•	Only parallel shocks (no steepener/flattener scenarios yet)
	•	No embedded options (caps/floors) on asset side

# Possible Extensions: if extended further, I would add:
	•	Forward curve-based floating reset logic
	•	Mortgage prepayment (CPR) sensitivity
	•	Additional IRRBB shock shapes
	•	Product-level contribution breakdown for NII and EVE
	•	Scenario reporting module