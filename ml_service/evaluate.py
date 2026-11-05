"""Rolling-origin backtest. Usage: python evaluate.py [history.csv] [horizon]"""
import sys

import joblib
import numpy as np
import pandas as pd

from features import recursive_forecast

CSV = sys.argv[1] if len(sys.argv) > 1 else 'history.csv'
H = int(sys.argv[2]) if len(sys.argv) > 2 else 4   # forecast horizon (weeks)
ORIGINS = 12                                        # past cut-off points per product
MIN_TRAIN = 8                                       # same gate as the Odoo module

model = joblib.load('model.pkl')
df = pd.read_csv(CSV).sort_values(['product_tmpl_id', 'week'])
series = {pid: g['qty'].to_numpy(float) for pid, g in df.groupby('product_tmpl_id')}

rows = []
for pid, s in series.items():
    last_origin = len(s) - H
    for o in range(max(MIN_TRAIN, last_origin - ORIGINS + 1), last_origin + 1):
        train, actual = s[:o], s[o:o + H]
        rows.append({
            'pid': pid,
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


print('%d products, %d forecasts, horizon %d weeks\n' % (len(series), len(rows), H))
print('%-8s %8s %8s %12s %8s' % ('', 'WAPE', 'MAPE', 'Horizon-MAPE', 'Bias'))
for key in ('model', 'naive'):
    w, m, h, b = score(key)
    print('%-8s %7.1f%% %7.1f%% %11.1f%% %+7.1f%%' % (key, w * 100, m * 100, h * 100, b * 100))

inside = [(r['model'].mean() * 0.8) <= r['actual'].mean() <= (r['model'].mean() * 1.25) for r in rows]
print('\nInterval coverage (actual horizon mean inside low/high band): %.0f%%' % (np.mean(inside) * 100))

per_product = {}
for r in rows:
    per_product.setdefault(r['pid'], []).append(np.abs(r['actual'] - r['model']).sum() / max(r['actual'].sum(), 1))
worst = sorted(per_product.items(), key=lambda kv: -np.mean(kv[1]))[:5]
print('\nWorst 5 products by WAPE:')
for pid, v in worst:
    print('  product %-5s %.1f%%' % (pid, np.mean(v) * 100))
