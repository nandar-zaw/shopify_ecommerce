import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shopify_order_id = fields.Char(string='Shopify Order ID', copy=False, index=True)
    cart_id = fields.Many2one('shopify.cart', string='ShopFlow Cart')
    shipping_cost = fields.Float(string='Shipping Cost', default=0.0)

    _sql_constraints = [
        ('shopify_order_id_unique', 'unique(shopify_order_id)', 'Shopify Order ID must be unique.'),
    ]

    def action_confirm(self):
        if self.env.context.get('skip_shopflow_invoice_check'):
            return super().action_confirm()

        for order in self:
            unpaid_invoice = self.env['account.move'].search(
                [
                    ('partner_id', '=', order.partner_id.commercial_partner_id.id),
                    ('payment_state', '!=', 'paid'),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                ],
                limit=1,
            )
            if unpaid_invoice:
                raise ValidationError(
                    'Customer has an outstanding unpaid invoice. '
                    'Please settle it before placing a new order.'
                )
        return super().action_confirm()

    @api.model
    def _shopflow_import_from_shopify_order(self, order_data):
        order_data = order_data or {}
        shopify_order_id = str(order_data.get('id') or '').strip()
        if not shopify_order_id:
            raise ValidationError(_('Shopify order payload is missing an order id.'))

        existing = self.search([('shopify_order_id', '=', shopify_order_id)], limit=1)
        if existing:
            _logger.info('Skipping already imported Shopify order %s', shopify_order_id)
            return existing

        customer = order_data.get('customer') or {}
        partner = self.env['res.partner']._shopflow_upsert_from_shopify_customer(customer, order_data)

        lines = []
        for line_item in order_data.get('line_items') or []:
            product = self.env['product.product']._shopflow_find_from_shopify_line_item(line_item)
            if not product:
                _logger.warning(
                    'Skipping Shopify order line %s for order %s because no matching product was found',
                    line_item.get('id'),
                    shopify_order_id,
                )
                continue

            quantity = float(line_item.get('quantity') or 0.0)
            price_unit = float(line_item.get('price') or product.lst_price or 0.0)
            lines.append(
                (
                    0,
                    0,
                    {
                        'product_id': product.id,
                        'name': line_item.get('title') or product.display_name,
                        'product_uom_qty': quantity,
                        'product_uom': product.uom_id.id,
                        'price_unit': price_unit,
                    },
                )
            )

        shipping_cost = 0.0
        shipping_lines = order_data.get('shipping_lines') or []
        if shipping_lines:
            try:
                shipping_cost = float(shipping_lines[0].get('price') or 0.0)
            except (TypeError, ValueError):
                shipping_cost = 0.0

        vals = {
            'partner_id': partner.id,
            'partner_invoice_id': partner.id,
            'partner_shipping_id': partner.id,
            'shopify_order_id': shopify_order_id,
            'shipping_cost': shipping_cost,
            'client_order_ref': order_data.get('name') or order_data.get('order_number') or shopify_order_id,
            'note': order_data.get('note') or False,
            'order_line': lines,
        }

        order = self.create(vals)
        _logger.info('Created sale order %s from Shopify order %s', order.name, shopify_order_id)

        if (order_data.get('financial_status') or '').lower() == 'paid':
            order.with_context(skip_shopflow_invoice_check=True).action_confirm()
            order._shopflow_validate_pickings_from_shopify()

        return order

    def _shopflow_validate_pickings_from_shopify(self):
        for order in self:
            pickings = order.picking_ids.filtered(lambda picking: picking.state not in ('done', 'cancel'))
            for picking in pickings:
                try:
                    picking.action_assign()
                    for move in picking.move_ids_without_package.filtered(lambda move: move.state not in ('done', 'cancel')):
                        move.quantity_done = move.product_uom_qty

                    action = picking.button_validate()
                    if isinstance(action, dict) and action.get('res_model'):
                        model = action['res_model']
                        wizard = self.env[model].with_context(action.get('context') or {}).create({})
                        if hasattr(wizard, 'process'):
                            wizard.process()
                        elif hasattr(wizard, 'process_cancel_backorder'):
                            wizard.process_cancel_backorder()
                    _logger.info('Validated picking %s for Shopify order %s', picking.name, order.shopify_order_id)
                except Exception:  # pylint: disable=broad-except
                    _logger.exception(
                        'Failed to auto-validate picking %s for Shopify order %s',
                        picking.name,
                        order.shopify_order_id,
                    )

