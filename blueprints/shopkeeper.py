import os
import uuid
from functools import wraps
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from extensions import db
from models import Shopkeeper, Product, ShopInventory, Order, OrderItem, Customer
from utils.qr_gen import generate_upi_qr, generate_order_payment_qr
from utils.bill_pdf import generate_bill_pdf

shopkeeper_bp = Blueprint("shopkeeper", __name__, url_prefix="/shopkeeper")

ALLOWED_IMG_EXT = {"png", "jpg", "jpeg", "webp"}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "shopkeeper":
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.shopkeeper_login"))
        return f(*args, **kwargs)
    return wrapper


def current_shop():
    return Shopkeeper.query.get(session["user_id"])


@shopkeeper_bp.route("/welcome")
@login_required
def welcome():
    return render_template("shopkeeper/welcome.html", shop=current_shop())


@shopkeeper_bp.route("/dashboard")
@login_required
def dashboard():
    shop = current_shop()
    pending_orders = Order.query.filter_by(shopkeeper_id=shop.id).filter(
        Order.status.in_(["placed", "packed", "payment_uploaded"])
    ).count()
    total_products = ShopInventory.query.filter_by(shopkeeper_id=shop.id).count()
    confirmed_orders = Order.query.filter_by(shopkeeper_id=shop.id, status="confirmed").all()
    earnings = sum(o.total_amount for o in confirmed_orders)
    recent = Order.query.filter_by(shopkeeper_id=shop.id).order_by(Order.created_at.desc()).limit(5).all()
    return render_template("shopkeeper/dashboard.html", shop=shop, pending_orders=pending_orders,
                            total_products=total_products, earnings=earnings, recent=recent)


# ---------------- ORDERS ----------------

@shopkeeper_bp.route("/orders")
@login_required
def orders():
    shop = current_shop()
    status_filter = request.args.get("status", "")
    q = Order.query.filter_by(shopkeeper_id=shop.id)
    if status_filter:
        q = q.filter_by(status=status_filter)
    all_orders = q.order_by(Order.created_at.desc()).all()
    return render_template("shopkeeper/orders.html", shop=shop, orders=all_orders, status_filter=status_filter)


@shopkeeper_bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    shop = current_shop()
    order = Order.query.get_or_404(order_id)
    if order.shopkeeper_id != shop.id:
        abort(403)
    customer = Customer.query.get(order.customer_id)
    return render_template("shopkeeper/order_detail.html", shop=shop, order=order, customer=customer)


@shopkeeper_bp.route("/orders/<int:order_id>/update-prices", methods=["POST"])
@login_required
def update_prices(order_id):
    shop = current_shop()
    order = Order.query.get_or_404(order_id)
    if order.shopkeeper_id != shop.id:
        abort(403)
    if order.status == "confirmed":
        flash("Cannot edit a confirmed order.", "error")
        return redirect(url_for("shopkeeper.order_detail", order_id=order.id))

    total = 0
    for item in order.items:
        val = request.form.get(f"price_{item.id}")
        if val is not None:
            try:
                price = float(val)
                if price < 0:
                    price = 0
                item.selling_price = price
            except ValueError:
                pass
        total += item.selling_price * item.qty

    order.discount_note = request.form.get("discount_note", "").strip()
    order.total_amount = total

    # If already packed, the customer may already be looking at a QR - keep its
    # amount in sync with any price/discount change.
    if order.status == "packed" and shop.upi_id:
        try:
            filename = f"orderqr_{order.id}_{uuid.uuid4().hex[:8]}.png"
            save_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "qr")
            order.payment_qr_image = generate_order_payment_qr(
                shop.upi_id, shop.shop_name, order.total_amount, order.id, save_dir, filename
            )
        except Exception:
            current_app.logger.exception("Order QR regeneration failed")

    db.session.commit()
    flash("Bill updated. Catalog MRP is unaffected. ✅", "success")
    return redirect(url_for("shopkeeper.order_detail", order_id=order.id))


@shopkeeper_bp.route("/orders/<int:order_id>/mark-packed", methods=["POST"])
@login_required
def mark_packed(order_id):
    shop = current_shop()
    order = Order.query.get_or_404(order_id)
    if order.shopkeeper_id != shop.id:
        abort(403)
    order.status = "packed"
    order.packed_at = datetime.utcnow()

    # Generate a fresh QR with THIS order's exact amount locked in, so the
    # customer's UPI app won't let them pay a different amount.
    if shop.upi_id:
        try:
            filename = f"orderqr_{order.id}_{uuid.uuid4().hex[:8]}.png"
            save_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "qr")
            order.payment_qr_image = generate_order_payment_qr(
                shop.upi_id, shop.shop_name, order.total_amount, order.id, save_dir, filename
            )
        except Exception:
            current_app.logger.exception("Order QR generation failed")
            order.payment_qr_image = None

    db.session.commit()
    flash("Order marked as packed. Customer can now view your QR code and pay. 📦", "success")
    return redirect(url_for("shopkeeper.order_detail", order_id=order.id))


@shopkeeper_bp.route("/orders/<int:order_id>/confirm-payment", methods=["POST"])
@login_required
def confirm_payment(order_id):
    shop = current_shop()
    order = Order.query.get_or_404(order_id)
    if order.shopkeeper_id != shop.id:
        abort(403)
    if order.status != "payment_uploaded":
        flash("Waiting for the customer to upload a payment screenshot first.", "error")
        return redirect(url_for("shopkeeper.order_detail", order_id=order.id))

    order.status = "confirmed"
    order.confirmed_at = datetime.utcnow()
    db.session.commit()

    customer = Customer.query.get(order.customer_id)
    filename = f"bill_{order.id}_{uuid.uuid4().hex[:8]}.pdf"
    rel_path = generate_bill_pdf(order, shop, customer, current_app.config["BILLS_FOLDER"], filename)
    order.bill_pdf_path = rel_path
    db.session.commit()

    flash("Payment confirmed! Bill generated and now available to the customer. ✅", "success")
    return redirect(url_for("shopkeeper.order_detail", order_id=order.id))


@shopkeeper_bp.route("/orders/<int:order_id>/print-bill")
@login_required
def print_bill(order_id):
    shop = current_shop()
    order = Order.query.get_or_404(order_id)
    if order.shopkeeper_id != shop.id:
        abort(403)
    customer = Customer.query.get(order.customer_id)
    return render_template("shopkeeper/print_bill.html", shop=shop, order=order, customer=customer)


# ---------------- INVENTORY ----------------

@shopkeeper_bp.route("/inventory")
@login_required
def inventory():
    shop = current_shop()
    all_products = Product.query.filter_by(is_active=True).order_by(Product.category, Product.name).all()
    owned_ids = {si.product_id for si in ShopInventory.query.filter_by(shopkeeper_id=shop.id).all()}
    return render_template("shopkeeper/inventory.html", shop=shop, products=all_products, owned_ids=owned_ids)


@shopkeeper_bp.route("/inventory/add/<int:product_id>", methods=["POST"])
@login_required
def inventory_add(product_id):
    shop = current_shop()
    exists = ShopInventory.query.filter_by(shopkeeper_id=shop.id, product_id=product_id).first()
    if not exists:
        db.session.add(ShopInventory(shopkeeper_id=shop.id, product_id=product_id, in_stock=True))
        db.session.commit()
    return redirect(url_for("shopkeeper.inventory"))


@shopkeeper_bp.route("/inventory/remove/<int:product_id>", methods=["POST"])
@login_required
def inventory_remove(product_id):
    shop = current_shop()
    item = ShopInventory.query.filter_by(shopkeeper_id=shop.id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("shopkeeper.inventory"))


@shopkeeper_bp.route("/inventory/add-all", methods=["POST"])
@login_required
def inventory_add_all():
    shop = current_shop()
    owned_ids = {si.product_id for si in ShopInventory.query.filter_by(shopkeeper_id=shop.id).all()}
    all_products = Product.query.filter_by(is_active=True).all()
    added = 0
    for p in all_products:
        if p.id not in owned_ids:
            db.session.add(ShopInventory(shopkeeper_id=shop.id, product_id=p.id, in_stock=True))
            added += 1
    db.session.commit()
    flash(f"Added {added} products from admin catalog to your inventory. 📦", "success")
    return redirect(url_for("shopkeeper.inventory"))


# ---------------- PROFILE ----------------

@shopkeeper_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    shop = current_shop()
    if request.method == "POST":
        shop.name = request.form.get("name", shop.name).strip()
        shop.shop_name = request.form.get("shop_name", shop.shop_name).strip()
        shop.phone = request.form.get("phone", shop.phone).strip()
        shop.gstin = request.form.get("gstin", "").strip() or None
        shop.shop_address = request.form.get("shop_address", "").strip()
        shop.location_area = request.form.get("location_area", "").strip()
        shop.upi_id = request.form.get("upi_id", "").strip()

        qr_file = request.files.get("qr_image")
        if qr_file and qr_file.filename:
            ext = qr_file.filename.rsplit(".", 1)[-1].lower()
            if ext in ALLOWED_IMG_EXT:
                filename = f"qr_{shop.id}_{uuid.uuid4().hex[:8]}.{ext}"
                save_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "qr")
                os.makedirs(save_dir, exist_ok=True)
                qr_file.save(os.path.join(save_dir, filename))
                shop.qr_image = f"uploads/qr/{filename}"
        elif shop.upi_id:
            # auto-generate/refresh QR from the UPI id whenever no file was uploaded
            try:
                filename = f"qr_{shop.id}_{uuid.uuid4().hex[:8]}.png"
                save_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "qr")
                shop.qr_image = generate_upi_qr(shop.upi_id, shop.shop_name, save_dir, filename)
            except Exception as e:
                current_app.logger.exception("QR generation failed")
                flash(f"Profile saved, but QR generation failed: {e}", "error")
                db.session.commit()
                return redirect(url_for("shopkeeper.profile"))

        db.session.commit()
        flash("Profile updated! ✅", "success")
        return redirect(url_for("shopkeeper.profile"))
    return render_template("shopkeeper/profile.html", shop=shop)


@shopkeeper_bp.route("/profile/generate-qr", methods=["POST"])
@login_required
def generate_qr():
    shop = current_shop()
    if not shop.upi_id:
        flash("Please add a UPI ID first.", "error")
        return redirect(url_for("shopkeeper.profile"))
    try:
        filename = f"qr_{shop.id}_{uuid.uuid4().hex[:8]}.png"
        save_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "qr")
        shop.qr_image = generate_upi_qr(shop.upi_id, shop.shop_name, save_dir, filename)
        db.session.commit()
        flash("QR code generated from your UPI ID! 📱", "success")
    except Exception as e:
        current_app.logger.exception("QR generation failed")
        flash(f"QR generation failed: {e}", "error")
    return redirect(url_for("shopkeeper.profile"))


# ---------------- ANALYTICS ----------------

@shopkeeper_bp.route("/analytics")
@login_required
def analytics():
    shop = current_shop()
    confirmed_orders = Order.query.filter_by(shopkeeper_id=shop.id, status="confirmed").all()
    total_earnings = sum(o.total_amount for o in confirmed_orders)
    total_orders = len(confirmed_orders)
    items_sold = {}
    for o in confirmed_orders:
        for it in o.items:
            items_sold[it.product_name] = items_sold.get(it.product_name, 0) + it.qty
    top_products = sorted(items_sold.items(), key=lambda x: x[1], reverse=True)[:10]
    return render_template("shopkeeper/analytics.html", shop=shop, total_earnings=total_earnings,
                            total_orders=total_orders, top_products=top_products)
