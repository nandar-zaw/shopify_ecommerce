import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ShopifySync(models.Model):
    _name = 'shopify.sync'
    _description = 'Shopify Sync Service'
    _auto = False

    sync_type = fields.Selection(
        [('product', 'Product'), ('order', 'Order'), ('inventory', 'Inventory'), ('customer', 'Customer')],
        string='Sync Type',
    )

    def sync_products_to_shopify(self):
        products = self.env['product.template'].search([('active', '=', True), ('sale_ok', '=', True)])
        _logger.info('Syncing %s active products to Shopify', len(products))
        for product in products:
            product.action_export_to_shopify()

    def sync_orders_from_shopify(self, config=None):
        config = config or self.env['shopify.config']._get_active_config()
        client = config._get_client()
        imported = 0
        failed = 0
        errors = []
        sync_log = self.env['shopify.sync.log'].create(
            {
                'config_id': config.id,
                'sync_type': 'order',
                'direction': 'inbound',
                'status': 'pending',
                'start_time': fields.Datetime.now(),
            }
        )
        _logger.info('Pulling orders from Shopify for config %s', config.id)
        try:
            for order_data in client.iter_orders(page_size=100):
                try:
                    self.env['sale.order']._shopflow_import_from_shopify_order(order_data)
                    imported += 1
                except Exception as exc:  # pylint: disable=broad-except
                    failed += 1
                    errors.append(f"Order {order_data.get('id')}: {exc}")
                    _logger.exception('Failed to import Shopify order payload: %s', order_data.get('id'))

            sync_log.write(
                {
                    'status': 'failed' if failed else 'success',
                    'end_time': fields.Datetime.now(),
                    'error_message': '\n'.join(errors[:20]) if errors else False,
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            sync_log.write(
                {
                    'status': 'failed',
                    'end_time': fields.Datetime.now(),
                    'error_message': str(exc),
                }
            )
            raise

        _logger.info('Imported or checked %s Shopify orders (%s failed)', imported, failed)
        return {
            'imported': imported,
            'failed': failed,
            'sync_log_id': sync_log.id,
        }

    # customer_data acts as a DTO — raw Shopify payload mapped to Odoo fields
    def sync_customers_from_shopify(self, config=None):
        config = config or self.env['shopify.config']._get_active_config()
        client = config._get_client()
        imported = 0
        failed = 0
        errors = []
        sync_log = self.env['shopify.sync.log'].create(
            {
                'config_id': config.id,
                'sync_type': 'customer',
                'direction': 'inbound',
                'status': 'pending',
                'start_time': fields.Datetime.now(),
            }
        )
        _logger.info('Pulling customers from Shopify for config %s', config.id)
        query = """
        query Customers($first: Int!, $after: String) {
          customers(first: $first, after: $after) {
            edges {
              node {
                id
                firstName
                lastName
                email
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        try:
            after = None
            while True:
                payload = client.graphql(query, {'first': 100, 'after': after})
                edges = (payload.get('customers') or {}).get('edges') or []
                for edge in edges:
                    customer = edge.get('node') or {}
                    customer_data = {
                        'id': client._extract_gid_numeric_id(customer.get('id')),
                        'first_name': customer.get('firstName') or '',
                        'last_name': customer.get('lastName') or '',
                        'email': customer.get('email') or '',
                    }
                    try:
                        self.env['res.partner'].sync_from_shopify(customer_data)
                        imported += 1
                    except Exception as exc:  # pylint: disable=broad-except
                        failed += 1
                        errors.append(f"Customer {customer_data.get('id')}: {exc}")
                        _logger.exception('Failed to import Shopify customer payload: %s', customer_data.get('id'))

                page_info = (payload.get('customers') or {}).get('pageInfo') or {}
                if not page_info.get('hasNextPage'):
                    break
                after = page_info.get('endCursor')

            sync_log.write(
                {
                    'status': 'failed' if failed else 'success',
                    'end_time': fields.Datetime.now(),
                    'error_message': '\n'.join(errors[:20]) if errors else False,
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            sync_log.write(
                {
                    'status': 'failed',
                    'end_time': fields.Datetime.now(),
                    'error_message': str(exc),
                }
            )
            raise

        _logger.info('Imported or checked %s Shopify customers (%s failed)', imported, failed)
        return {
            'imported': imported,
            'failed': failed,
            'sync_log_id': sync_log.id,
        }

    def sync_inventory_to_shopify(self):
        _logger.info('Pushing inventory levels to Shopify')

    def retry_failed_syncs(self):
        failed_logs = self.env['shopify.sync.log'].search([('status', '=', 'failed')])
        _logger.info('Found %s failed sync logs to retry', len(failed_logs))
        for log in failed_logs:
            _logger.info('Failed sync log %s (%s): %s', log.id, log.sync_type, log.error_message)
