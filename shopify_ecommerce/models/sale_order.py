from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shopify_order_id    = fields.Char(string='Shopify order ID', copy=False, index=True)
    shopify_order_name  = fields.Char(string='Shopify order name', copy=False)  # e.g. #1001
    imported_from_shopify = fields.Boolean(string='Imported from Shopify', default=False)
    cart_id             = fields.Many2one('sale.cart', string='Source cart', readonly=True)