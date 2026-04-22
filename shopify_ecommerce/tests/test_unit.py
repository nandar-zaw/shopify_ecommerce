import unittest


def _map_customer_data(customer_data):
    customer_data = customer_data or {}
    shopify_customer_id = str(customer_data.get('id') or '').strip()
    email = (customer_data.get('email') or '').strip().lower()
    first_name = (customer_data.get('first_name') or '').strip()
    last_name = (customer_data.get('last_name') or '').strip()
    name = ' '.join(part for part in [first_name, last_name] if part) or email or 'Shopify Customer'
    return {
        'name': name,
        'email': email,
        'shopflow_customer_id': shopify_customer_id,
    }


class TestResPartnerSyncFromShopifyMapping(unittest.TestCase):
    def test_maps_basic_fields(self):
        payload = {
            'id': 101,
            'email': 'alice@example.com',
            'first_name': 'Alice',
            'last_name': 'Lee',
        }
        mapped = _map_customer_data(payload)

        self.assertEqual(mapped['shopflow_customer_id'], '101')
        self.assertEqual(mapped['email'], 'alice@example.com')
        self.assertEqual(mapped['name'], 'Alice Lee')

    def test_normalizes_email_and_id(self):
        payload = {
            'id': '  202  ',
            'email': '  BOB@EXAMPLE.COM  ',
            'first_name': 'Bob',
            'last_name': 'M.',
        }
        mapped = _map_customer_data(payload)

        self.assertEqual(mapped['shopflow_customer_id'], '202')
        self.assertEqual(mapped['email'], 'bob@example.com')
        self.assertEqual(mapped['name'], 'Bob M.')

    def test_name_falls_back_to_email(self):
        payload = {
            'id': '303',
            'email': 'no.name@example.com',
            'first_name': '',
            'last_name': '',
        }
        mapped = _map_customer_data(payload)

        self.assertEqual(mapped['name'], 'no.name@example.com')

    def test_name_falls_back_to_shopify_customer_label(self):
        payload = {
            'id': '404',
            'email': '',
            'first_name': '',
            'last_name': '',
        }
        mapped = _map_customer_data(payload)

        self.assertEqual(mapped['name'], 'Shopify Customer')
        self.assertEqual(mapped['email'], '')


if __name__ == '__main__':
    unittest.main()

