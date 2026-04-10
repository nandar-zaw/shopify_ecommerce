from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    shopify_product_id  = fields.Char(string='Shopify product ID', copy=False, index=True)
    shopify_synced_on   = fields.Datetime(string='Last synced to Shopify', readonly=True)
    is_published        = fields.Boolean(string='Published on store', default=False)
    ai_rec_count        = fields.Integer(
        string='Times recommended',
        compute='_compute_ai_rec_count', store=False
    )

    def _compute_ai_rec_count(self):
        for rec in self:
            rec.ai_rec_count = self.env['shopify.ai.recommendation'].search_count([
                ('product_id', '=', rec.id)
            ])

    def action_export_to_shopify(self):
        self.ensure_one()
        self.env['shopify.sync'].create({
            'sync_type': 'product',
            'direction': 'odoo_to_shopify',
            'ref_id': str(self.id),
        }).execute()