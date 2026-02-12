# IRRBB / ALM Mini Engine (Repricing Gap + NII + EVE)

I built this project to practice ALM / IRRBB concepts by implementing a small working “engine”.
It’s not a full bank model, but it helped me understand how repricing mismatch, deposit behaviour,
and discounting affect NII and EVE under rate shocks.

## What this does
Given a dummy banking book (assets + liabilities) and a simple zero curve, the script produces:
- **Repricing gap report** (bucketed by time-to-reprice)
- **12M NII sensitivity** under parallel shocks (base, ±100bp, ±300bp)
- **EVE (PV) sensitivity** under the same shocks using monthly cashflows and curve discounting

## Inputs
- `data/positions.csv`  
  Small set of positions (mortgages, bond, floating loan, NMD deposits, term deposit, wholesale funding)
- `data/curve_base.csv`  
  Base zero curve (tenor_months, zero_rate_annual)
- `assumptions.yaml`  
  Behavioral and pricing assumptions (deposit beta, deposit floor, deposit runoff/decay)

## Outputs (generated in `outputs/`)
- `repricing_gap.csv`
- `nii_results.csv`
- `deposit_rates_by_scenario.csv`
- `eve_results.csv`
- `model_assumptions_used.csv`

## How to run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_mvp.py