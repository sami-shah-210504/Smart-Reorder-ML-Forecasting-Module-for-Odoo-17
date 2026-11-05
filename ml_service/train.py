"""Offline training. Usage: python train.py [history.csv]
CSV columns: product_tmpl_id,week,qty. Without a CSV, trains on synthetic data."""
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from features import make_features


def synthetic(n=200, weeks=80, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        base, amp = rng.uniform(2, 40), rng.uniform(0, 0.4)
        t = np.arange(weeks)
        mu = base * (1 + amp * np.sin(2 * np.pi * t / 52))
        out.append(np.maximum(0, rng.poisson(mu)).astype(float))
    return out


def main():
    if len(sys.argv) > 1:
        df = pd.read_csv(sys.argv[1]).sort_values(['product_tmpl_id', 'week'])
        series = [g['qty'].to_numpy(float) for _, g in df.groupby('product_tmpl_id')]
    else:
        series = synthetic()

    X, y = [], []
    for s in series:
        for i in range(8, len(s)):
            X.append(make_features(s[:i]))
            y.append(s[i])

    model = Ridge(alpha=1.0).fit(np.array(X), np.array(y))
    joblib.dump(model, 'model.pkl')
    print('trained on', len(X), 'samples, R2 =', round(model.score(np.array(X), np.array(y)), 3))


if __name__ == '__main__':
    main()
