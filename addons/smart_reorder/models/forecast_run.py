import logging
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.tools import float_round

_logger = logging.getLogger(__name__)
MIN_HISTORY_WEEKS = 8


class ForecastRun(models.Model):
    _name = 'smart.forecast.run'
    _description = 'Forecast Run'
    _order = 'id desc'

    name = fields.Char(required=True, default=lambda s: 'Run %s' % fields.Datetime.now())
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done'), ('failed', 'Failed')],
        default='draft', required=True)
    trigger = fields.Selection(
        [('manual', 'Manual'), ('cron', 'Scheduled')],
        default='manual', required=True)
    horizon_weeks = fields.Integer(string='Horizon (weeks)', default=4, required=True)
    lead_time_weeks = fields.Integer(default=lambda s: s._param('smart_reorder.lead_time_weeks', 2))
    safety_weeks = fields.Integer(default=lambda s: s._param('smart_reorder.safety_weeks', 1))
    product_count = fields.Integer(string='Products', readonly=True)
    error_message = fields.Text(string='Error', readonly=True)
    run_duration = fields.Float(string='Duration (s)', readonly=True)
    line_ids = fields.One2many('smart.forecast.line', 'run_id', string='Lines')
    
    @api.model
    def _param(self, key, default):
        return int(self.env['ir.config_parameter'].sudo().get_param(key, default))

    def _eligible_products(self):
        return self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('type', '=', 'product'),
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id),
        ])

    def _build_payload(self, products, min_weeks=MIN_HISTORY_WEEKS):
        if not products:
            return []
        self.env.cr.execute("""
            SELECT pp.product_tmpl_id,
                   date_trunc('week', so.date_order)::date AS week,
                   SUM(sol.product_uom_qty)
              FROM sale_order_line sol
              JOIN sale_order so ON so.id = sol.order_id
              JOIN product_product pp ON pp.id = sol.product_id
             WHERE so.state IN ('sale', 'done')
               AND so.company_id = %s
               AND pp.product_tmpl_id IN %s
          GROUP BY 1, 2
          ORDER BY 1, 2
        """, (self.company_id.id, tuple(products.ids)))

        series = {}
        for tmpl_id, week, qty in self.env.cr.fetchall():
            series.setdefault(tmpl_id, {})[week] = float(qty)

        this_week = date.today() - timedelta(days=date.today().weekday())
        payload = []
        for tmpl_id, weeks in series.items():
            cur, rows = min(weeks), []
            while cur < this_week:   # stop before the incomplete current week
                rows.append({'week': cur.isoformat(), 'qty': weeks.get(cur, 0.0)})
                cur += timedelta(weeks=1)
            if len(rows) >= min_weeks:
                payload.append({'product_tmpl_id': tmpl_id, 'weekly_sales': rows})
        return payload

    def action_execute(self):
        self.ensure_one()
        started = fields.Datetime.now()
        try:
            # savepoint: a failure leaves no orphan lines or partial product writes
            with self.env.cr.savepoint():
                self.line_ids.unlink()
                products = self._eligible_products()
                payload = self._build_payload(products)
                predictions = self.env['smart.forecast.service'].forecast(
                    payload, self.horizon_weeks)
                self._write_results(predictions)
            self.write({
                'state': 'done',
                'error_message': False,
                'product_count': len(predictions),
                'run_duration': (fields.Datetime.now() - started).total_seconds(),
            })
        except Exception as exc:
            _logger.exception('Forecast run %s failed', self.id)
            self.write({'state': 'failed', 'error_message': str(exc)})
        return True

    def _write_results(self, predictions):
        now = fields.Datetime.now()
        tmpls = self.env['product.template'].browse([p['product_tmpl_id'] for p in predictions])
        by_id = {t.id: t for t in tmpls}
        vals = []
        for p in predictions:
            t = by_id.get(p['product_tmpl_id'])
            if not t:
                continue
            vals.append({
                'run_id': self.id,
                'product_id': t.id,
                'weekly_forecast': p['weekly_forecast'],
                'forecast_lo': p.get('forecast_lo', 0.0),
                'forecast_hi': p.get('forecast_hi', 0.0),
                'model_version': p.get('model_version'),
                'qty_available': t.qty_available,
                'incoming_qty': t.incoming_qty,
            })
            t.write({
                'forecast_qty': float_round(p['weekly_forecast'], 2),
                'forecast_run_id': self.id,
                'forecast_updated': now,
            })
        self.env['smart.forecast.line'].create(vals)

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Suggestions',
            'res_model': 'smart.forecast.line',
            'view_mode': 'tree,form',
            'domain': [('run_id', '=', self.id)],
        }

    @api.model
    def _cron_weekly(self):
        self.create({'trigger': 'cron', 'horizon_weeks': 4}).action_execute()