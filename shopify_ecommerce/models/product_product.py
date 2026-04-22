import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopify_variant_id = fields.Char(string='Shopify Variant ID', copy=False, index=True)
    color = fields.Char(string='Color')
    size = fields.Char(string='Size')
    price_modifier = fields.Float(string='Price Modifier', default=0.0)

    @api.model
    def _shopflow_find_from_shopify_line_item(self, line_item):
        line_item = line_item or {}
        variant_id = str(line_item.get('variant_id') or '').strip()
        sku = (line_item.get('sku') or '').strip()
        product_id = str(line_item.get('product_id') or '').strip()

        product = self.browse()
        if variant_id:
            product = self.search([('shopify_variant_id', '=', variant_id)], limit=1)
        if not product and sku:
            product = self.search([('default_code', '=', sku)], limit=1)
        if not product and product_id:
            template = self.env['product.template'].search([('shopify_product_id', '=', product_id)], limit=1)
            product = template.product_variant_id if template else self.browse()

        return product

