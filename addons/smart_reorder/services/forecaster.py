import logging

import requests

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_URL = 'http://host.docker.internal:8000/v1/forecast'
TIMEOUT = 30
RETRIES = 1


class ForecastService(models.AbstractModel):
    _name = 'smart.forecast.service'
    _description = 'Forecasting Service Client'

    def forecast(self, payload, horizon_weeks):
        if not payload:
            return []
        url = self.env['ir.config_parameter'].sudo().get_param(
            'smart_reorder.service_url', DEFAULT_URL)
        body = {'items': payload, 'horizon_weeks': horizon_weeks}

        last_error = None
        for attempt in range(RETRIES + 1):
            try:
                resp = requests.post(url, json=body, timeout=TIMEOUT)
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error = exc
                _logger.warning('Forecast service attempt %s failed: %s', attempt + 1, exc)
        else:
            raise UserError('Forecasting service unavailable: %s' % last_error)

        data = resp.json()
        if data.get('version') != 1:
            raise UserError('Unsupported service contract version.')
        return data['predictions']