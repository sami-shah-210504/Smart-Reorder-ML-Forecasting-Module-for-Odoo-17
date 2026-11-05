from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestSecurity(TransactionCase):

    def test_plain_user_cannot_read_runs(self):
        user = self.env['res.users'].create({
            'name': 'Plain', 'login': 'sr_plain',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['smart.forecast.run'].with_user(user).search([])

    def test_manager_group_can(self):
        user = self.env['res.users'].create({
            'name': 'Mgr', 'login': 'sr_mgr',
            'groups_id': [(6, 0, [self.env.ref('smart_reorder.group_smart_reorder_manager').id])]})
        self.env['smart.forecast.run'].with_user(user).search([])
