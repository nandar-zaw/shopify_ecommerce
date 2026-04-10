from odoo import models, fields, api

class SaleCart(models.Model):
    _name        = 'sale.cart'
    _description = 'Shopping cart'
    _rec_name    = 'name'

    name            = fields.Char(string='Cart ref', compute='_compute_name')
    partner_id      = fields.Many2one('res.partner', string='Customer', ondelete='cascade')
    session_id      = fields.Char(string='Session ID', index=True)
    discount_code   = fields.Char(string='Discount code')
    discount_amount = fields.Monetary(string='Discount amount', currency_field='currency_id')
    currency_id     = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    subtotal        = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)
    state           = fields.Selection([
        ('active',    'Active'),
        ('converted', 'Converted to order'),
        ('abandoned', 'Abandoned'),
    ], default='active', string='Status')
    line_ids        = fields.One2many('sale.cart.line', 'cart_id', string='Cart items')
    sale_order_id   = fields.Many2one('sale.order', string='Converted order', readonly=True)
    created_at      = fields.Datetime(string='Created', default=fields.Datetime.now)

    def _compute_name(self):
        for cart in self:
            cart.name = f'Cart #{cart.id or "new"}'

    @api.depends('line_ids.line_total')
    def _compute_subtotal(self):
        for cart in self:
            cart.subtotal = sum(cart.line_ids.mapped('line_total'))

    def action_convert_to_order(self):
        """Convert this cart into a confirmed sale.order."""
        self.ensure_one()
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'origin':     f'Cart #{self.id}',
            'order_line': [(0, 0, {
                'product_id':    line.product_id.id,
                'product_uom_qty': line.quantity,
                'price_unit':    line.unit_price,
            }) for line in self.line_ids],
        })
        self.write({'state': 'converted', 'sale_order_id': order.id})
        return order


class SaleCartLine(models.Model):
    _name        = 'sale.cart.line'
    _description = 'Cart line item'

    cart_id         = fields.Many2one('sale.cart', string='Cart', ondelete='cascade', required=True)
    product_id      = fields.Many2one('product.product', string='Product variant', required=True)
    quantity        = fields.Integer(string='Quantity', default=1)
    unit_price      = fields.Float(string='Unit price', digits=(16, 2))
    line_total      = fields.Float(string='Line total', compute='_compute_total', store=True)
    added_at        = fields.Datetime(string='Added', default=fields.Datetime.now)

    @api.depends('quantity', 'unit_price')
    def _compute_total(self):
        for line in self:
            line.line_total = line.quantity * line.unit_price

    @api.onchange('product_id')
    def _onchange_product(self):
        if self.product_id:
            self.unit_price = self.product_id.lst_price