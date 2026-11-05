from odoo import fields, models


class ForecastWizard(models.TransientModel):
    _name = 'smart.forecast.wizard'
    _description = 'Run Forecast Wizard'

    horizon_weeks = fields.Integer(string='Horizon (weeks)', default=4, required=True)

    def action_run(self):
        self.ensure_one()
        run = self.env['smart.forecast.run'].create({
            'trigger': 'manual',
            'horizon_weeks': self.horizon_weeks,
        })
        run.action_execute()
        if run.state == 'failed':
            # Not raising: an exception would roll back the saved 'failed' record
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Forecast failed',
                    'message': run.error_message,
                    'type': 'danger',
                    'sticky': True,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'smart.forecast.run',
                        'res_id': run.id,
                        'view_mode': 'form',
                    },
                },
            }
        return run.action_view_lines()
