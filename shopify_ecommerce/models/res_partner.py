from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    loyalty_points     = fields.Integer(string='Loyalty points', default=0)
    shopify_customer_id = fields.Char(string='Shopify customer ID', copy=False, index=True)
    # Addresses are already handled natively by res.partner hierarchy
    # (child_ids with type='delivery' / 'invoice')