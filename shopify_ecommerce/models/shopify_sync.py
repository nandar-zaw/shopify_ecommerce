from odoo import models, fields

class ShopifySync(models.Model):
    _name        = 'shopify.sync'
    _description = 'Shopify sync operation log'
    _order       = 'started_at desc'

    config_id    = fields.Many2one('shopify.config', string='Store config', required=True, ondelete='cascade')
    sync_type    = fields.Selection([
        ('product',   'Product'),
        ('order',     'Order'),
        ('inventory', 'Inventory'),
        ('full',      'Full sync'),
    ], string='Sync type', required=True)
    direction    = fields.Selection([
        ('odoo_to_shopify', 'Odoo → Shopify'),
        ('shopify_to_odoo', 'Shopify → Odoo'),
        ('bidirectional',   'Bidirectional'),
    ], string='Direction', required=True)
    status       = fields.Selection([
        ('pending',  'Pending'),
        ('running',  'Running'),
        ('success',  'Success'),
        ('failed',   'Failed'),
    ], default='pending', string='Status')
    ref_id       = fields.Char(string='Record ref')
    started_at   = fields.Datetime(string='Started', default=fields.Datetime.now)
    completed_at = fields.Datetime(string='Completed', readonly=True)
    records_processed = fields.Integer(string='Records processed', default=0)
    error_message = fields.Text(string='Error message')

    def execute(self):
        """Override in subclass or call specific sync method."""
        pass


class ShopifyWebhookEvent(models.Model):
    _name        = 'shopify.webhook.event'
    _description = 'Incoming Shopify webhook event'
    _order       = 'received_at desc'

    topic        = fields.Char(string='Topic', required=True)   # e.g. orders/create
    payload      = fields.Text(string='Raw payload (JSON)')
    received_at  = fields.Datetime(string='Received', default=fields.Datetime.now)
    processed    = fields.Boolean(string='Processed', default=False)
    hmac_valid   = fields.Boolean(string='HMAC verified', default=False)
    error_msg    = fields.Text(string='Processing error')
    sale_order_id = fields.Many2one('sale.order', string='Created order', readonly=True)