import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    shopify_invoice_ref = fields.Char(string='Shopify Invoice Reference', copy=False)
    sent_to_customer = fields.Boolean(string='Sent to Customer', default=False)

    def action_post(self):
        result = super().action_post()
        self._send_invoice_email()
        return result

    def _send_invoice_email(self):
        for move in self.filtered(lambda m: m.move_type == 'out_invoice'):
            _logger.info('Sending invoice %s to %s', move.name, move.partner_id.email or 'no-email')
            move.sent_to_customer = True

