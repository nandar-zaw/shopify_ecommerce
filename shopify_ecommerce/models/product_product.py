from odoo import models, fields

class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopify_variant_id  = fields.Char(string='Shopify variant ID', copy=False, index=True)
    reorder_threshold   = fields.Integer(string='Low stock threshold', default=5)