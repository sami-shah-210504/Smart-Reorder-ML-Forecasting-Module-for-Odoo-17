"""Rolling-origin backtest and interval calibration.
Usage: python evaluate.py [history.csv] [horizon]"""
import json
import sys

import joblib
import numpy as np
import pandas as pd

from features import recursive_forecast

CSV = sys.argv[1] if len(sys.argv) > 1 else 'history.csv'
H = int(sys.argv[2]) if len(sys.argv) > 2 else 4   # forecast horizon (weeks)
ORIGINS = 12                                        # past cut-off points per product
CAL_ORIGINS = 8                                     # first N origins fit the band, the rest test it
MIN_TRAIN = 8                                       # same gate as the Odoo module
TARGET = 0.80                                       # intended interval coverage

model = joblib.load('model.pkl')
df = pd.read_csv(CSV).sort_values(['product_tmpl_id', 'week'])
series = {pid: g['qty'].to_numpy(float) for pid, g in df.groupby('product_tmpl_id')}

rows = []
for pid, s in series.items():
    last_origin = len(s) - H
    start = max(MIN_TRAIN, last_origin - ORIGINS + 1)
    for k, o in enumerate(range(start, last_origin + 1)):
        train, actual = s[:o], s[o:o + H]
        rows.append({
            'pid': pid,
            'k': k,
            'actual': actual,
            'model': np.array(recursive_forecast(model, train, H)),
            'naive': np.full(H, train[-4:].mean()),
        })


def score(key):
    a = np.concatenate([r['actual'] for r in rows])
    f = np.concatenate([r[key] for r in rows])
    wape = np.abs(a - f).sum() / a.sum()
    nz = a > 0
    mape = np.mean(np.abs(a[nz] - f[nz]) / a[nz])
    am = np.array([r['actual'].mean() for r in rows])
    fm = np.array([r[key].mean() for r in rows])
    nz2 = am > 0
    hmape = np.mean(np.abs(am[nz2] - fm[nz2]) / am[nz2])
    bias = (f.sum() - a.sum()) / a.sum()
    return wape, mape, hmape, bias


def ratios(rs):
    a = np.array([r['actual'].mean() for r in rs])
    f = np.array([r['model'].mean() for r in rs])
    ok = f > 0
    return a[ok] / f[ok]


def coverage(rs, lo, hi):
    a = np.array([r['actual'].mean() for r in rs])
    f = np.array([r['model'].mean() for r in rs])
    return float(np.mean((f * lo <= a) & (a <= f * hi)))


print('%d products, %d forecasts, horizon %d weeks\n' % (len(series), len(rows), H))
print('%-8s %8s %8s %12s %8s' % ('', 'WAPE', 'MAPE', 'Horizon-MAPE', 'Bias'))
for key in ('model', 'naive'):
    w, m, h, b = score(key)
    print('%-8s %7.1f%% %7.1f%% %11.1f%% %+7.1f%%' % (key, w * 100, m * 100, h * 100, b * 100))

# ---- interval calibration ----
tail = (1 - TARGET) / 2
cal = [r for r in rows if r['k'] < CAL_ORIGINS]
test = [r for r in rows if r['k'] >= CAL_ORIGINS]

lo, hi = np.quantile(ratios(cal), [tail, 1 - tail])
print('\nInterval calibration (target %.0f%%)' % (TARGET * 100))
print('  fitted on %d forecasts, tested on %d held-out forecasts' % (len(cal), len(test)))
print('  old band x0.80 - x1.25 : held-out coverage %.0f%%' % (coverage(test, 0.8, 1.25) * 100))
print('  new band x%.2f - x%.2f : held-out coverage %.0f%%' % (lo, hi, coverage(test, lo, hi) * 100))

# final band: refit on every forecast, save for the service
lo_all, hi_all = np.quantile(ratios(rows), [tail, 1 - tail])
with open('interval.json', 'w') as f:
    json.dump({'lo': round(float(lo_all), 3), 'hi': round(float(hi_all), 3),
               'target': TARGET, 'horizon': H, 'n': len(rows)}, f, indent=2)
print('  saved interval.json: x%.2f - x%.2f' % (lo_all, hi_all))

per_product = {}
for r in rows:
    per_product.setdefault(r['pid'], []).append(
        np.abs(r['actual'] - r['model']).sum() / max(r['actual'].sum(), 1))
worst = sorted(per_product.items(), key=lambda kv: -np.mean(kv[1]))[:5]
print('\nWorst 5 products by WAPE:')
for pid, v in worst:
    print('  product %-5s %.1f%%' % (pid, np.mean(v) * 100))
