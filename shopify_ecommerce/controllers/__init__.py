import base64
import hashlib
import hmac
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def validate_hmac(secret, body, hmac_header):
    if not secret or not hmac_header:
        return False
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(computed_hmac, hmac_header)


class WebhookController(http.Controller):
    @http.route('/shopify/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def shopify_webhook(self, **kwargs):
        body = request.httprequest.get_data() or b''
        hmac_header = request.httprequest.headers.get('X-Shopify-Hmac-Sha256')
        topic = request.httprequest.headers.get('X-Shopify-Topic')

        config = request.env['shopify.config'].sudo().search([('active', '=', True)], limit=1)
        secret = config.webhook_secret if config else ''
        is_valid = validate_hmac(secret, body, hmac_header)

        request.env['shopify.webhook.event'].sudo().create({
            'topic': topic,
            'payload': body.decode('utf-8', errors='replace'),
            'processing_status': 'pending',
            'hmac_valid': is_valid,
        })

        if not is_valid:
            _logger.warning('Rejected Shopify webhook due to invalid HMAC for topic %s', topic)
            return Response('Unauthorized', status=401)

        return Response('OK', status=200)

