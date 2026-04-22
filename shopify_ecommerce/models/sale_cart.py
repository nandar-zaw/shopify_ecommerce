import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ShopifyCart(models.Model):
    _name = 'shopify.cart'
    _description = 'ShopFlow Cart'

    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    session_ref = fields.Char(string='Session Reference')
    discount_code = fields.Char(string='Discount Code')
    discount_amount = fields.Float(string='Discount Amount', default=0.0)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)
    state = fields.Selection(
        [('active', 'Active'), ('checked_out', 'Checked Out'), ('abandoned', 'Abandoned')],
        string='State',
        default='active',
        required=True,
    )
    cart_item_ids = fields.One2many('shopify.cart.item', 'cart_id', string='Cart Items')

    @api.depends('cart_item_ids.line_total', 'discount_amount')
    def _compute_subtotal(self):
        for cart in self:
            lines_total = sum(cart.cart_item_ids.mapped('line_total'))
            cart.subtotal = lines_total - cart.discount_amount


class ShopifyCartItem(models.Model):
    _name = 'shopify.cart.item'
    _description = 'ShopFlow Cart Item'

    cart_id = fields.Many2one('shopify.cart', string='Cart', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Integer(string='Quantity', default=1)
    unit_price = fields.Float(string='Unit Price')
    line_total = fields.Float(string='Line Total', compute='_compute_line_total', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_line_total(self):
        for item in self:
            item.line_total = item.quantity * item.unit_price
