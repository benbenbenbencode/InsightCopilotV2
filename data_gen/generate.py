"""Synthetic consumer-lending dataset (Indonesia-flavoured), written as CSVs.

    python data_gen/generate.py --size medium --out data

Sizes (customers): small=10k, medium=40k, large=100k. Same seed -> same data.

Built-in "stories" an analyst (or the agent) can discover:
  * Loans disbursed from 2025-07 onward default ~40% more (cohort deterioration)
  * Paid-social acquisition has a worse default rate than referral
  * Risk grade E has high rejection and high default; grade A the opposite
  * Many first-installment defaults (fraud-like behaviour)
"""
from __future__ import annotations

import argparse
import os
import numpy as np
import pandas as pd

SIZES = {"small": 10_000, "medium": 40_000, "large": 100_000}

CITIES = {  # city: (province, weight)
    "Jakarta": ("DKI Jakarta", 22), "Surabaya": ("Jawa Timur", 9), "Bandung": ("Jawa Barat", 8),
    "Bekasi": ("Jawa Barat", 7), "Tangerang": ("Banten", 7), "Depok": ("Jawa Barat", 5),
    "Medan": ("Sumatera Utara", 7), "Semarang": ("Jawa Tengah", 5), "Makassar": ("Sulawesi Selatan", 4),
    "Palembang": ("Sumatera Selatan", 4), "Batam": ("Kepulauan Riau", 3), "Denpasar": ("Bali", 3),
    "Yogyakarta": ("DI Yogyakarta", 3), "Malang": ("Jawa Timur", 3), "Balikpapan": ("Kalimantan Timur", 2),
    "Pontianak": ("Kalimantan Barat", 2), "Manado": ("Sulawesi Utara", 2), "Pekanbaru": ("Riau", 4),
}
EMPLOYMENT = ["employee", "self_employed", "gig_worker", "civil_servant"]
EMP_W = [0.50, 0.22, 0.20, 0.08]
INCOME_MU = {"employee": 15.9, "self_employed": 15.8, "gig_worker": 15.5, "civil_servant": 16.0}  # ln(IDR/month)
CHANNELS = ["organic", "referral", "paid_social", "partner", "field_agent"]
CH_W = [0.30, 0.18, 0.28, 0.14, 0.10]
CH_RISK = {"organic": 1.0, "referral": 0.75, "paid_social": 1.35, "partner": 1.0, "field_agent": 1.15}

PRODUCTS = pd.DataFrame([
    (1, "Cash Loan", "installment", 1_000_000, 30_000_000, "3,6,9,12"),
    (2, "Paylater", "revolving_bnpl", 500_000, 5_000_000, "1,3"),
    (3, "Salary Advance", "short_term", 1_000_000, 5_000_000, "1"),
    (4, "Micro Business Loan", "installment", 10_000_000, 100_000_000, "6,12"),
], columns=["product_id", "product_name", "product_type", "min_amount", "max_amount", "tenor_options"])
TENORS = {1: ([3, 6, 9, 12], [0.20, 0.35, 0.20, 0.25]), 2: ([1, 3], [0.55, 0.45]),
          3: ([1], [1.0]), 4: ([6, 12], [0.45, 0.55])}
PROD_MULT = {1: 1.0, 2: 0.8, 3: 0.6, 4: 1.3}
GRADES = ["A", "B", "C", "D", "E"]
RATE = {"A": 0.012, "B": 0.016, "C": 0.021, "D": 0.027, "E": 0.034}   # flat monthly
PD = {"A": 0.02, "B": 0.05, "C": 0.09, "D": 0.16, "E": 0.28}
FEE = {1: 0.03, 2: 0.02, 3: 0.04, 4: 0.025}
REJECT_REASONS = ["low_credit_score", "high_dti", "income_unverified", "incomplete_kyc", "fraud_flag"]
PAY_CH = ["va_bca", "va_mandiri", "alfamart", "indomaret", "autodebit", "ewallet"]
PAY_W = [0.25, 0.18, 0.14, 0.12, 0.17, 0.14]


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def grade_from_score(cs):
    return np.select([cs >= 700, cs >= 640, cs >= 580, cs >= 520], list("ABCD"), default="E")


def generate(n_customers: int, asof: pd.Timestamp, seed: int) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2023-07-01")
    span = (asof - start).days

    # ---------------- customers ----------------
    cid = np.arange(1, n_customers + 1)
    emp = rng.choice(EMPLOYMENT, n_customers, p=EMP_W)
    city_names = list(CITIES)
    cw = np.array([CITIES[c][1] for c in city_names], float)
    city = rng.choice(city_names, n_customers, p=cw / cw.sum())
    province = np.array([CITIES[c][0] for c in city])
    income = np.exp(rng.normal(np.vectorize(INCOME_MU.get)(emp), 0.45))
    income = (np.round(income / 100_000) * 100_000).clip(2_500_000, 60_000_000).astype("int64")
    signup = start + pd.to_timedelta((rng.beta(1.6, 1.0, n_customers) * span).astype(int), unit="D")
    channel = rng.choice(CHANNELS, n_customers, p=CH_W)
    latent = rng.normal(0, 1, n_customers)  # true creditworthiness
    customers = pd.DataFrame({
        "customer_id": cid,
        "signup_date": signup.date,
        "birth_year": rng.integers(1968, 2005, n_customers),
        "gender": rng.choice(["M", "F"], n_customers, p=[0.52, 0.48]),
        "city": city, "province": province,
        "employment_type": emp, "monthly_income": income,
        "acquisition_channel": channel,
        "device_os": rng.choice(["android", "ios"], n_customers, p=[0.88, 0.12]),
        "kyc_verified": rng.random(n_customers) > 0.03,
    })

    # ---------------- applications ----------------
    n_apps = 1 + rng.poisson(1.3, n_customers)
    app_cust = np.repeat(np.arange(n_customers), n_apps)
    k = np.concatenate([np.arange(a) for a in n_apps])
    gaps = rng.exponential(40, len(app_cust)) * (k > 0) + rng.exponential(2, len(app_cust)) * (k == 0)
    # cumulative offset per customer: apps are ordered in time
    offset = pd.Series(gaps).groupby(app_cust).cumsum().to_numpy()
    app_date = signup[app_cust] + pd.to_timedelta(offset.astype(int), unit="D")
    keep = app_date <= asof
    app_cust, app_date, k = app_cust[keep], app_date[keep], k[keep]
    app_date = pd.DatetimeIndex(app_date)
    n = len(app_cust)

    prod = np.zeros(n, dtype=int)
    for e in EMPLOYMENT:
        m = emp[app_cust] == e
        w = {"employee": [0.42, 0.28, 0.25, 0.05], "self_employed": [0.40, 0.25, 0.0, 0.35],
             "gig_worker": [0.50, 0.40, 0.0, 0.10], "civil_servant": [0.45, 0.20, 0.30, 0.05]}[e]
        prod[m] = rng.choice([1, 2, 3, 4], m.sum(), p=np.array(w) / sum(w))
    lo = PRODUCTS.set_index("product_id")["min_amount"].to_numpy()
    hi = PRODUCTS.set_index("product_id")["max_amount"].to_numpy()
    req = np.exp(rng.uniform(np.log(lo[prod - 1]), np.log(hi[prod - 1])))
    req = (np.round(req / 50_000) * 50_000).astype("int64")

    credit = np.clip(570 + 85 * (latent[app_cust] + rng.normal(0, 0.35, n)), 300, 850).round().astype(int)
    grade = grade_from_score(credit)
    inc = income[app_cust]
    ratio = req / inc  # requested / monthly income
    p_approve = sigmoid(0.4 + 1.5 * (credit - 570) / 85 - 0.9 * np.log1p(ratio) - 0.4 * (k == 0))
    approved = rng.random(n) < p_approve
    cap = inc * np.select([grade == "A", grade == "B", grade == "C", grade == "D"], [4, 3, 2.2, 1.5], 1.0)
    appr_amt = np.where(approved, np.minimum(req, (np.round(cap / 50_000) * 50_000)).astype("int64"), 0)
    appr_amt = np.maximum(appr_amt, np.where(approved, lo[prod - 1] // 2, 0)).astype("int64")
    reason = rng.choice(REJECT_REASONS, n, p=[0.38, 0.22, 0.17, 0.15, 0.08])
    reason = np.where(approved, None, reason)
    taken = approved & (rng.random(n) < 0.93)
    apps = pd.DataFrame({
        "application_id": np.arange(1, n + 1),
        "customer_id": cid[app_cust],
        "application_date": app_date.date,
        "product_id": prod,
        "requested_amount": req,
        "approved_amount": appr_amt,
        "decision": np.where(approved, "approved", "rejected"),
        "reject_reason": reason,
        "credit_score": credit,
        "risk_grade": grade,
        "accepted_by_customer": taken,
    })

    # ---------------- loans ----------------
    li = np.where(taken)[0]
    m = len(li)
    l_prod = prod[li]
    tenor = np.zeros(m, dtype=int)
    for p, (ts, tw) in TENORS.items():
        mm = l_prod == p
        tenor[mm] = rng.choice(ts, mm.sum(), p=tw)
    disb = app_date[li] + pd.to_timedelta(rng.choice([0, 1, 1, 2], m), unit="D")
    ok = disb <= asof
    li, l_prod, tenor, disb = li[ok], l_prod[ok], tenor[ok], pd.DatetimeIndex(disb[ok])
    m = len(li)
    principal = appr_amt[li]
    l_grade = grade[li]
    rate = np.vectorize(RATE.get)(l_grade)
    fee = np.vectorize(FEE.get)(l_prod)
    loan_id = np.arange(1, m + 1)
    loans = pd.DataFrame({
        "loan_id": loan_id,
        "application_id": apps["application_id"].to_numpy()[li],
        "customer_id": cid[app_cust[li]],
        "product_id": l_prod,
        "disbursement_date": disb.date,
        "principal": principal,
        "tenor_months": tenor,
        "monthly_interest_rate": rate,
        "admin_fee": (principal * fee).round(-2).astype("int64"),
        "risk_grade": l_grade,
        "acquisition_channel": channel[app_cust[li]],
    })

    # ---------------- installments ----------------
    rep = np.repeat(np.arange(m), tenor)
    inst_no = np.concatenate([np.arange(1, t + 1) for t in tenor])
    due = disb[rep] + pd.to_timedelta(30 * inst_no, unit="D")
    base = np.round(principal / tenor, -2).astype("int64")
    p_due = base[rep].copy()
    last = inst_no == tenor[rep]
    # last installment absorbs rounding so principal sums exactly
    p_due[last] = principal[rep][last] - base[rep][last] * (tenor[rep][last] - 1)
    i_due = np.round(principal[rep] * rate[rep], -2).astype("int64")
    inst = pd.DataFrame({
        "loan_id": loan_id[rep], "installment_no": inst_no, "due_date": due.date,
        "principal_due": p_due, "interest_due": i_due,
    })
    inst["total_due"] = inst["principal_due"] + inst["interest_due"]

    # ---------------- behaviour: default + lateness ----------------
    base_pd = np.vectorize(PD.get)(l_grade) * np.vectorize(PROD_MULT.get)(l_prod)
    ch_mult = np.vectorize(CH_RISK.get)(loans["acquisition_channel"].to_numpy())
    shock = np.where(disb >= pd.Timestamp("2025-07-01"), 1.4, 1.0)
    p_def = np.clip(base_pd * ch_mult * shock, 0, 0.9)
    is_def = rng.random(m) < p_def
    first_pay_def = rng.random(m) < 0.35
    def_no = np.where(first_pay_def, 1, rng.integers(1, tenor + 1))
    def_no = np.where(is_def, def_no, 10_000)
    recover = is_def & (rng.random(m) < 0.25)

    p_late = np.select([l_grade == "A", l_grade == "B", l_grade == "C", l_grade == "D"],
                       [0.08, 0.14, 0.22, 0.32], 0.45)
    late_flag = rng.random(len(inst)) < p_late[rep]
    late_days = np.minimum(1 + rng.geometric(0.18, len(inst)), 30)
    early = rng.random(len(inst)) < 0.10
    days_off = np.where(late_flag, late_days, np.where(early, -rng.integers(1, 4, len(inst)), 0))

    defaulted_inst = inst_no >= def_no[rep]
    rec_inst = recover[rep] & (inst_no == def_no[rep])
    days_off = np.where(rec_inst, rng.integers(31, 121, len(inst)), days_off)
    pays = ~defaulted_inst | rec_inst
    paid_date = due + pd.to_timedelta(days_off, unit="D")
    pays &= paid_date <= asof
    idx = np.where(pays)[0]
    n_pay = len(idx)
    secs = rng.integers(6 * 3600, 23 * 3600, n_pay)
    late_n = np.clip(days_off[idx], 0, 30)
    payments = pd.DataFrame({
        "payment_id": np.arange(1, n_pay + 1),
        "loan_id": inst["loan_id"].to_numpy()[idx],
        "installment_no": inst_no[idx],
        "paid_at": (paid_date[idx].normalize() + pd.to_timedelta(secs, unit="s")),
        "amount_paid": inst["total_due"].to_numpy()[idx],
        "late_fee": (inst["total_due"].to_numpy()[idx] * 0.005 * late_n).round(-2).astype("int64"),
        "payment_channel": rng.choice(PAY_CH, n_pay, p=PAY_W),
    })
    payments = payments.sort_values("paid_at").reset_index(drop=True)
    payments["payment_id"] = np.arange(1, n_pay + 1)

    return {"raw_products": PRODUCTS, "raw_customers": customers, "raw_applications": apps,
            "raw_loans": loans, "raw_installments": inst, "raw_payments": payments}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", choices=SIZES, default="medium")
    ap.add_argument("--customers", type=int, help="override customer count")
    ap.add_argument("--asof", default="2026-09-30", help="snapshot date (data ends here)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    n = a.customers or SIZES[a.size]
    tables = generate(n, pd.Timestamp(a.asof), a.seed)
    os.makedirs(a.out, exist_ok=True)
    total_mb = 0.0
    for name, df in tables.items():
        path = os.path.join(a.out, f"{name}.csv")
        df.to_csv(path, index=False)
        mb = os.path.getsize(path) / 1e6
        total_mb += mb
        print(f"{name:18s} {len(df):>10,} rows  {mb:7.1f} MB csv")
    print(f"{'TOTAL':18s} {sum(len(d) for d in tables.values()):>10,} rows  {total_mb:7.1f} MB csv")


if __name__ == "__main__":
    main()
