import json
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

from features import recursive_forecast

app = FastAPI(title='Smart Reorder Forecast Service')

HERE = Path(__file__).parent
model = joblib.load(HERE / 'model.pkl')
MODEL_VERSION = 'ridge-lag-v1'

try:
    with open(HERE / 'interval.json') as f:
        BAND = json.load(f)
except FileNotFoundError:
    BAND = {'lo': 0.8, 'hi': 1.25}      # uncalibrated fallback


class Item(BaseModel):
    product_tmpl_id: int
    weekly_sales: list[dict]


class ForecastRequest(BaseModel):
    items: list[Item]
    horizon_weeks: int = 4


@app.get('/health')
def health():
    return {'ok': True, 'model_version': MODEL_VERSION, 'band': BAND}


@app.post('/v1/forecast')
def forecast(req: ForecastRequest):
    preds = []
    for item in req.items:
        hist = [float(r['qty']) for r in sorted(item.weekly_sales, key=lambda r: r['week'])]
        if len(hist) < 4:
            continue
        yhat = recursive_forecast(model, hist, req.horizon_weeks)
        m = float(np.mean(yhat))
        preds.append({
            'product_tmpl_id': item.product_tmpl_id,
            'weekly_forecast': m,
            'forecast_lo': m * BAND['lo'],
            'forecast_hi': m * BAND['hi'],
            'model_version': MODEL_VERSION,
        })
    return {'version': 1, 'predictions': preds}