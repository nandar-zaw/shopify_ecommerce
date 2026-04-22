import json
import logging
import time

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .shopify_client import ShopifyClient, ShopifyClientError

_logger = logging.getLogger(__name__)


class ShopifyConfig(models.Model):
    _name = 'shopify.config'
    _description = 'Shopify Configuration'

    name = fields.Char(string='Store Name', required=True)
    store_url = fields.Char(string='Store URL', required=True, help='Store name or full myshopify domain')
    api_key = fields.Char(string='API Key')
    api_secret = fields.Char(string='API Secret', password=True)
    webhook_secret = fields.Char(string='Webhook Secret', password=True)
    api_version = fields.Char(string='API Version', default='2024-01', required=True)
    active = fields.Boolean(string='Active', default=True)
    last_tested_on = fields.Datetime(string='Last Connection Test')
    last_test_status = fields.Selection(
        [('success', 'Success'), ('failed', 'Failed')],
        string='Last Test Status',
        readonly=True,
        copy=False,
    )
    last_test_message = fields.Text(string='Last Test Message', readonly=True, copy=False)
    sync_log_ids = fields.One2many('shopify.sync.log', 'config_id', string='Sync Logs')

    def _token_cache_key(self):
        self.ensure_one()
        return f'shopify_ecommerce.token_cache.{self.id}'

    def _request_access_token(self):
        self.ensure_one()
        if not self.store_url or not self.api_key or not self.api_secret:
            raise UserError(_('Store URL, API Key, and API Secret are required to request a Shopify token.'))

        base_store = self.store_url.strip().lower().replace('https://', '').replace('http://', '')
        base_store = base_store.split('/')[0]
        if base_store.endswith('.myshopify.com'):
            base_store = base_store[: -len('.myshopify.com')]

        response = requests.post(
            f'https://{base_store}.myshopify.com/admin/oauth/access_token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'client_credentials',
                'client_id': self.api_key,
                'client_secret': self.api_secret,
            },
            timeout=30,
        )
        if not response.ok:
            raise UserError(_('Token request failed: %s') % response.status_code)

        payload = response.json()
        access_token = payload.get('access_token')
        expires_in = int(payload.get('expires_in') or 0)
        if not access_token:
            raise UserError(_('Shopify token response did not include an access token.'))

        cache_value = json.dumps(
            {
                'access_token': access_token,
                'expires_at': time.time() + expires_in if expires_in else 0,
            }
        )
        self.env['ir.config_parameter'].sudo().set_param(self._token_cache_key(), cache_value)
        return access_token

    def _get_access_token(self):
        self.ensure_one()
        cached = self.env['ir.config_parameter'].sudo().get_param(self._token_cache_key())
        if cached:
            try:
                data = json.loads(cached)
            except ValueError:
                data = {}
            token = data.get('access_token')
            expires_at = float(data.get('expires_at') or 0)
            if token and (not expires_at or time.time() < expires_at - 60):
                return token

        return self._request_access_token()

    @api.model
    def _get_active_config(self):
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise UserError(_('No active Shopify configuration found.'))
        if not config.store_url or not config.api_key or not config.api_secret:
            raise UserError(_('Active Shopify configuration is missing Store URL, API Key, or API Secret.'))
        return config

    def _get_client(self):
        self.ensure_one()
        return ShopifyClient(
            store=self.store_url,
            token=self._get_access_token(),
            api_version=self.api_version or '2024-01',
        )

    @api.model
    def _get_active_client(self):
        return self._get_active_config()._get_client()

    def action_test_connection(self):
        self.ensure_one()
        if not self.store_url or not self.api_key or not self.api_secret:
            raise UserError(_('Store URL, API Key, and API Secret are required to test the connection.'))

        try:
            client = ShopifyClient(
                store=self.store_url,
                token=self._get_access_token(),
                api_version=self.api_version or '2024-01',
            )
            payload = client.get_shop_identity()
            shop_name = payload.get('name') or payload.get('myshopifyDomain') or self.store_url
            message = _('Connected successfully to Shopify store: %s') % shop_name
            self.write(
                {
                    'last_tested_on': fields.Datetime.now(),
                    'last_test_status': 'success',
                    'last_test_message': message,
                }
            )
            _logger.info('Shopify connection test succeeded for config %s (%s)', self.id, self.store_url)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Shopify Connection'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
            }
        except ShopifyClientError as exc:
            error_message = str(exc)
            self.write(
                {
                    'last_tested_on': fields.Datetime.now(),
                    'last_test_status': 'failed',
                    'last_test_message': error_message,
                }
            )
            _logger.warning('Shopify connection test failed for config %s: %s', self.id, error_message)
            raise UserError(_('Shopify connection failed: %s') % error_message) from exc

    def action_sync_orders_now(self):
        self.ensure_one()
        result = self.env['shopify.sync'].sync_orders_from_shopify(config=self)
        message = _(
            'Order sync completed. Imported/checked: %(imported)s, Failed: %(failed)s, Log ID: %(log_id)s'
        ) % {
            'imported': result.get('imported', 0),
            'failed': result.get('failed', 0),
            'log_id': result.get('sync_log_id') or '-',
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shopify Order Sync'),
                'message': message,
                'type': 'warning' if result.get('failed') else 'success',
                'sticky': bool(result.get('failed')),
            },
        }


class ShopifySyncLog(models.Model):
    _name = 'shopify.sync.log'
    _description = 'Shopify Sync Log'
    _order = 'start_time desc, id desc'

    config_id = fields.Many2one('shopify.config', string='Configuration')
    sync_type = fields.Char(string='Sync Type')
    direction = fields.Selection([('inbound', 'Inbound'), ('outbound', 'Outbound')], string='Direction')
    status = fields.Selection(
        [('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')],
        string='Status',
        default='pending',
    )
    start_time = fields.Datetime(string='Start Time')
    end_time = fields.Datetime(string='End Time')
    error_message = fields.Text(string='Error Message')


class ShopifyWebhookEvent(models.Model):
    _name = 'shopify.webhook.event'
    _description = 'Shopify Webhook Event'
    _order = 'received_at desc, id desc'

    topic = fields.Char(string='Topic')
    payload = fields.Text(string='Payload')
    received_at = fields.Datetime(string='Received At', default=fields.Datetime.now)
    processing_status = fields.Selection(
        [('pending', 'Pending'), ('processed', 'Processed'), ('failed', 'Failed')],
        string='Processing Status',
        default='pending',
    )
    hmac_valid = fields.Boolean(string='HMAC Valid', default=False)

