import numpy as np


def make_features(h):
    h = list(h)
    return [h[-1], h[-2], h[-4], float(np.mean(h[-4:])), float(np.std(h[-4:]))]
