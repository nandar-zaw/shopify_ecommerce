import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .shopify_client import ShopifyClientError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    shopify_product_id = fields.Char(string='Shopify Product ID', copy=False, index=True)
    shopify_synced = fields.Boolean(string='Synced to Shopify', default=False)
    shopify_synced_on = fields.Datetime(string='Last Synced On', readonly=True, copy=False)
    tags = fields.Char(string='Shopify Tags')

    def _build_shopify_options(self):
        self.ensure_one()
        options = []
        for line in self.attribute_line_ids.filtered(lambda l: l.value_ids):
            options.append(
                {
                    'name': line.attribute_id.name,
                    'values': line.value_ids.mapped('name'),
                }
            )
        return options

    def _build_shopify_variant_payload(self, variant):
        payload = {
            'title': variant.display_name,
            'price': str(variant.lst_price),
            'sku': variant.default_code or '',
            'inventory_quantity': int(variant.qty_available),
        }
        option_values = variant.product_template_attribute_value_ids[:3]
        for idx, value in enumerate(option_values, start=1):
            payload[f'option{idx}'] = value.product_attribute_value_id.name
        return payload

    def _build_shopify_payload(self):
        self.ensure_one()
        payload = {
            'title': self.name,
            'body_html': self.description_sale or self.description or '',
            'vendor': self.company_id.name or '',
            'status': 'active' if self.sale_ok and self.active else 'draft',
            'tags': self.tags or '',
            'variants': [self._build_shopify_variant_payload(v) for v in self.product_variant_ids],
        }
        options = self._build_shopify_options()
        if options:
            payload['options'] = options
        return {'product': payload}

    def action_export_to_shopify(self):
        self.ensure_one()
        client = self.env['shopify.config']._get_active_client()
        payload = self._build_shopify_payload()
        try:
            if self.shopify_product_id:
                payload.setdefault('product', {})['id'] = self.shopify_product_id
            result = client.upsert_product(payload)
            self._apply_shopify_product_response(result.get('product', {}))
        except ShopifyClientError as exc:
            _logger.exception('Failed to export product %s to Shopify', self.display_name)
            raise UserError(_('Failed to export product to Shopify: %s') % exc) from exc

        _logger.info('Product %s exported to Shopify product %s', self.display_name, self.shopify_product_id)
        return True

    def _apply_shopify_product_response(self, product_data):
        self.ensure_one()
        if not product_data:
            return

        self.write(
            {
                'shopify_product_id': str(product_data.get('id') or self.shopify_product_id or ''),
                'shopify_synced': True,
                'shopify_synced_on': fields.Datetime.now(),
            }
        )

        variants = product_data.get('variants', [])
        for variant in self.product_variant_ids:
            matched = False
            for shopify_variant in variants:
                if variant.default_code and shopify_variant.get('sku') == variant.default_code:
                    variant.shopify_variant_id = str(shopify_variant.get('id') or '')
                    matched = True
                    break
            if not matched and len(variants) == 1:
                variant.shopify_variant_id = str(variants[0].get('id') or '')

    @api.model
    def import_from_shopify(self):
        client = self.env['shopify.config']._get_active_client()
        imported = 0
        for product_data in client.iter_products(page_size=100):
            self._upsert_product_from_shopify(product_data)
            imported += 1

        _logger.info('Imported/updated %s Shopify products into Odoo', imported)
        return imported

    @api.model
    def _upsert_product_from_shopify(self, product_data):
        product = self.search([('shopify_product_id', '=', str(product_data.get('id')))], limit=1)
        variants = product_data.get('variants') or []
        primary_variant = variants[0] if variants else {}
        vals = {
            'name': product_data.get('title') or _('Shopify Product'),
            'description_sale': product_data.get('body_html') or '',
            'shopify_product_id': str(product_data.get('id') or ''),
            'tags': product_data.get('tags') or '',
            'shopify_synced': True,
            'shopify_synced_on': fields.Datetime.now(),
            'default_code': primary_variant.get('sku') or False,
            'list_price': float(primary_variant.get('price') or 0.0),
            'sale_ok': True,
        }
        if product:
            product.write(vals)
        else:
            product = self.create(vals)

        product._upsert_variants_from_shopify(variants)
        return product

    def _upsert_variants_from_shopify(self, variants):
        self.ensure_one()
        if not variants:
            return

        for shopify_variant in variants:
            variant_record = self.product_variant_ids.filtered(
                lambda v: v.shopify_variant_id == str(shopify_variant.get('id'))
            )[:1]
            if not variant_record and shopify_variant.get('sku'):
                variant_record = self.product_variant_ids.filtered(
                    lambda v: v.default_code == shopify_variant.get('sku')
                )[:1]
            if not variant_record:
                variant_record = self.product_variant_ids[:1]
            if not variant_record:
                continue

            list_price = float(shopify_variant.get('price') or 0.0)
            variant_record.write(
                {
                    'shopify_variant_id': str(shopify_variant.get('id') or ''),
                    'default_code': shopify_variant.get('sku') or variant_record.default_code,
                    'color': shopify_variant.get('option1') or variant_record.color,
                    'size': shopify_variant.get('option2') or variant_record.size,
                    'price_modifier': max(list_price - self.list_price, 0.0),
                }
            )

    def action_open_sync_wizard(self):
        return {
            'name': _('Sync Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'shopify.product.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_operation': 'export',
                'active_model': 'product.template',
                'active_ids': self.ids,
            },
        }

    def export_to_shopify(self):
        for product in self:
            _logger.info('Exporting product %s to Shopify', product.display_name)
            product.action_export_to_shopify()
