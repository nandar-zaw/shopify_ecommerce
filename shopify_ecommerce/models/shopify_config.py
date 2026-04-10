from odoo import models, fields, api
from odoo.exceptions import UserError
import requests

class ShopifyConfig(models.Model):
    _name        = 'shopify.config'
    _description = 'Shopify store configuration'
    _rec_name    = 'store_name'

    store_name      = fields.Char(string='Store name', required=True)
    store_url       = fields.Char(string='Store URL (.myshopify.com)', required=True)
    api_key         = fields.Char(string='API key')
    access_token    = fields.Char(string='Access token', required=True)
    webhook_secret  = fields.Char(string='Webhook secret')
    api_version     = fields.Char(string='API version', default='2024-01')
    is_active       = fields.Boolean(string='Active', default=True)
    sync_products   = fields.Boolean(string='Sync products', default=True)
    sync_orders     = fields.Boolean(string='Sync orders', default=True)
    sync_inventory  = fields.Boolean(string='Sync inventory', default=True)
    last_order_sync = fields.Datetime(string='Last order sync', readonly=True)
    sync_log_ids    = fields.One2many('shopify.sync', 'config_id', string='Sync history')

    def _get_headers(self):
        return {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json',
        }

    def _base_url(self):
        return f'https://{self.store_url}/admin/api/{self.api_version}'

    def action_test_connection(self):
        self.ensure_one()
        try:
            resp = requests.get(
                f'{self._base_url()}/shop.json',
                headers=self._get_headers(),
                timeout=10
            )
            resp.raise_for_status()
            shop = resp.json().get('shop', {})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection successful',
                    'message': f'Connected to: {shop.get("name")}',
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f'Connection failed: {e}')