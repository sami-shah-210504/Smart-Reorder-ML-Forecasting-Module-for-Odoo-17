from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    forecast_qty = fields.Float(string='Forecast / week', readonly=True, copy=False)
    forecast_run_id = fields.Many2one('smart.forecast.run', string='Forecast Run',
                                      readonly=True, copy=False, ondelete='set null')
    forecast_updated = fields.Datetime(string='Forecast Updated', readonly=True, copy=False)

    def action_view_forecast_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Forecast History',
            'res_model': 'smart.forecast.line',
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', self.id)],
        }