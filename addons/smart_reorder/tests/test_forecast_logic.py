from unittest.mock import patch

from odoo.tests.common import TransactionCase

SERVICE = 'odoo.addons.smart_reorder.services.forecaster.ForecastService.forecast'


class TestForecastLogic(TransactionCase):

    def setUp(self):
        super().setUp()
        self.run_rec = self.env['smart.forecast.run'].create({'trigger': 'manual'})
        self.tmpl = self.env['product.template'].create({
            'name': 'SR Test', 'type': 'product', 'standard_price': 2.0})

    def _line(self, forecast, avail, incoming=0.0):
        return self.env['smart.forecast.line'].create({
            'run_id': self.run_rec.id,
            'product_id': self.tmpl.id,
            'weekly_forecast': forecast,
            'qty_available': avail,
            'incoming_qty': incoming,
        })

    def test_suggestion_basic(self):
        line = self._line(10.0, 15.0)      # need 10 * (2+1) = 30, have 15 -> order 15
        self.assertEqual(line.suggested_qty, 15.0)
        self.assertEqual(line.suggested_value, 30.0)

    def test_suggestion_never_negative(self):
        self.assertEqual(self._line(2.0, 500.0).suggested_qty, 0.0)

    def test_incoming_counts(self):
        self.assertEqual(self._line(10.0, 10.0, 20.0).suggested_qty, 0.0)

    def test_failed_run_captured(self):
        with patch(SERVICE, side_effect=Exception('boom')):
            self.run_rec.action_execute()
        self.assertEqual(self.run_rec.state, 'failed')
        self.assertIn('boom', self.run_rec.error_message)
        self.assertFalse(self.run_rec.line_ids)

    def test_success_writes_lines_and_product(self):
        preds = [{'product_tmpl_id': self.tmpl.id, 'weekly_forecast': 5.0,
                  'forecast_lo': 4.0, 'forecast_hi': 6.0, 'model_version': 't'}]
        with patch(SERVICE, return_value=preds), \
             patch.object(type(self.run_rec), '_build_payload', return_value=[{}]):
            self.run_rec.action_execute()
        self.assertEqual(self.run_rec.state, 'done')
        self.assertEqual(len(self.run_rec.line_ids), 1)
        self.assertEqual(self.tmpl.forecast_qty, 5.0)

    def test_create_rfq_groups_by_vendor_and_is_idempotent(self):
        vendor = self.env['res.partner'].create({'name': 'SR Vendor'})
        self.env['product.supplierinfo'].create({
            'partner_id': vendor.id, 'product_tmpl_id': self.tmpl.id,
            'price': 2.0, 'min_qty': 0})
        line = self._line(10.0, 15.0)                # suggests 15
        line.action_create_purchase_orders()

        po = line.purchase_order_id
        self.assertTrue(po)
        self.assertEqual(po.partner_id, vendor)
        self.assertEqual(po.order_line.product_qty, 15.0)

        line.action_create_purchase_orders()         # second click
        self.assertEqual(self.env['purchase.order'].search_count(
            [('partner_id', '=', vendor.id)]), 1)

    def test_create_rfq_skips_product_without_vendor(self):
        line = self._line(10.0, 15.0)
        line.action_create_purchase_orders()
        self.assertFalse(line.purchase_order_id)