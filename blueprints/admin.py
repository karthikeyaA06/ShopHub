import os
import uuid
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app, abort
)
from werkzeug.utils import secure_filename
from extensions import db
from models import Admin, Shopkeeper, Customer, Product, ShopInventory, Order, AppSetting

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_IMG_EXT = {"png", "jpg", "jpeg", "webp"}
ALLOWED_UNITS = ["pcs", "kg", "gm", "ltr", "ml", "dozen", "pack"]


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("auth.admin_login"))
        return f(*args, **kwargs)
    return wrapper


def get_settings():
    settings = AppSetting.query.first()
    if not settings:
        settings = AppSetting(app_name="ShopHub")
        db.session.add(settings)
        db.session.commit()
    return settings


@admin_bp.route("/dashboard")
@login_required
def dashboard():
    settings = get_settings()
    total_shops = Shopkeeper.query.count()
    total_customers = Customer.query.count()
    total_products = Product.query.count()
    total_orders = Order.query.count()
    confirmed = Order.query.filter_by(status="confirmed").all()
    platform_gmv = sum(o.total_amount for o in confirmed)
    return render_template("admin/dashboard.html", settings=settings, total_shops=total_shops,
                            total_customers=total_customers, total_products=total_products,
                            total_orders=total_orders, platform_gmv=platform_gmv)


# ---------------- SHOPS ----------------

@admin_bp.route("/shops")
@login_required
def shops():
    q = request.args.get("q", "").strip()
    query = Shopkeeper.query
    if q:
        query = query.filter(Shopkeeper.shop_name.ilike(f"%{q}%"))
    all_shops = query.order_by(Shopkeeper.created_at.desc()).all()
    return render_template("admin/shops.html", shops=all_shops, q=q)


@admin_bp.route("/shops/<int:shop_id>/toggle-active", methods=["POST"])
@login_required
def toggle_shop_active(shop_id):
    shop = Shopkeeper.query.get_or_404(shop_id)
    shop.is_active = not shop.is_active
    db.session.commit()
    flash(f"{shop.shop_name} is now {'active' if shop.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.shops"))


# ---------------- CUSTOMERS ----------------

@admin_bp.route("/customers")
@login_required
def customers():
    q = request.args.get("q", "").strip()
    query = Customer.query
    if q:
        query = query.filter(Customer.name.ilike(f"%{q}%"))
    all_customers = query.order_by(Customer.created_at.desc()).all()
    return render_template("admin/customers.html", customers=all_customers, q=q)


# ---------------- INVENTORY (MASTER CATALOG) ----------------

@admin_bp.route("/inventory")
@login_required
def inventory():
    category = request.args.get("category", "")
    query = Product.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.category, Product.name).all()
    categories = [c[0] for c in db.session.query(Product.category).distinct().all()]
    return render_template("admin/inventory.html", products=products, categories=categories,
                            active_category=category, units=ALLOWED_UNITS)

@admin_bp.route("/inventory/delete/<int:product_id>", methods=["POST"])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    flash("Product successfully removed.", "success")
    return redirect(url_for('admin.inventory'))


@admin_bp.route("/inventory/add", methods=["POST"])
@login_required
def inventory_add():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    mrp = request.form.get("mrp", "0")
    unit = request.form.get("unit", "pcs")
    description = request.form.get("description", "").strip()
    image_url = request.form.get("image_url", "").strip()

    if not (name and category and mrp):
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("admin.inventory"))

    product = Product(name=name, category=category, mrp=float(mrp), unit=unit, description=description)
    if image_url:
        product.image = image_url

    db.session.add(product)
    db.session.commit()
    flash(f"'{name}' added to master catalog. 🆕", "success")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:product_id>/edit", methods=["POST"])
@login_required
def inventory_edit(product_id):
    product = Product.query.get_or_404(product_id)
    product.name = request.form.get("name", product.name).strip()
    product.category = request.form.get("category", product.category).strip()
    mrp = request.form.get("mrp")
    if mrp:
        product.mrp = float(mrp)
    product.unit = request.form.get("unit", product.unit)
    product.description = request.form.get("description", product.description).strip()
    product.is_active = request.form.get("is_active") == "on"

    image_url = request.form.get("image_url", "").strip()
    if image_url:
        product.image = image_url

    db.session.commit()
    flash(f"'{product.name}' updated. This MRP change is now visible to every shop. ✅", "success")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/sync-all-shops", methods=["POST"])
@login_required
def sync_all_shops():
    """Pushes every active master product into every shop's inventory (new products only)."""
    shops = Shopkeeper.query.all()
    products = Product.query.filter_by(is_active=True).all()
    added = 0
    for shop in shops:
        owned_ids = {si.product_id for si in ShopInventory.query.filter_by(shopkeeper_id=shop.id).all()}
        for p in products:
            if p.id not in owned_ids:
                db.session.add(ShopInventory(shopkeeper_id=shop.id, product_id=p.id, in_stock=True))
                added += 1
    db.session.commit()
    flash(f"Synced catalog to all shops. {added} new listings added across {len(shops)} shops. 🔄", "success")
    return redirect(url_for("admin.inventory"))


# ---------------- APP SETTINGS ----------------

@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    app_settings = get_settings()
    if request.method == "POST":
        app_settings.app_name = request.form.get("app_name", app_settings.app_name).strip()
        logo_file = request.files.get("logo")
        if logo_file and logo_file.filename:
            ext = logo_file.filename.rsplit(".", 1)[-1].lower()
            if ext in ALLOWED_IMG_EXT:
                filename = f"logo_{uuid.uuid4().hex[:8]}.{ext}"
                save_dir = os.path.join(current_app.root_path, "static", "img")
                os.makedirs(save_dir, exist_ok=True)
                logo_file.save(os.path.join(save_dir, filename))
                app_settings.logo_path = f"img/{filename}"
                
        

        db.session.commit()
        flash("App settings updated! ✅", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", settings=app_settings)


# ---------------- API SECURITY (placeholder / demo) ----------------

@admin_bp.route("/security")
@login_required
def security():
    admin = Admin.query.get(session["user_id"])
    return render_template("admin/security.html", admin=admin)


# ---------------- ANALYTICS ----------------

@admin_bp.route("/analytics")
@login_required
def analytics():
    confirmed = Order.query.filter_by(status="confirmed").all()
    platform_gmv = sum(o.total_amount for o in confirmed)
    by_shop = {}
    for o in confirmed:
        by_shop.setdefault(o.shopkeeper_id, 0)
        by_shop[o.shopkeeper_id] += o.total_amount
    shop_rankings = []
    for shop_id, total in sorted(by_shop.items(), key=lambda x: x[1], reverse=True)[:10]:
        shop = Shopkeeper.query.get(shop_id)
        if shop:
            shop_rankings.append((shop.shop_name, total))
    return render_template("admin/analytics.html", platform_gmv=platform_gmv,
                            total_orders=len(confirmed), shop_rankings=shop_rankings)