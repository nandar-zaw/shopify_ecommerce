import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    reorder_threshold = fields.Float(string='Reorder Threshold', default=0.0)
    low_stock_alert = fields.Boolean(
        string='Low Stock Alert',
        compute='_compute_low_stock_alert',
        store=True,
    )

    @api.depends('quantity', 'reorder_threshold')
    def _compute_low_stock_alert(self):
        for quant in self:
            quant.low_stock_alert = quant.quantity <= quant.reorder_threshold

    def write(self, vals):
        result = super().write(vals)
        if {'reserved_quantity', 'quantity'} & set(vals.keys()):
            self._push_stock_to_shopify()
        return result

    def _push_stock_to_shopify(self):
        for quant in self:
            _logger.info('Pushing stock for %s to Shopify', quant.product_id.display_name)
