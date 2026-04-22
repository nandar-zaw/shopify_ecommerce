# Shopify E-Commerce Connector for Odoo 17

![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Odoo](https://img.shields.io/badge/Odoo-17-purple.svg)
![Docker](https://img.shields.io/badge/docker-compose-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## Problem Statement

Small and medium-sized enterprises (SMEs) that operate Shopify storefronts alongside Odoo ERP systems face a critical operational challenge: data lives in two disconnected places. Store managers are forced to manually re-enter orders, update inventory counts, and reconcile customer records across both platforms — a process that is time-consuming, error-prone, and impossible to scale.

Without a reliable sync layer, inventory mismatches cause overselling, delayed order processing leads to poor customer experiences, and sales teams lack visibility into which customers are most likely to convert. Marketing teams cannot act on abandoned cart data, and customer support has no unified view of a buyer's purchase history.

This project solves that problem by building a **bidirectional synchronization module** that deeply integrates Shopify with Odoo 17. Products flow from Odoo to Shopify automatically. Orders placed on Shopify are imported into Odoo as native sale orders. Inventory levels are kept in sync via scheduled jobs and real-time webhooks. The module also lays the foundation for AI-powered features including product recommendations, lead scoring, and chatbot-assisted support — turning raw store data into actionable business intelligence.

---

## Key Features

- **Product Sync** — Export Odoo products to Shopify with one click; fields include title, price, and publish status
- **Order Import** — Shopify orders are pulled into Odoo as `sale.order` records with full line item detail
- **Inventory Sync** — Hourly cron job pushes `stock.quant` levels to Shopify; incoming webhook updates Odoo quantities
- **Webhook Processing** — Receives and validates Shopify webhook events (`orders/create`, `inventory_levels/update`, etc.) using HMAC verification
- **Abandoned Cart Recovery** — `sale.cart` model tracks incomplete carts; `action_convert_to_order()` converts them to sale orders
- **AI Recommendations (stub)** — `shopify.ai.recommendation` model stores ML-driven product suggestion scores
- **Lead Scoring (stub)** — `shopify.lead.score` computes hot/warm/cold conversion probability bands per customer
- **Chatbot Support (stub)** — `shopify.ai.chat.session` tracks support transcripts and escalation events
- **DTOs** — Clean data transfer objects decouple the Shopify API payload structure from Odoo ORM models
- **Security** — Built on Odoo 17's native role-based access control; all model permissions defined in `ir.model.access.csv`

---

## Use Cases

1. **As a store manager**, I want to export an Odoo product to my Shopify store with a single click, so that I don't have to re-enter product details in two systems.

2. **As a warehouse staff member**, I want Odoo's inventory levels to automatically reflect what is shown on the Shopify storefront, so that I can avoid overselling and fulfill orders accurately.

3. **As a sales representative**, I want to see a lead score for each customer based on their Shopify purchase history, so that I can prioritize follow-up on the highest-value prospects.

4. **As a customer service agent**, I want to view a customer's full Shopify order history inside Odoo when handling a support request, so that I can resolve issues without switching between platforms.

5. **As a store administrator**, I want to configure my Shopify API credentials and webhook secret inside Odoo, so that I can control which store events trigger data synchronization.

6. **As a marketing manager**, I want to see which customers abandoned their carts and receive AI-powered product recommendations for them, so that I can run targeted recovery campaigns.

7. **As a developer**, I want all Shopify API payloads mapped through typed DTOs before they touch the Odoo ORM, so that the codebase is maintainable and testable without spinning up a full Odoo instance.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SHOPIFY STORE                            │
│              (Products, Orders, Inventory, Customers)           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          REST API (HTTPS)  │  Webhooks (HTTPS POST)
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│              ODOO 17 MODULE — shopify_ecommerce                  │
│                                                                 │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────┐  │
│  │   API Layer     │   │   Sync Engine    │   │  Webhook    │  │
│  │ shopify_config  │──▶│  shopify_sync    │◀──│  Handler    │  │
│  │ _get_headers()  │   │  execute()       │   │  hmac valid │  │
│  └─────────────────┘   └────────┬─────────┘   └─────────────┘  │
│                                 │                               │
│  ┌──────────────────────────────▼──────────────────────────┐   │
│  │                   DTO Layer (dto.py)                     │   │
│  │  ShopifyProductDTO  ShopifyOrderDTO  ShopifyCustomerDTO  │   │
│  └──────────────────────────────┬──────────────────────────┘   │
│                                 │                               │
│  ┌──────────────────────────────▼──────────────────────────┐   │
│  │                  Odoo ORM Models                         │   │
│  │  product.template  sale.order  stock.quant  res.partner  │   │
│  │  sale.cart  shopify.ai.recommendation  shopify.lead.score│   │
│  └──────────────────────────────┬──────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────┐
│                     PostgreSQL 15 Database                       │
│              (odoo17 — port 5433 via Docker Compose)             │
└─────────────────────────────────────────────────────────────────┘
```

**Sync Flows:**

| Direction | Trigger | Mechanism |
|---|---|---|
| Odoo → Shopify | User clicks "Export to Shopify" | `action_export_to_shopify()` → REST POST |
| Shopify → Odoo (Orders) | Webhook `orders/create` | `ShopifyWebhookEvent` → `sale.order` |
| Odoo → Shopify (Inventory) | Hourly cron | `_cron_sync_inventory()` → REST PUT |
| Shopify → Odoo (Inventory) | Webhook `inventory_levels/update` | `ShopifyWebhookEvent` → `stock.quant` |

---

## Setup & Run

### Prerequisites

- Docker Desktop installed and running
- Git

### Start the Application

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Start Odoo 17 + PostgreSQL 15
docker-compose up -d

# View logs
docker logs -f odoo17
```

### Access the Application

| Service | URL | Credentials |
|---|---|---|
| Odoo Web UI | http://localhost:8069 | admin / admin |
| PostgreSQL | localhost:5433 | odoo / odoo |

### Install the Module

1. Open http://localhost:8069
2. Go to **Apps** → search "Shopify E-Commerce Connector"
3. Click **Install**

### Configure Shopify Connection

1. Go to **Shopify → Configuration → Stores**
2. Create a new `shopify.config` record
3. Enter your store URL, API key, access token, and webhook secret
4. Click **Test Connection**

### Enable Sync Cron Jobs

1. Go to **Settings → Technical → Automation → Scheduled Actions**
2. Enable: `Shopify: Import Orders`, `Shopify: Sync Inventory`

---

## Running Tests

### Unit Tests (no Odoo or DB required)

```bash
python -m unittest discover -s addons/shopify_ecommerce/tests -p "test_dto.py" -v
```

### Integration Tests (requires running Odoo)

```bash
docker exec -it odoo17 odoo shell -d odoo17
# Then from the Odoo shell:
# env['shopify.config'].search([])
```

Or run via Odoo's test runner:

```bash
docker exec -it odoo17 python -m pytest addons/shopify_ecommerce/tests/test_shopify_config_integration.py
```

---

## Security

This module uses **Odoo 17's built-in authentication and role-based access control**:

- All model permissions are defined in `security/ir.model.access.csv`
- Shopify API credentials (access token, webhook secret) are stored as encrypted fields on `shopify.config`
- Webhook payloads are validated using HMAC-SHA256 before processing (`hmac_valid` field)
- Odoo session-based authentication controls access to all views and actions
- Users must have the `Shopify Manager` or `Shopify User` group to access sync features

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| ERP Framework | Odoo 17 (Community) |
| Database | PostgreSQL 15 |
| Containerization | Docker Compose |
| External API | Shopify REST API v2024-01 |
| CI/CD | GitHub Actions |
| Testing | Python `unittest`, Odoo `TransactionCase` |

---

## Project Structure

```
addons/shopify_ecommerce/
├── __manifest__.py              # Module metadata + dependencies
├── models/
│   ├── shopify_config.py        # Store connection + API client
│   ├── shopify_sync.py          # Sync engine + webhook handler
│   ├── dto.py                   # Data Transfer Objects (DTOs)
│   ├── ai_models.py             # Recommendations, lead scoring, chatbot
│   ├── product_template.py      # Product sync extensions
│   ├── sale_order.py            # Order import extensions
│   ├── sale_cart.py             # Abandoned cart model
│   └── stock_quant.py           # Inventory sync + low-stock alerts
├── views/
│   ├── shopify_config_views.xml
│   └── sale_cart_views.xml
├── data/
│   └── cron_jobs.xml            # Scheduled jobs (disabled by default)
├── security/
│   └── ir.model.access.csv      # Access control rules
├── tests/
│   ├── test_dto.py              # Unit tests (no DB required)
│   └── test_shopify_config_integration.py  # Integration tests
└── controllers/                 # Future webhook HTTP endpoints
docs/
├── class_diagram.md             # Mermaid domain model class diagram
└── er_diagram.md                # Mermaid ER diagram
.github/
└── workflows/
    └── ci.yml                   # GitHub Actions CI pipeline
```

---

## CI/CD

This project uses **GitHub Actions** for continuous integration. On every push or pull request to `main`:

1. Checks out the code
2. Sets up Python 3.10
3. Runs all unit tests in `tests/test_dto.py` (no DB or Odoo needed)
4. Reports pass/fail

See `.github/workflows/ci.yml` for the full pipeline definition.

---

## Diagrams

- **Domain Model Class Diagram** → [`docs/class_diagram.md`](docs/class_diagram.md)
- **Database ER Diagram** → [`docs/er_diagram.md`](docs/er_diagram.md)

Both diagrams use [Mermaid](https://mermaid.live) syntax and render natively in GitHub.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
