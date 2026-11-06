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
    purchase_order_id = fields.Many2one('purchase.order', string='RFQ',
                                        readonly=True, copy=False, ondelete='set null')
    @api.depends('weekly_forecast', 'qty_available', 'incoming_qty',
                 'product_id.standard_price', 'run_id.lead_time_weeks', 'run_id.safety_weeks')
    def _compute_suggestion(self):
        for line in self:
            weeks = line.run_id.lead_time_weeks + line.run_id.safety_weeks
            target = line.weekly_forecast * weeks
            on_hand = (line.qty_available or 0.0) + (line.incoming_qty or 0.0)
            line.suggested_qty = max(0.0, float(ceil(target - on_hand)))
            line.suggested_value = line.suggested_qty * (line.product_id.standard_price or 0.0)

    def action_create_purchase_orders(self):
        """One draft RFQ per primary vendor for the selected lines."""
        lines = self.filtered(lambda l: l.suggested_qty > 0 and not l.purchase_order_id)
        by_vendor = {}
        no_vendor = 0
        for line in lines:
            seller = line.product_id.seller_ids[:1]
            if not seller:
                no_vendor += 1
                continue
            by_vendor.setdefault(seller.partner_id, self.browse())
            by_vendor[seller.partner_id] |= line

        orders = self.env['purchase.order']
        for partner, vlines in by_vendor.items():
            po = self.env['purchase.order'].create({
                'partner_id': partner.id,
                'order_line': [(0, 0, {
                    'product_id': l.product_id.product_variant_id.id,
                    'name': l.product_id.display_name,
                    'product_qty': l.suggested_qty,
                    'product_uom': l.product_id.uom_po_id.id,
                }) for l in vlines],
            })
            vlines.write({'purchase_order_id': po.id})
            orders |= po

        if not orders:
            return self._notify(
                'No RFQs created', 'warning',
                'Nothing to order, or already ordered. %d line(s) skipped: no vendor.' % no_vendor)

        action = {
            'type': 'ir.actions.act_window',
            'name': 'Draft RFQs',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', orders.ids)],
        }
        if no_vendor:
            return self._notify(
                '%d RFQ(s) created' % len(orders), 'warning',
                '%d line(s) skipped because the product has no vendor.' % no_vendor,
                next_action=action)
        return action

    def _notify(self, title, kind, message, next_action=None):
        params = {'title': title, 'message': message, 'type': kind, 'sticky': False}
        if next_action:
            params['next'] = next_action
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': params}