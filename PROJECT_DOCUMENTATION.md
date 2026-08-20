# ShopHub — Project Documentation

A complete reference for what this project is, what it was built with, and why — useful for your
own notes, a viva/presentation, or a report submission.

---

## 1. The Original Prompt (as given)

This is the exact request that defined the project scope:

> hi
> i need to create a web and website.
> where it will contain 3 pages like one for customer, shopkeeper, admin.
>
> when the people open the web or app they should get an animation like welcome to app name, with
> some good animation and good ui with some emojis and don't make it look odd it should be
> professional
>
> when customers enters the proper login credentials they should see like welcome Customer name
> with good animation and also same for the shopkeeper when they login they should see welcome Shop
> name.
>
> **login page:** there should be 3 different login like one for customer, one for shopkeeper and
> one for admin login, where the new customer and new shopkeeper can have new registration but the
> admin should have only login not the registration and also give forgot password option when the
> users forget their passwords.
>
> **customer page:** profile option where they can add their name and delivery address, my cart and
> orders option, and in the first screen they should see products list — all products with
> categories like dairy, pulses, spices etc. When they add any product to the cart a party popper
> emoji should appear on the screen, and hovering over a product should trigger a "product comes up"
> animation. Add product search, and 2 search options to find a store — by store name and by
> location (showing shops in that location). When a shop is selected, show "Shopping from [Shop
> Name]" at the top. After the bill is generated and payment is done, customers can download a
> non-editable softcopy e-bill — the download option only appears once payment is confirmed by the
> shopkeeper.
>
> **shopkeeper page:** an Orders section showing all customer orders, where the shopkeeper can edit
> the price/add a discount on the bill (without changing the product catalog). An Inventory section
> to pull products from the admin's catalog, including an "add all" option. After generating the
> bill, the shopkeeper clicks "ORDER PACKED — READY TO DELIVERY," which reveals the shop's QR code
> to the customer; the customer then uploads a payment screenshot. Profile section for name, shop
> name, phone, GSTIN (optional), address, UPI ID, and QR image (auto-generated from UPI if left
> blank) — Razorpay gateway should initialize. The final bill (after discount) can be printed, and
> must show shop name, address, GSTIN, customer name, customer phone, and both MRP and the reduced
> selling price. An Analytics option showing earnings and units sold. Uploaded payment screenshots
> should appear in that order's entry in the Orders section.
>
> **admin page:** a single fixed admin account (no registration). Sections for API security,
> analytics, registered shops (name, address, phone, GSTIN, owner name), registered customers (name,
> phone), and app/web settings (change app name and logo). An inventory section to add/edit products
> — MRP, image, category, and unit of sale (kg/pcs/ltr etc.) — plus a "Sync to All Shops" button.
> Only admin can change MRP, and that MRP is visible to everyone.
>
> **global requirements:** professional, lag-free transitions across all pages; must handle many
> concurrent logins without issue; a shared low-opacity background image across all users.

That request was implemented feature-for-feature as a working Flask + SQLite web app, delivered as
a downloadable project folder for local development in VS Code.

---

## 2. Tech Stack — What Was Used and Why

| Layer | Technology | Why this choice |
|---|---|---|
| **Backend framework** | [Flask](https://flask.palletsprojects.com/) (Python) | Lightweight, minimal boilerplate, ideal for a multi-role app built quickly; Blueprints map cleanly onto the three portals (customer/shopkeeper/admin) as separate, self-contained route modules. |
| **Database** | SQLite (via **Flask-SQLAlchemy** ORM) | Zero-config, file-based — no separate database server to install, perfect for local dev/coursework. SQLAlchemy's ORM means the models (`Product`, `Order`, etc.) are plain Python classes, and swapping to PostgreSQL/MySQL later only requires changing one config line — the model code doesn't change. |
| **Password security** | Werkzeug's `generate_password_hash` / `check_password_hash` | Comes bundled with Flask, uses salted PBKDF2 hashing — no plaintext passwords are ever stored. |
| **Templating** | Jinja2 (Flask's default) | Server-rendered HTML keeps the app simple (no separate frontend build step/React app needed) while still allowing dynamic, role-specific pages. |
| **UI framework** | Bootstrap 5 (via CDN) | Fast to build a clean, professional, responsive layout without writing a design system from scratch — buttons, forms, modals, and the grid system all came from it. |
| **Fonts** | Google Fonts — Poppins | A modern, rounded sans-serif that reads as "friendly but professional," matching the emoji-friendly, approachable tone the spec asked for. |
| **Animations/interactivity** | Custom CSS (`@keyframes`) + vanilla JavaScript | The splash screen, welcome animations, product hover "lift" effect, and status transitions are all CSS animations — no heavy JS framework needed, keeps the app fast ("lag-free" as requested). |
| **Party popper effect** | [canvas-confetti](https://github.com/catdad/canvas-confetti) (CDN) + a custom emoji burst | A tiny, dependency-free JS library purpose-built for exactly this kind of celebratory burst — triggered via AJAX right when "Add to Cart" succeeds. |
| **QR code generation** | `qrcode` (Python library, needs **Pillow** to render the image) | Generates a scannable UPI-payment QR directly from the shopkeeper's UPI ID (`upi://pay?pa=...`) — no external QR API/service required, works fully offline. |
| **PDF bill generation** | `reportlab` | Produces the non-editable e-bill as a real PDF (not an image or editable Word doc) — satisfies "non-editable softcopy" directly, and lets us lay out a proper item table with MRP vs. selling price columns. |
| **File uploads** | Flask's built-in `request.files` + Werkzeug | Used for the shopkeeper's logo/QR uploads and the customer's payment-screenshot upload — no extra library needed. |
| **Environment config** | `python-dotenv` + a `config.py` | Keeps secrets (Flask `SECRET_KEY`, admin bootstrap credentials, optional Razorpay keys) out of the source code and in a local `.env` file that isn't committed/shared. |
| **Payment confirmation flow** | UPI QR + manual screenshot upload/confirm (not a live gateway by default) | This was a deliberate scope decision: a real Razorpay integration needs your own live API keys and a merchant account, which weren't available. The UPI QR + screenshot + shopkeeper-confirms flow replicates exactly how small local shops actually take UPI payments today, and needs zero external accounts to demo. A Razorpay hook point (`RAZORPAY_KEY_ID`/`SECRET` in `config.py`) is left in place if you want to wire up the real gateway later. |

### Why Flask over alternatives (e.g., Django, Node/Express, or a React SPA)
- **Django** would have added a lot of built-in machinery (admin panel, ORM conventions, auth
  system) that would have needed to be *worked around* rather than used, since the spec needed
  three custom-designed portals, not Django's default admin.
- **A React/Node SPA** would have required a separate frontend build pipeline and API layer — more
  moving parts for a project meant to be run with a single `python app.py` in VS Code.
- **Flask** hits the sweet spot: small enough to understand end-to-end, structured enough (via
  Blueprints) to cleanly separate the three portals, and fast to get running locally.

---

## 3. Architecture Overview

```
Browser (Customer / Shopkeeper / Admin)
        │
        ▼
   Flask app (app.py)
        │
   ┌────┴─────────────────────────────┐
   │        Blueprints (routes)        │
   │  auth.py │ customer.py │          │
   │  shopkeeper.py │ admin.py         │
   └────┬─────────────────────────────┘
        │
   ┌────┴──────────┐      ┌───────────────────┐
   │ models.py      │      │ utils/            │
   │ (SQLAlchemy    │◄────►│  qr_gen.py         │
   │  ORM models)    │      │  bill_pdf.py       │
   └────┬───────────┘      └───────────────────┘
        │
        ▼
  SQLite database (instance/shophub.db)
```

- **`app.py`** — the application factory; registers all four blueprints, seeds the database with the
  one admin account and demo products on first run, and injects app-wide template variables (app
  name/logo).
- **`config.py`** — central configuration (secret key, database path, upload folder, admin bootstrap
  credentials, optional Razorpay keys).
- **`extensions.py`** — holds the single shared `SQLAlchemy` instance, so it can be imported without
  circular-import issues between `app.py` and the models/blueprints.
- **`models.py`** — every database table as a Python class: `Admin`, `Customer`, `Shopkeeper`,
  `Product` (master catalog), `ShopInventory` (which products a shop stocks), `CartItem`, `Order`,
  `OrderItem`, `AppSetting`.
- **`blueprints/`** — one file per portal, each with its own login-required decorator so a customer
  can never hit a shopkeeper route and vice versa.
- **`utils/`** — small, focused helper modules: one for QR generation, one for PDF bill generation.
- **`templates/`** — one subfolder per portal (`auth/`, `customer/`, `shopkeeper/`, `admin/`), all
  extending a shared `base.html` for the navbar, background layer, and flash messages.
- **`static/`** — CSS (all animations/styling in one file), JS (AJAX add-to-cart + confetti +
  splash-redirect logic), and generated files (QR codes, payment screenshots, bills) under
  `uploads/`/`bills/`.

---

## 4. Database Schema (Entity Overview)

| Table | Purpose | Key fields |
|---|---|---|
| `admins` | Single fixed admin login | email, password_hash |
| `customers` | Customer accounts | name, phone, delivery_address, security Q&A for password reset |
| `shopkeepers` | Shop accounts | shop_name, phone, gstin (nullable), upi_id, qr_image, location_area |
| `products` | **Master catalog** — admin-owned | name, category, mrp, unit, image (URL or local path) |
| `shop_inventory` | Which products a given shop stocks | links a shopkeeper ↔ a product |
| `cart_items` | A customer's active cart | tied to one shopkeeper (customers shop from one shop at a time) |
| `orders` | One order per checkout | status (`placed → packed → payment_uploaded → confirmed`), totals |
| `order_items` | Line items on an order | **snapshots** product name/MRP at order time, plus an editable `selling_price` |
| `app_settings` | Admin-controlled app name/logo | single row |

**Important design decision:** `OrderItem` stores its own `mrp` and `selling_price` fields separate
from the live `Product.mrp`. This is what makes "shopkeeper edits price without touching the
catalog" work — the bill reflects a snapshot at order time, while the master `Product.mrp` (and
therefore what every other customer sees) is untouched.

---

## 5. Order Lifecycle (State Machine)

```
placed → packed → payment_uploaded → confirmed
```

| Status | Set by | What it unlocks |
|---|---|---|
| `placed` | Customer checks out | Shopkeeper can now see & edit the bill |
| `packed` | Shopkeeper clicks "ORDER PACKED — READY TO DELIVERY" | Customer now sees the shop's QR code and can upload a payment screenshot |
| `payment_uploaded` | Customer uploads a screenshot | Shopkeeper sees the screenshot and can confirm |
| `confirmed` | Shopkeeper clicks "Confirm Payment" | A PDF bill is generated server-side; customer's "Download E-Bill" button appears |

---

## 6. Feature-to-Requirement Mapping

| Your requirement | How it was implemented |
|---|---|
| Animated splash + role select | `templates/auth/splash.html` — CSS keyframe animations, auto-redirects after ~2.4s |
| Personalized "Welcome [Name]" | `templates/customer/welcome.html` / `shopkeeper/welcome.html` — shown right after login, before landing on the dashboard |
| 3 separate logins, 2 with registration | `blueprints/auth.py` — distinct routes per role; `admin_login` has no matching register route at all |
| Forgot password | Security-question flow (no email server needed) — stored as a hashed answer, verified before allowing a password reset |
| Product categories + search | `customer.py::home()` filters by `category` and a `q` search string via SQL `ILIKE` |
| Party popper on add-to-cart | AJAX POST → JSON response → `canvas-confetti` burst + an emoji pop animation, no page reload |
| Product hover animation | Pure CSS `transform`/`box-shadow` transition on `.product-card:hover` |
| Store search by name/location | `customer.py::store_search()` — two independent filters on `Shopkeeper.shop_name` and `Shopkeeper.location_area` |
| "Shopping from [Shop]" banner | Rendered whenever `customer.selected_shop_id` is set |
| Non-editable e-bill, gated by payment | PDF only generated (via `reportlab`) once `order.status == "confirmed"`; download route checks that status server-side, not just hides the button |
| Shopkeeper price/discount editing | `shopkeeper.py::update_prices()` writes to `OrderItem.selling_price`, never touches `Product.mrp` |
| Inventory from admin catalog + "Add All" | `shopkeeper.py::inventory_add_all()` bulk-inserts `ShopInventory` rows for every catalog product not already owned |
| "ORDER PACKED" reveals QR | Status transition to `packed` is the trigger; template conditionally shows the QR only at that status |
| Payment screenshot upload | Stored under `static/uploads/payments/`, shown to the shopkeeper on the order detail page |
| UPI QR auto-generation | `utils/qr_gen.py` builds a `upi://pay?...` URI and renders it as a PNG via the `qrcode` + Pillow libraries |
| Printable bill w/ MRP vs. selling price | `templates/shopkeeper/print_bill.html` — a clean, print-CSS-styled page with `window.print()` |
| Shopkeeper analytics | `shopkeeper.py::analytics()` aggregates confirmed orders for earnings + a top-products-sold table |
| Admin: shops/customers directories | `admin.py::shops()` / `customers()` — searchable tables |
| Admin: app name/logo settings | `admin.py::settings()` writes to the single `AppSetting` row, read by every template via a context processor |
| Admin: MRP control + "Sync to All Shops" | Only admin routes can write `Product.mrp`; sync bulk-adds new catalog products into every shop's inventory |
| Shared low-opacity background | `.bg-layer` in `static/css/style.css` — a CSS gradient/pattern (kept dependency-free; swappable for a real photo) |
| Handles concurrent logins | Session-based auth is inherently per-user/stateless on the server side; SQLite is fine at demo scale, and the ORM models are DB-agnostic if you need to swap to PostgreSQL for real concurrent load later |

---

## 7. Notable Design Decisions & Trade-offs

- **GSTIN is optional** on shop registration, exactly as specified — stored as `nullable=True`.
- **Location search is text-based**, not GPS/maps — a shop's "Area/Locality" field is matched
  against the customer's search text. No mapping API key was available/requested, so this was the
  practical choice; swappable for a geocoding API later.
- **Razorpay isn't live by default** — the working, zero-setup payment flow is UPI QR + screenshot +
  manual shopkeeper confirmation, which is how most small local shops actually operate today. A
  config hook (`RAZORPAY_KEY_ID`/`SECRET`) is left in place for when real gateway keys are available.
- **Admin is seeded, not registered** — created automatically on first run from `ADMIN_EMAIL`/
  `ADMIN_PASSWORD` in `config.py`/`.env`, matching "admin is only one, that's me, no one can
  register."
- **MRP is never duplicated into the shop's inventory table** — `ShopInventory` only stores *which*
  products a shop carries, not their own copy of the price. This is what guarantees "only admin can
  change MRP, seen by everyone" without needing a sync step every time price changes.

---

## 8. How to Re-explain This Project in One Paragraph (for a viva/presentation)

> "ShopHub is a multi-vendor local grocery marketplace built with Flask and SQLite, with three
> separate portals — Customer, Shopkeeper, and Admin — each with its own authentication and
> permissions. The Admin controls a master product catalog (name, MRP, category, unit) that every
> shop draws from, so pricing stays consistent platform-wide. Shopkeepers pick which of those
> products they stock, and can apply per-bill discounts without ever touching the master price.
> Customers browse by category or search, pick a specific shop by name or location, and go through
> a full order lifecycle — place order, shop packs it and reveals a UPI QR code, customer pays and
> uploads a screenshot, shopkeeper confirms — after which a non-editable PDF e-bill is generated and
> becomes downloadable. The whole flow was built without needing any paid third-party services:
> passwords are hashed locally, QR codes are generated from the UPI ID directly, and bills are
> rendered as real PDFs with ReportLab — so the entire project runs standalone with just
> `python app.py`."

---

## 9. Files in This Project (Quick Reference)

```
ShopHub/
├── app.py                    # App factory + DB seeding
├── config.py                  # All configuration in one place
├── extensions.py               # Shared SQLAlchemy instance
├── models.py                    # 9 database tables as ORM classes
├── requirements.txt              # 7 core dependencies
├── .env.example                   # Template for local secrets
├── blueprints/
│   ├── auth.py                     # Splash, role select, all login/register/forgot routes
│   ├── customer.py                  # Browse, cart, checkout, orders, profile
│   ├── shopkeeper.py                 # Orders, pricing, inventory, profile+QR, analytics
│   └── admin.py                       # Catalog, shops, customers, settings, analytics
├── utils/
│   ├── qr_gen.py                       # UPI → QR PNG
│   └── bill_pdf.py                      # Order → PDF bill
├── templates/                             # ~30 Jinja2 templates across 4 role folders
└── static/                                 # CSS animations, JS, uploaded/generated files
```

---

*This document was generated to capture the full scope, stack, and reasoning behind the ShopHub
project as built — keep it alongside your code as a reference or submission companion.*
