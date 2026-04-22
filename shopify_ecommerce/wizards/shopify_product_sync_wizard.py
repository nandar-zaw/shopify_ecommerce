import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.shopify_client import ShopifyClientError

_logger = logging.getLogger(__name__)


class ShopifyProductSyncWizard(models.TransientModel):
    _name = 'shopify.product.sync.wizard'
    _description = 'Shopify Product Sync Wizard'

    operation = fields.Selection(
        [('export', 'Export Selected Products'), ('import', 'Import Products from Shopify')],
        string='Operation',
        required=True,
        default='export',
    )
    total_records = fields.Integer(string='Total Records', readonly=True, default=0)
    processed_records = fields.Integer(string='Processed Records', readonly=True, default=0)
    failed_records = fields.Integer(string='Failed Records', readonly=True, default=0)
    progress_pct = fields.Float(string='Progress (%)', readonly=True, digits=(16, 2), default=0.0)
    result_message = fields.Text(string='Result', readonly=True)

    def _set_progress(self, processed, total, failed=0, message=False):
        total = total or 0
        progress_pct = (processed / total * 100.0) if total else 100.0
        self.write(
            {
                'total_records': total,
                'processed_records': processed,
                'failed_records': failed,
                'progress_pct': progress_pct,
                'result_message': message or self.result_message,
            }
        )

    def action_run(self):
        self.ensure_one()
        config = self.env['shopify.config']._get_active_config()
        sync_log = self.env['shopify.sync.log'].create(
            {
                'config_id': config.id,
                'sync_type': 'product',
                'direction': 'outbound' if self.operation == 'export' else 'inbound',
                'status': 'pending',
                'start_time': fields.Datetime.now(),
            }
        )

        try:
            if self.operation == 'import':
                try:
                    imported = self.env['product.template'].import_from_shopify()
                except ShopifyClientError as exc:
                    _logger.exception('Import from Shopify failed')
                    raise UserError(_('Import from Shopify failed: %s') % exc) from exc

                message = _('Imported/updated %s products from Shopify.') % imported
                self._set_progress(imported, imported, 0, message)
            else:
                products = self.env['product.template'].browse(self.env.context.get('active_ids', []))
                if not products:
                    raise UserError(_('Please select at least one product to export.'))

                total = len(products)
                processed = 0
                failed = 0
                errors = []
                for product in products:
                    try:
                        product.action_export_to_shopify()
                        processed += 1
                    except (UserError, ShopifyClientError):
                        failed += 1
                        _logger.exception('Bulk export failed for product %s', product.display_name)
                        errors.append(product.display_name)
                    self._set_progress(processed + failed, total, failed)

                message = _('Export complete. Success: %s, Failed: %s.') % (processed, failed)
                if errors:
                    message = message + _('\nFailed products: %s') % ', '.join(errors[:10])
                self._set_progress(processed + failed, total, failed, message)

            sync_log.write({'status': 'success', 'end_time': fields.Datetime.now(), 'error_message': False})
        except Exception as exc:  # pylint: disable=broad-except
            sync_log.write(
                {
                    'status': 'failed',
                    'end_time': fields.Datetime.now(),
                    'error_message': str(exc),
                }
            )
            raise

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shopify Product Sync'),
                'message': self.result_message or _('Product sync finished.'),
                'type': 'success',
                'sticky': False,
            },
        }
