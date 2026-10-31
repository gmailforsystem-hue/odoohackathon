# LIVE LINK: https://temporary-flying-hawthorn-31nn4a5-mc8q71uen-anon-delta-lake.vercel.app/

# Brightloop Subscription Platform

> **A high-performance subscription lifecycle and recurring billing platform built with Python, SQLite, and Vanilla JavaScript.**

Brightloop is an enterprise-oriented subscription management platform designed to manage the complete recurring revenue lifecycle—from products and quotations to subscriptions, automated billing, invoicing, payments, taxes, discounts, and audit tracking.

The platform focuses on delivering a lightweight architecture with **zero external Python dependencies**, persistent relational data, modular frontend components, and automated billing logic.

---

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Core Workflows](#core-workflows)
- [API Overview](#api-overview)
- [Role-Based Access Control](#role-based-access-control)
- [Performance](#performance)
- [Testing](#testing)
- [Getting Started](#getting-started)
- [Hackathon Demo](#hackathon-demo)
- [Future Improvements](#future-improvements)

---

## Overview

Subscription businesses require reliable systems to manage recurring revenue, customer contracts, billing schedules, invoices, payments, and financial adjustments.

Brightloop provides a unified platform for managing these workflows through a modular architecture.

The application supports:

- Product and variant management
- Subscription plans and recurring contracts
- Sales quotations
- Quotation-to-subscription conversion
- Automated recurring billing
- Invoice generation
- Partial and full payment processing
- Discounts and tax calculations
- Customer self-service
- Role-based access control
- Audit logging

---

## Problem Statement

Managing recurring billing involves multiple interconnected business processes.

Many workflows require separate systems for:

- Customer management
- Product configuration
- Subscription lifecycle management
- Recurring invoice generation
- Payment reconciliation
- Tax and discount calculations
- User permissions and auditability

This fragmentation increases operational complexity and makes it difficult to maintain a clear view of the complete subscription lifecycle.

---

## Solution

Brightloop centralizes the recurring billing workflow into a single platform.

```text id="brightloop-flow"
Product & Pricing
        ↓
Quotation
        ↓
Subscription
        ↓
Recurring Billing
        ↓
Invoice Generation
        ↓
Payment Collection
        ↓
Revenue Tracking & Audit
```

The platform is designed around persistent relational data and connected business workflows rather than isolated interface demonstrations.

---

# Key Features

## Subscription Lifecycle Management

Manage subscriptions throughout their lifecycle.

Supported states include:

- Draft
- Quotation
- Confirmed
- Active
- Paused
- Closed

Additional capabilities:

- Auto-renewal
- Configurable payment terms
- Billing date tracking
- Subscription line items
- Optional add-ons
- Add-on enable/disable functionality

---

## Automated Billing Engine

The billing engine processes eligible active subscriptions and generates invoices according to their billing schedules.

Supported billing frequencies:

- Monthly
- Quarterly
- Annually

### Idempotent Billing

Before generating an invoice, the system verifies whether billing for the relevant interval has already been completed.

This prevents duplicate invoice generation when the billing process is executed multiple times.

```text id="billing-flow"
Find Eligible Subscriptions
          ↓
Validate Billing Date
          ↓
Check Existing Billing Record
          ↓
Calculate Products & Add-ons
          ↓
Apply Discounts
          ↓
Calculate Taxes
          ↓
Generate Invoice
          ↓
Update Billing Schedule
```

---

## Financial Calculations

Brightloop includes support for core recurring billing calculations.

### Proration

When a subscription component is added during an active billing period:

```text id="proration"
Prorated Amount =
Total Amount ×
(Remaining Active Days / Total Days in Billing Period)
```

### Discounts

Supported discount types:

- Percentage-based discounts
- Fixed-value discounts
- Minimum spend validation
- Validity date checks

### Taxes

Supported tax configurations include:

- Regional tax rules
- GST
- VAT
- Sales tax
- Inclusive taxes
- Exclusive taxes

---

## Products and Variants

The product catalog supports:

- Product creation
- Unique product codes
- Sales pricing
- Cost pricing
- Product activation/deactivation
- Product variants
- Variant-based price surcharges

---

## Quotations

Brightloop supports the sales-to-subscription workflow.

```text id="quotation-flow"
Create Quotation
        ↓
Send Proposal
        ↓
Customer Acceptance
        ↓
Convert to Subscription
        ↓
Activate Billing Lifecycle
```

Quotation templates can be used to streamline recurring sales configurations.

---

## Invoices and Payments

The platform includes a persistent invoice and payment ledger.

Supported invoice statuses:

- Draft
- Confirmed
- Partially Paid
- Paid
- Overdue

Payment processing supports:

- Partial payments
- Full payments
- Balance reconciliation
- Payment history tracking

---

## Role-Based Access Control

Brightloop supports three primary user roles.

| Feature | Admin | Staff | Customer |
|---|:---:|:---:|:---:|
| Financial Dashboard | ✓ | ✓ | — |
| Run Automated Billing | ✓ | — | — |
| Manage Subscriptions | ✓ | ✓ | — |
| Convert Quotations | ✓ | ✓ | — |
| Manage Products & Plans | ✓ | — | — |
| Record Payments | ✓ | ✓ | — |
| Manage Taxes & Discounts | ✓ | — | — |
| Manage Team Members | ✓ | — | — |
| Customer Portal | ✓ | ✓ | ✓ |
| Toggle Subscription Add-ons | ✓ | ✓ | ✓ |
| View Audit Logs | ✓ | — | — |

---

## Customer Self-Service

Customers can access their subscription-related information through a dedicated portal.

Capabilities include:

- Viewing subscriptions
- Managing available add-ons
- Viewing invoices
- Accessing account information

---

# Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+ |
| Backend Dependencies | Python Standard Library |
| Database | SQLite3 |
| API | REST over HTTP |
| Frontend | Vanilla JavaScript (ES6+) |
| Styling | CSS3 |
| Deployment | Cloudflare Quick Tunnels |

### Zero-Dependency Backend

The backend is built using Python's standard library.

Core modules include:

```text id="python-modules"
http.server
sqlite3
json
urllib.parse
hashlib
datetime
```

This architecture reduces external dependency management and keeps the project lightweight and straightforward to deploy.

---

# System Architecture

```text id="architecture"
┌─────────────────────────────────────┐
│          Frontend Application       │
│    Vanilla JavaScript + CSS3        │
└──────────────────┬──────────────────┘
                   │
                   │ HTTP / REST API
                   ▼
┌─────────────────────────────────────┐
│          Python API Server          │
│       Standard Library Backend      │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│         Billing Engine              │
│  Billing • Tax • Discount • Payment │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│            SQLite3 Database         │
│    Persistent Relational Storage    │
└─────────────────────────────────────┘
```

---

# Project Structure

```text id="project-structure"
brightloop_subscriptions/
│
├── README.md
│
├── backend/
│   ├── brightloop.db
│   ├── database.py
│   ├── billing_engine.py
│   └── server.py
│
├── frontend/
│   ├── index.html
│   │
│   ├── css/
│   │   └── styles.css
│   │
│   └── js/
│       ├── app.js
│       └── pages/
│           ├── dashboard.js
│           ├── subscriptions.js
│           ├── quotations.js
│           ├── products.js
│           ├── plans.js
│           ├── invoices.js
│           ├── payments.js
│           ├── discounts.js
│           ├── taxes.js
│           ├── customers.js
│           ├── portal.js
│           ├── team.js
│           └── audit.js
│
└── tests/
    ├── test_backend.py
    ├── test_server_in_memory.py
    ├── test_benchmark_scale.py
    └── test_api_endpoints.py
```

---

# API Overview

All API responses follow a consistent JSON structure.

### Success

```json id="api-success"
{
  "status": "success",
  "data": {}
}
```

### Error

```json id="api-error"
{
  "status": "error",
  "message": "Description of the error"
}
```

## Available API Modules

### Reports

```text id="reports-api"
GET /api/reports/summary
GET /api/reports/aging
```

### Subscriptions

```text id="subscriptions-api"
GET  /api/subscriptions
POST /api/subscriptions
GET  /api/subscriptions/{id}
POST /api/subscriptions/{id}/transition
POST /api/subscriptions/{id}/toggle-addon
```

### Quotations

```text id="quotations-api"
GET  /api/quotations
POST /api/quotations
POST /api/quotations/{id}/convert
```

### Products and Plans

```text id="products-api"
GET  /api/products
POST /api/products
POST /api/products/{id}/variants

GET  /api/plans
POST /api/plans
```

### Billing and Invoices

```text id="billing-api"
GET  /api/invoices
GET  /api/invoices/{id}

POST /api/billing/run-day
```

### Payments

```text id="payments-api"
GET  /api/payments
POST /api/payments
```

### Discounts and Taxes

```text id="financial-api"
GET  /api/discounts
POST /api/discounts

GET  /api/taxes
POST /api/taxes
```

### Users and Audit Logs

```text id="users-api"
GET  /api/auth/users
POST /api/team/invite

GET /api/audit/logs
```

---

# Performance and Reliability

Brightloop includes several mechanisms intended to improve responsiveness and stability.

## Request Deduplication

Duplicate in-flight GET requests can be reused to reduce unnecessary backend and database activity.

## Search Debouncing

Search interactions use a debounce window to avoid excessive requests while users are typing.

## Database Indexing

Indexes are used for frequently queried fields, including:

- Customer IDs
- Subscription status
- Invoice due dates
- Next billing dates

## Latency Monitoring

The application includes latency telemetry and smoothing to provide more stable performance indicators.

---

# Testing

The project includes automated tests covering key areas of the platform.

## Financial Engine Tests

Coverage includes:

- Proration calculations
- Tax calculations
- Discount validation
- Duplicate billing prevention

## API Integration Tests

Tests validate critical REST endpoints and HTTP behavior.

## Scalability Benchmarks

The benchmark suite evaluates subscription operations against a larger dataset and measures execution performance against the project's defined SLA target.

---

# Getting Started

## Prerequisites

- Python 3.10 or later

No external Python packages are required.

## Run the Application

Clone the repository:

```bash id="clone"
git clone <repository-url>
cd brightloop_subscriptions
```

Start the backend server:

```bash id="start-server"
cd backend
python3 server.py
```

Then open the application using the local URL served by the application.

---

# Hackathon Demo Guide

A recommended demonstration sequence:

### 1. Dashboard

Demonstrate:

- Recurring revenue metrics
- Active subscriptions
- Accounts receivable
- Performance indicators

### 2. Quotation Conversion

Show how a quotation can be converted into a subscription.

```text id="demo-quotation"
Quotation → Subscription → Active Billing
```

### 3. Automated Billing

Run the billing process and demonstrate:

- Invoice generation
- Discounts
- Taxes
- Billing schedule updates

Execute the billing process again to demonstrate idempotency and duplicate prevention.

### 4. Payment Processing

Record a partial payment and demonstrate:

```text id="demo-payment"
Invoice → Partial Payment → Balance Recalculation
```

### 5. Role-Based Experience

Switch between Admin, Staff, and Customer views to demonstrate role-specific access and workflows.

---

# Future Improvements

Potential areas for future development include:

- Secure production authentication
- Payment gateway integration
- Email notifications
- Webhook support
- PDF invoice generation
- Multi-currency support
- Multi-tenant organizations
- Advanced analytics
- Production cloud deployment
- Additional tax automation

---

# Built For

**Hackathon Project — Brightloop Subscription Platform**

Brightloop demonstrates how a complete subscription and recurring billing workflow can be implemented using a lightweight architecture, persistent relational data, REST APIs, automated billing logic, financial calculations, role-based access control, and automated testing.


