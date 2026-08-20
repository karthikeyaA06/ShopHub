import os
import uuid
from functools import wraps
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify, current_app, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from extensions import db
from models import Customer, Shopkeeper, Product, ShopInventory, CartItem, Order, OrderItem
from utils.bill_pdf import generate_bill_pdf

try:
    import razorpay
except ImportError:
    razorpay = None

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")

ALLOWED_IMG_EXT = {"png", "jpg", "jpeg", "webp"}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "customer":
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.customer_login"))
        return f(*args, **kwargs)
    return wrapper


def current_customer():
    return Customer.query.get(session["user_id"])


@customer_bp.route("/welcome")
@login_required
def welcome():
    cust = current_customer()
    return render_template("customer/welcome.html", customer=cust)


@customer_bp.route("/home")
@login_required
def home():
    cust = current_customer()
    category = request.args.get("category", "")
    query = request.args.get("q", "").strip()

    if cust.selected_shop_id:
        shop = Shopkeeper.query.get(cust.selected_shop_id)
        prod_ids = [si.product_id for si in ShopInventory.query.filter_by(
            shopkeeper_id=shop.id, in_stock=True).all()]
        products_q = Product.query.filter(Product.id.in_(prod_ids), Product.is_active == True)
    else:
        shop = None
        products_q = Product.query.filter_by(is_active=True)

    if category:
        products_q = products_q.filter_by(category=category)
    if query:
        products_q = products_q.filter(Product.name.ilike(f"%{query}%"))

    products = products_q.order_by(Product.category, Product.name).all()
    categories = [c[0] for c in db.session.query(Product.category).distinct().all()]

    cart_count = CartItem.query.filter_by(customer_id=cust.id).count()

    return render_template(
        "customer/home.html", customer=cust, shop=shop, products=products,
        categories=categories, active_category=category, query=query, cart_count=cart_count
    )


@customer_bp.route("/store-search")
@login_required
def store_search():
    name_q = request.args.get("name", "").strip()
    loc_q = request.args.get("location", "").strip()
    results = []
    if name_q or loc_q:
        q = Shopkeeper.query.filter_by(is_active=True)
        if name_q:
            q = q.filter(Shopkeeper.shop_name.ilike(f"%{name_q}%"))
        if loc_q:
            q = q.filter(Shopkeeper.location_area.ilike(f"%{loc_q}%"))
        results = q.all()
    return render_template("customer/store_search.html", results=results, name_q=name_q, loc_q=loc_q)


@customer_bp.route("/select-shop/<int:shop_id>")
@login_required
def select_shop(shop_id):
    shop = Shopkeeper.query.get_or_404(shop_id)
    cust = current_customer()
    if cust.selected_shop_id != shop.id:
        # switching shops clears cart (cart items belong to a specific shop)
        CartItem.query.filter_by(customer_id=cust.id).delete()
    cust.selected_shop_id = shop.id
    db.session.commit()
    flash(f"Now shopping from {shop.shop_name} 🛍️", "success")
    return redirect(url_for("customer.home"))


@customer_bp.route("/add-to-cart", methods=["POST"])
@login_required
def add_to_cart():
    cust = current_customer()
    if not cust.selected_shop_id:
        return jsonify({"ok": False, "message": "Please select a shop first."}), 400

    product_id = int(request.form.get("product_id"))
    qty = float(request.form.get("qty", 1))

    inv = ShopInventory.query.filter_by(shopkeeper_id=cust.selected_shop_id, product_id=product_id).first()
    if not inv or not inv.in_stock:
        return jsonify({"ok": False, "message": "This product is not available at this shop."}), 400

    item = CartItem.query.filter_by(
        customer_id=cust.id, shopkeeper_id=cust.selected_shop_id, product_id=product_id
    ).first()
    if item:
        item.qty += qty
    else:
        item = CartItem(customer_id=cust.id, shopkeeper_id=cust.selected_shop_id, product_id=product_id, qty=qty)
        db.session.add(item)
    db.session.commit()

    cart_count = CartItem.query.filter_by(customer_id=cust.id).count()
    return jsonify({"ok": True, "message": "Added to cart! 🎉", "cart_count": cart_count})


@customer_bp.route("/cart")
@login_required
def cart():
    cust = current_customer()
    items = CartItem.query.filter_by(customer_id=cust.id).all()
    shop = Shopkeeper.query.get(cust.selected_shop_id) if cust.selected_shop_id else None
    total = sum(i.product.mrp * i.qty for i in items)
    return render_template("customer/cart.html", customer=cust, items=items, shop=shop, total=total)


@customer_bp.route("/cart/update", methods=["POST"])
@login_required
def cart_update():
    item_id = int(request.form.get("item_id"))
    qty = float(request.form.get("qty", 1))
    item = CartItem.query.get_or_404(item_id)
    if item.customer_id != session["user_id"]:
        abort(403)
    if qty <= 0:
        db.session.delete(item)
    else:
        item.qty = qty
    db.session.commit()
    return redirect(url_for("customer.cart"))


@customer_bp.route("/cart/remove/<int:item_id>")
@login_required
def cart_remove(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.customer_id != session["user_id"]:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("customer.cart"))


@customer_bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cust = current_customer()
    items = CartItem.query.filter_by(customer_id=cust.id).all()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("customer.cart"))
    if not cust.delivery_address:
        flash("Please add a delivery address in your profile before checking out.", "error")
        return redirect(url_for("customer.profile"))

    order = Order(customer_id=cust.id, shopkeeper_id=cust.selected_shop_id, status="placed")
    db.session.add(order)
    db.session.flush()

    total_mrp = 0
    for ci in items:
        oi = OrderItem(
            order_id=order.id, product_id=ci.product.id, product_name=ci.product.name,
            unit=ci.product.unit, qty=ci.qty, mrp=ci.product.mrp, selling_price=ci.product.mrp
        )
        total_mrp += ci.product.mrp * ci.qty
        db.session.add(oi)
        db.session.delete(ci)

    order.total_mrp = total_mrp
    order.total_amount = total_mrp
    db.session.commit()
    flash("Order placed! Track it under My Orders. 📦", "success")
    return redirect(url_for("customer.orders"))


@customer_bp.route("/orders")
@login_required
def orders():
    cust = current_customer()
    all_orders = Order.query.filter_by(customer_id=cust.id).order_by(Order.created_at.desc()).all()
    return render_template("customer/orders.html", customer=cust, orders=all_orders)


@customer_bp.route("/orders/<int:order_id>/upload-payment", methods=["POST"])
@login_required
def upload_payment(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != session["user_id"]:
        abort(403)
    if order.status != "packed":
        flash("This order is not ready for payment upload yet.", "error")
        return redirect(url_for("customer.orders"))

    file = request.files.get("screenshot")
    if not file or file.filename == "":
        flash("Please choose a screenshot to upload.", "error")
        return redirect(url_for("customer.orders"))
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMG_EXT:
        flash("Only image files are allowed.", "error")
        return redirect(url_for("customer.orders"))

    filename = f"pay_{order.id}_{uuid.uuid4().hex[:8]}.{ext}"
    save_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "payments")
    os.makedirs(save_dir, exist_ok=True)
    file.save(os.path.join(save_dir, filename))

    order.payment_screenshot = f"uploads/payments/{filename}"
    order.status = "payment_uploaded"
    db.session.commit()
    flash("Payment screenshot uploaded! Waiting for shop confirmation. ⏳", "success")
    return redirect(url_for("customer.orders"))


def _razorpay_client():
    key_id = current_app.config.get("RAZORPAY_KEY_ID")
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET")
    if not razorpay or not key_id or not key_secret:
        return None
    return razorpay.Client(auth=(key_id, key_secret))


@customer_bp.route("/orders/<int:order_id>/razorpay/create", methods=["POST"])
@login_required
def razorpay_create(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != session["user_id"]:
        abort(403)
    if order.status != "packed":
        return jsonify({"ok": False, "message": "This order isn't ready for payment yet."}), 400

    client = _razorpay_client()
    if not client:
        return jsonify({"ok": False, "message": "Razorpay is not configured on this server."}), 400

    shop = Shopkeeper.query.get(order.shopkeeper_id)
    cust = current_customer()

    try:
        rp_order = client.order.create({
            "amount": int(round(order.total_amount * 100)),  # paise
            "currency": "INR",
            "receipt": f"shophub_order_{order.id}",
            "payment_capture": 1,
        })
    except Exception as e:
        current_app.logger.exception("Razorpay order creation failed")
        return jsonify({"ok": False, "message": f"Could not start payment: {e}"}), 500

    order.razorpay_order_id = rp_order["id"]
    db.session.commit()

    return jsonify({
        "ok": True,
        "key_id": current_app.config["RAZORPAY_KEY_ID"],
        "razorpay_order_id": rp_order["id"],
        "amount": rp_order["amount"],
        "currency": rp_order["currency"],
        "shop_name": shop.shop_name,
        "customer_name": cust.name,
        "customer_phone": cust.phone,
    })


@customer_bp.route("/orders/<int:order_id>/razorpay/verify", methods=["POST"])
@login_required
def razorpay_verify(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != session["user_id"]:
        abort(403)

    client = _razorpay_client()
    if not client:
        return jsonify({"ok": False, "message": "Razorpay is not configured on this server."}), 400

    data = request.get_json(silent=True) or {}
    rp_payment_id = data.get("razorpay_payment_id")
    rp_order_id = data.get("razorpay_order_id")
    rp_signature = data.get("razorpay_signature")

    if not (rp_payment_id and rp_order_id and rp_signature):
        return jsonify({"ok": False, "message": "Missing payment details."}), 400
    if rp_order_id != order.razorpay_order_id:
        return jsonify({"ok": False, "message": "Order mismatch."}), 400

    # Cryptographic verification (HMAC-SHA256 using your Razorpay secret key) -
    # this is what makes the payment trustworthy: it cannot be faked client-side.
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": rp_order_id,
            "razorpay_payment_id": rp_payment_id,
            "razorpay_signature": rp_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"ok": False, "message": "Payment verification failed. Please contact the shop."}), 400

    # Signature is valid -> payment is genuine. Confirm the order automatically,
    # no manual shopkeeper screenshot-check needed for this payment method.
    order.payment_method = "razorpay"
    order.razorpay_payment_id = rp_payment_id
    order.razorpay_signature = rp_signature
    order.status = "confirmed"
    order.confirmed_at = datetime.utcnow()
    db.session.commit()

    shop = Shopkeeper.query.get(order.shopkeeper_id)
    cust = current_customer()
    filename = f"bill_{order.id}_{uuid.uuid4().hex[:8]}.pdf"
    rel_path = generate_bill_pdf(order, shop, cust, current_app.config["BILLS_FOLDER"], filename)
    order.bill_pdf_path = rel_path
    db.session.commit()

    return jsonify({"ok": True, "message": "Payment verified securely! ✅"})


@customer_bp.route("/orders/<int:order_id>/download-bill")
@login_required
def download_bill(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != session["user_id"]:
        abort(403)
    if order.status != "confirmed" or not order.bill_pdf_path:
        flash("Bill is not available yet — waiting for shop to confirm payment.", "error")
        return redirect(url_for("customer.orders"))
    directory = current_app.config["BILLS_FOLDER"]
    fname = os.path.basename(order.bill_pdf_path)
    return send_from_directory(directory, fname, as_attachment=True,
                                download_name=f"ShopHub_Bill_{order.id}.pdf")


@customer_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    cust = current_customer()
    if request.method == "POST":
        cust.name = request.form.get("name", cust.name).strip()
        cust.delivery_address = request.form.get("delivery_address", "").strip()
        db.session.commit()
        flash("Profile updated! ✅", "success")
        return redirect(url_for("customer.profile"))
    return render_template("customer/profile.html", customer=cust)
