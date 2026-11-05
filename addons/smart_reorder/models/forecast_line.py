from math import ceil

from odoo import api, fields, models


class ForecastLine(models.Model):
    _name = 'smart.forecast.line'
    _description = 'Forecast Line'
    _order = 'suggested_value desc, id'

    run_id = fields.Many2one('smart.forecast.run', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='run_id.company_id', store=True)
    product_id = fields.Many2one('product.template', required=True)
    weekly_forecast = fields.Float(required=True)
    forecast_lo = fields.Float(string='Low')
    forecast_hi = fields.Float(string='High')
    model_version = fields.Char()
    qty_available = fields.Float(string='On Hand', readonly=True)
    incoming_qty = fields.Float(string='Incoming', readonly=True)
    suggested_qty = fields.Float(compute='_compute_suggestion', store=True)
    suggested_value = fields.Float(compute='_compute_suggestion', store=True)

    @api.depends('weekly_forecast', 'qty_available', 'incoming_qty',
                 'product_id.standard_price', 'run_id.lead_time_weeks', 'run_id.safety_weeks')
    def _compute_suggestion(self):
        for line in self:
            weeks = line.run_id.lead_time_weeks + line.run_id.safety_weeks
            target = line.weekly_forecast * weeks
            on_hand = (line.qty_available or 0.0) + (line.incoming_qty or 0.0)
            line.suggested_qty = max(0.0, float(ceil(target - on_hand)))
            line.suggested_value = line.suggested_qty * (line.product_id.standard_price or 0.0)