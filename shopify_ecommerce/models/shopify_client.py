import logging
import time

import requests

_logger = logging.getLogger(__name__)


class ShopifyClientError(Exception):
    """Raised when a Shopify API request fails."""


class ShopifyClient:
    BASE = 'https://{shop}.myshopify.com/admin/api/{api_version}'

    def __init__(self, store, token, api_version='2024-01', timeout=30, max_retries=3):
        self.store = self._normalize_store(store)
        self.token = token.strip()
        self.api_version = api_version
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            'X-Shopify-Access-Token': self.token,
            'Content-Type': 'application/json',
        }

    @staticmethod
    def _normalize_store(store):
        value = (store or '').strip().lower()
        if not value:
            raise ShopifyClientError('Store URL is required')

        for prefix in ('https://', 'http://'):
            if value.startswith(prefix):
                value = value[len(prefix) :]

        if value.endswith('.myshopify.com'):
            value = value[: -len('.myshopify.com')]

        value = value.split('/')[0]
        if not value:
            raise ShopifyClientError('Invalid Shopify store URL')

        return value

    def _base_url(self):
        return self.BASE.format(shop=self.store, api_version=self.api_version)

    @staticmethod
    def _extract_gid_numeric_id(gid):
        value = str(gid or '').strip()
        if not value:
            return ''
        if value.isdigit():
            return value
        if '/' in value:
            tail = value.rsplit('/', 1)[-1]
            return tail if tail.isdigit() else value
        return value

    def _request(self, method, endpoint, params=None, json=None):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        url = self._base_url() + endpoint
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise ShopifyClientError(f'Network error while calling Shopify: {exc}') from exc

            if response.status_code == 429 and attempt < self.max_retries:
                retry_after = response.headers.get('Retry-After')
                delay = float(retry_after) if retry_after else min(2 ** (attempt + 1), 10)
                _logger.warning('Shopify rate limit reached, retrying in %s seconds', delay)
                time.sleep(delay)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                detail = response.text.strip()[:500]
                hint = ''
                if response.status_code == 403 and 'read_products' in detail:
                    hint = (
                        ' The Shopify access token is missing the read_products scope. '
                        'Reinstall the app or regenerate the token with product read permission.'
                    )
                raise ShopifyClientError(
                    f'Shopify API error {response.status_code} for {endpoint}: {detail}{hint}'
                ) from exc

            if not response.text:
                return {}
            return response.json()

        raise ShopifyClientError(f'Shopify request failed: {last_error}')

    def graphql(self, query, variables=None):
        payload = self._request('POST', '/graphql.json', json={'query': query, 'variables': variables or {}})
        errors = payload.get('errors') or []
        if errors:
            raise ShopifyClientError(f'Shopify GraphQL errors: {errors}')
        return payload.get('data') or {}

    @staticmethod
    def _ensure_no_user_errors(result, key):
        user_errors = (result.get(key) or {}).get('userErrors') or []
        if user_errors:
            details = '; '.join(err.get('message') or 'Unknown GraphQL user error' for err in user_errors)
            raise ShopifyClientError(f'Shopify GraphQL mutation failed: {details}')

    def get_shop_identity(self):
        data = self.graphql(
            """
            query ShopIdentity {
              shop {
                name
                myshopifyDomain
              }
            }
            """
        )
        return data.get('shop') or {}

    def upsert_product(self, payload):
        product_payload = (payload or {}).get('product') or {}
        tags = [tag.strip() for tag in (product_payload.get('tags') or '').split(',') if tag.strip()]
        status = (product_payload.get('status') or 'DRAFT').upper()
        if status not in ('ACTIVE', 'DRAFT', 'ARCHIVED'):
            status = 'DRAFT'

        input_data = {
            'title': product_payload.get('title') or 'Odoo Product',
            'descriptionHtml': product_payload.get('body_html') or '',
            'vendor': product_payload.get('vendor') or '',
            'tags': tags,
            'status': status,
        }

        product_gid = None
        if product_payload.get('id'):
            product_gid = f"gid://shopify/Product/{self._extract_gid_numeric_id(product_payload.get('id'))}"
            input_data['id'] = product_gid

        if product_gid:
            mutation = """
            mutation UpdateProduct($input: ProductInput!) {
              productUpdate(input: $input) {
                product {
                  id
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            data = self.graphql(mutation, {'input': input_data})
            self._ensure_no_user_errors(data, 'productUpdate')
            product_gid = ((data.get('productUpdate') or {}).get('product') or {}).get('id') or product_gid
        else:
            mutation = """
            mutation CreateProduct($input: ProductInput!) {
              productCreate(input: $input) {
                product {
                  id
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            data = self.graphql(mutation, {'input': input_data})
            self._ensure_no_user_errors(data, 'productCreate')
            product_gid = ((data.get('productCreate') or {}).get('product') or {}).get('id')

        if not product_gid:
            raise ShopifyClientError('Shopify product mutation did not return a product id.')

        product_node = self._fetch_product_by_gid(product_gid)
        return {'product': self._format_product_node(product_node)}

    def _fetch_product_by_gid(self, product_gid):
        query = """
        query ProductById($id: ID!) {
          product(id: $id) {
            id
            title
            descriptionHtml
            tags
            variants(first: 100) {
              edges {
                node {
                  id
                  sku
                  price
                  selectedOptions {
                    name
                    value
                  }
                }
              }
            }
          }
        }
        """
        data = self.graphql(query, {'id': product_gid})
        return data.get('product') or {}

    def iter_products(self, page_size=100):
        after = None
        query = """
        query Products($first: Int!, $after: String) {
          products(first: $first, after: $after) {
            edges {
              cursor
              node {
                id
                title
                descriptionHtml
                tags
                variants(first: 100) {
                  edges {
                    node {
                      id
                      sku
                      price
                      selectedOptions {
                        name
                        value
                      }
                    }
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        while True:
            data = self.graphql(query, {'first': page_size, 'after': after})
            products = (data.get('products') or {}).get('edges') or []
            for edge in products:
                yield self._format_product_node(edge.get('node') or {})

            page_info = (data.get('products') or {}).get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                break
            after = page_info.get('endCursor')

    def iter_orders(self, page_size=100):
        after = None
        query = """
        query Orders($first: Int!, $after: String) {
          orders(first: $first, after: $after, reverse: true) {
            edges {
              node {
                id
                name
                note
                displayFinancialStatus
                customer {
                  id
                  firstName
                  lastName
                  email
                  phone
                }
                shippingLines(first: 10) {
                  edges {
                    node {
                      originalPriceSet {
                        shopMoney {
                          amount
                        }
                      }
                    }
                  }
                }
                lineItems(first: 100) {
                  edges {
                    node {
                      id
                      title
                      quantity
                      sku
                      variant {
                        id
                        sku
                        price
                        product {
                          id
                        }
                      }
                    }
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        while True:
            data = self.graphql(query, {'first': page_size, 'after': after})
            orders = (data.get('orders') or {}).get('edges') or []
            for edge in orders:
                yield self._format_order_node(edge.get('node') or {})

            page_info = (data.get('orders') or {}).get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                break
            after = page_info.get('endCursor')

    def _format_product_node(self, node):
        variants = []
        for edge in ((node.get('variants') or {}).get('edges') or []):
            variant = edge.get('node') or {}
            selected = variant.get('selectedOptions') or []
            mapped = {
                'id': self._extract_gid_numeric_id(variant.get('id')),
                'sku': variant.get('sku') or '',
                'price': variant.get('price') or '0.0',
            }
            for index, option in enumerate(selected[:3], start=1):
                mapped[f'option{index}'] = option.get('value') or ''
            variants.append(mapped)

        tags = node.get('tags') or []
        if isinstance(tags, list):
            tags = ', '.join(tags)

        return {
            'id': self._extract_gid_numeric_id(node.get('id')),
            'title': node.get('title') or '',
            'body_html': node.get('descriptionHtml') or '',
            'tags': tags or '',
            'variants': variants,
        }

    def _format_order_node(self, node):
        customer = node.get('customer') or {}
        line_items = []
        for edge in ((node.get('lineItems') or {}).get('edges') or []):
            line = edge.get('node') or {}
            variant = line.get('variant') or {}
            product = variant.get('product') or {}
            line_items.append(
                {
                    'id': self._extract_gid_numeric_id(line.get('id')),
                    'title': line.get('title') or '',
                    'quantity': line.get('quantity') or 0,
                    'sku': line.get('sku') or variant.get('sku') or '',
                    'price': variant.get('price') or '0.0',
                    'variant_id': self._extract_gid_numeric_id(variant.get('id')),
                    'product_id': self._extract_gid_numeric_id(product.get('id')),
                }
            )

        shipping_lines = []
        for edge in ((node.get('shippingLines') or {}).get('edges') or []):
            shipping_line = edge.get('node') or {}
            price = (
                ((shipping_line.get('originalPriceSet') or {}).get('shopMoney') or {}).get('amount')
                or '0.0'
            )
            shipping_lines.append({'price': price})

        financial_status = (node.get('displayFinancialStatus') or '').lower()
        status_map = {
            'paid': 'paid',
            'authorized': 'authorized',
            'partially_paid': 'partially_paid',
            'pending': 'pending',
        }
        mapped_financial_status = status_map.get(financial_status, financial_status)

        return {
            'id': self._extract_gid_numeric_id(node.get('id')),
            'name': node.get('name') or '',
            'note': node.get('note') or '',
            'financial_status': mapped_financial_status,
            'customer': {
                'id': self._extract_gid_numeric_id(customer.get('id')),
                'first_name': customer.get('firstName') or '',
                'last_name': customer.get('lastName') or '',
                'email': customer.get('email') or '',
                'phone': customer.get('phone') or '',
            },
            'line_items': line_items,
            'shipping_lines': shipping_lines,
        }

    def get(self, endpoint, params=None):
        return self._request('GET', endpoint, params=params)

    def post(self, endpoint, payload):
        return self._request('POST', endpoint, json=payload)

    def put(self, endpoint, payload):
        return self._request('PUT', endpoint, json=payload)

    def iter_paginated(self, endpoint, root_key, page_size=100, extra_params=None):
        if endpoint == '/products.json' and root_key == 'products':
            yield from self.iter_products(page_size=page_size)
            return

        if endpoint == '/orders.json' and root_key == 'orders':
            yield from self.iter_orders(page_size=page_size)
            return

        raise ShopifyClientError(
            f'GraphQL client does not support REST pagination for endpoint {endpoint}. '
            'Use iter_products() or iter_orders() instead.'
        )

