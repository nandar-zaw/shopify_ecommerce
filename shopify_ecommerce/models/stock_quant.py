from odoo import models, fields, api

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    shopify_inventory_item_id = fields.Char(string='Shopify inventory item ID', copy=False)
    last_shopify_push         = fields.Datetime(string='Last pushed to Shopify', readonly=True)

    def _check_low_stock(self):
        """Called after every stock move to alert and push to Shopify."""
        for quant in self:
            threshold = quant.product_id.reorder_threshold
            if quant.quantity <= threshold:
                # Post internal message / trigger alert
                quant.product_id.message_post(
                    body=f'Low stock alert: {quant.quantity} units remaining '
                         f'(threshold: {threshold})'
                )