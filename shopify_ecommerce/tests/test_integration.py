from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


class _FakeCustomerClientSuccess:
    @staticmethod
    def _extract_gid_numeric_id(gid):
        value = str(gid or '').strip()
        if '/' in value:
            return value.rsplit('/', 1)[-1]
        return value

    def graphql(self, query, variables=None):
        return {
            'customers': {
                'edges': [
                    {
                        'node': {
                            'id': 'gid://shopify/Customer/1001',
                            'firstName': 'Jane',
                            'lastName': 'Doe',
                            'email': 'jane@example.com',
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'endCursor': None,
                },
            }
        }


class _FakeCustomerClientSinglePage:
    @staticmethod
    def _extract_gid_numeric_id(gid):
        value = str(gid or '').strip()
        if '/' in value:
            return value.rsplit('/', 1)[-1]
        return value

    def graphql(self, query, variables=None):
        return {
            'customers': {
                'edges': [
                    {
                        'node': {
                            'id': 'gid://shopify/Customer/2002',
                            'firstName': 'Err',
                            'lastName': 'Case',
                            'email': 'err@example.com',
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'endCursor': None,
                },
            }
        }


@tagged('post_install', '-at_install')
class TestShopifyEcommerceIntegration(TransactionCase):
    def setUp(self):
        super().setUp()
        self.config = self.env['shopify.config'].create(
            {
                'name': 'Test Store',
                'store_url': 'test-store.myshopify.com',
                'api_key': 'key',
                'api_secret': 'secret',
                'active': True,
            }
        )

    def test_shopify_config_creation_defaults(self):
        self.assertEqual(self.config.api_version, '2024-01')
        self.assertTrue(self.config.active)
        self.assertEqual(self.config.name, 'Test Store')

    def test_sync_type_selection_contains_customer(self):
        selection = self.env['shopify.sync']._fields['sync_type'].selection
        self.assertIn(('customer', 'Customer'), selection)

    def test_res_partner_sync_from_shopify_creates_and_updates(self):
        payload = {
            'id': '9001',
            'email': 'first@example.com',
            'first_name': 'First',
            'last_name': 'User',
        }
        partner = self.env['res.partner'].sync_from_shopify(payload)
        self.assertEqual(partner.shopflow_customer_id, '9001')
        self.assertEqual(partner.email, 'first@example.com')
        self.assertEqual(partner.name, 'First User')

        updated = self.env['res.partner'].sync_from_shopify(
            {
                'id': '9001',
                'email': 'updated@example.com',
                'first_name': 'Updated',
                'last_name': 'Name',
            }
        )
        self.assertEqual(updated.id, partner.id)
        self.assertEqual(updated.email, 'updated@example.com')
        self.assertEqual(updated.name, 'Updated Name')

    def test_product_template_shopify_fields_are_updated(self):
        product = self.env['product.template'].create(
            {
                'name': 'Sync Product',
                'type': 'consu',
                'list_price': 50.0,
            }
        )
        self.assertFalse(product.shopify_synced)
        self.assertFalse(product.shopify_product_id)

        product._apply_shopify_product_response(
            {
                'id': '3003',
                'variants': [
                    {
                        'id': '4004',
                    }
                ],
            }
        )
        self.assertTrue(product.shopify_synced)
        self.assertEqual(product.shopify_product_id, '3003')
        self.assertTrue(product.shopify_synced_on)

    def test_sync_customers_from_shopify_writes_success_log(self):
        with patch(
            'odoo.addons.shopify_ecommerce.models.shopify_config.ShopifyConfig._get_client',
            return_value=_FakeCustomerClientSuccess(),
        ):
            result = self.env['shopify.sync'].sync_customers_from_shopify(config=self.config)

        self.assertEqual(result['imported'], 1)
        self.assertEqual(result['failed'], 0)

        sync_log = self.env['shopify.sync.log'].browse(result['sync_log_id'])
        self.assertEqual(sync_log.status, 'success')
        self.assertEqual(sync_log.sync_type, 'customer')
        partner = self.env['res.partner'].search([('shopflow_customer_id', '=', '1001')], limit=1)
        self.assertTrue(partner)

    def test_sync_customers_from_shopify_marks_failed_log_on_item_error(self):
        with patch(
            'odoo.addons.shopify_ecommerce.models.shopify_config.ShopifyConfig._get_client',
            return_value=_FakeCustomerClientSinglePage(),
        ), patch(
            'odoo.addons.shopify_ecommerce.models.res_partner.ResPartner.sync_from_shopify',
            side_effect=Exception('forced sync error'),
        ):
            result = self.env['shopify.sync'].sync_customers_from_shopify(config=self.config)

        self.assertEqual(result['imported'], 0)
        self.assertEqual(result['failed'], 1)

        sync_log = self.env['shopify.sync.log'].browse(result['sync_log_id'])
        self.assertEqual(sync_log.status, 'failed')
        self.assertIn('forced sync error', sync_log.error_message or '')

