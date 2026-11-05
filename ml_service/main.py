import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

from features import make_features
from features import recursive_forecast

app = FastAPI(title='Smart Reorder Forecast Service')
model = joblib.load('model.pkl')
MODEL_VERSION = 'ridge-lag-v1'


class Item(BaseModel):
    product_tmpl_id: int
    weekly_sales: list[dict]


class ForecastRequest(BaseModel):
    items: list[Item]
    horizon_weeks: int = 4


@app.get('/health')
def health():
    return {'ok': True, 'model_version': MODEL_VERSION}


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
            'forecast_lo': m * 0.8,
            'forecast_hi': m * 1.25,
            'model_version': MODEL_VERSION,
        })
        for _ in range(req.horizon_weeks):
            p = max(0.0, float(model.predict(np.array([make_features(hist)]))[0]))
            yhat.append(p)
            hist.append(p)
        m = float(np.mean(yhat))
        preds.append({
            'product_tmpl_id': item.product_tmpl_id,
            'weekly_forecast': m,
            'forecast_lo': m * 0.8,
            'forecast_hi': m * 1.25,
            'model_version': MODEL_VERSION,
        })
    return {'version': 1, 'predictions': preds}
