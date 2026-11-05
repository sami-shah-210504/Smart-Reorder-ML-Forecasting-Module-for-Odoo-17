import numpy as np


def make_features(h):
    h = list(h)
    return [h[-1], h[-2], h[-4], float(np.mean(h[-4:])), float(np.std(h[-4:]))]


def recursive_forecast(model, history, horizon):
    """Predict one week ahead, append it to the history, repeat."""
    hist = list(history)
    out = []
    for _ in range(horizon):
        p = max(0.0, float(model.predict(np.array([make_features(hist)]))[0]))
        out.append(p)
        hist.append(p)
    return out