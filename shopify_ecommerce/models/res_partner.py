import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    shopflow_customer_id = fields.Char(string='ShopFlow Customer ID', copy=False, index=True)
    loyalty_points = fields.Integer(string='Loyalty Points', default=0)
    registration_date = fields.Date(string='Registration Date')
    shopflow_address_type = fields.Selection(
        [('billing', 'Billing'), ('shipping', 'Shipping')],
        string='ShopFlow Address Type',
    )

    _sql_constraints = [
        (
            'shopflow_customer_id_unique',
            'unique(shopflow_customer_id)',
            'ShopFlow Customer ID must be unique.',
        ),
    ]

    def init(self):
        super().init()
        # Keep partner emails unique only for records participating in ShopFlow sync.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS res_partner_shopflow_email_unique_idx
            ON res_partner (lower(email))
            WHERE shopflow_customer_id IS NOT NULL AND email IS NOT NULL
            """
        )

    @api.model
    def sync_from_shopify(self, customer_data):
        customer_data = customer_data or {}
        shopify_customer_id = str(customer_data.get('id') or '').strip()
        email = (customer_data.get('email') or '').strip().lower()
        first_name = (customer_data.get('first_name') or '').strip()
        last_name = (customer_data.get('last_name') or '').strip()
        name = ' '.join(part for part in [first_name, last_name] if part) or email or _('Shopify Customer')

        partner = self.browse()
        if shopify_customer_id:
            partner = self.search([('shopflow_customer_id', '=', shopify_customer_id)], limit=1)
        if not partner and email:
            partner = self.search([('email', '=', email)], limit=1)

        vals = {
            'name': name,
            'email': email or False,
            'shopflow_customer_id': shopify_customer_id or False,
        }
        vals = {key: value for key, value in vals.items() if value is not False}

        if partner:
            partner.write(vals)
            return partner

        return self.create(vals)

    @api.model
    def _shopflow_upsert_from_shopify_customer(self, customer_data, order_data=None):
        customer_data = customer_data or {}
        order_data = order_data or {}

        shopify_customer_id = str(customer_data.get('id') or '').strip()
        email = (customer_data.get('email') or order_data.get('email') or '').strip().lower()
        name = (
            customer_data.get('name')
            or ' '.join(filter(None, [customer_data.get('first_name'), customer_data.get('last_name')]))
            or order_data.get('name')
            or email
            or _('Shopify Customer')
        )

        partner = self.browse()
        if shopify_customer_id:
            partner = self.search([('shopflow_customer_id', '=', shopify_customer_id)], limit=1)
        if not partner and email:
            partner = self.search([('email', '=', email)], limit=1)

        vals = {
            'name': name,
            'email': email or False,
            'phone': customer_data.get('phone') or order_data.get('phone') or False,
            'mobile': customer_data.get('phone') or order_data.get('phone') or False,
            'shopflow_customer_id': shopify_customer_id or False,
            'registration_date': fields.Date.to_date((customer_data.get('created_at') or order_data.get('created_at') or '')[:10])
            if (customer_data.get('created_at') or order_data.get('created_at'))
            else False,
        }
        vals = {key: value for key, value in vals.items() if value is not False}

        if partner:
            partner.write(vals)
            return partner

        return self.create(vals)

