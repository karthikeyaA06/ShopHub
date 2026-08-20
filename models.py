from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class AppSetting(db.Model):
    __tablename__ = "app_settings"
    id = db.Column(db.Integer, primary_key=True)
    app_name = db.Column(db.String(120), default="ShopHub")
    logo_path = db.Column(db.String(255), default="img/default_logo.png")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Admin(db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), default="Administrator")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    delivery_address = db.Column(db.Text, default="")
    security_question = db.Column(db.String(255), default="What is your favourite food?")
    security_answer_hash = db.Column(db.String(255), nullable=True)
    selected_shop_id = db.Column(db.Integer, db.ForeignKey("shopkeepers.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship("Order", backref="customer", lazy=True)
    cart_items = db.relationship("CartItem", backref="customer", lazy=True, cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def set_security_answer(self, ans):
        self.security_answer_hash = generate_password_hash(ans.strip().lower())

    def check_security_answer(self, ans):
        if not self.security_answer_hash:
            return False
        return check_password_hash(self.security_answer_hash, ans.strip().lower())


class Shopkeeper(db.Model):
    __tablename__ = "shopkeepers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    shop_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    gstin = db.Column(db.String(30), nullable=True)
    shop_address = db.Column(db.Text, default="")
    location_area = db.Column(db.String(120), default="")  # simple text-based location for search
    upi_id = db.Column(db.String(120), default="")
    qr_image = db.Column(db.String(255), nullable=True)
    security_question = db.Column(db.String(255), default="What is your favourite food?")
    security_answer_hash = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inventory = db.relationship("ShopInventory", backref="shopkeeper", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="shopkeeper", lazy=True)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def set_security_answer(self, ans):
        self.security_answer_hash = generate_password_hash(ans.strip().lower())

    def check_security_answer(self, ans):
        if not self.security_answer_hash:
            return False
        return check_password_hash(self.security_answer_hash, ans.strip().lower())


class Product(db.Model):
    """Master catalog - owned/edited only by Admin."""
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)  # Dairy, Pulses, Spices, etc.
    mrp = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default="pcs")  # kg, pcs, ltr, gm, etc.
    image = db.Column(db.String(255), default="img/product_placeholder.png")
    description = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ShopInventory(db.Model):
    """Which master products a shopkeeper stocks."""
    __tablename__ = "shop_inventory"
    id = db.Column(db.Integer, primary_key=True)
    shopkeeper_id = db.Column(db.Integer, db.ForeignKey("shopkeepers.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    in_stock = db.Column(db.Boolean, default=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")

    __table_args__ = (db.UniqueConstraint("shopkeeper_id", "product_id", name="uix_shop_product"),)


class CartItem(db.Model):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    shopkeeper_id = db.Column(db.Integer, db.ForeignKey("shopkeepers.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    qty = db.Column(db.Float, default=1)

    product = db.relationship("Product")


ORDER_STATUSES = [
    "placed",            # customer checked out
    "packed",            # shopkeeper marked packed, QR shown to customer
    "payment_uploaded",  # customer uploaded payment screenshot
    "confirmed",         # shopkeeper confirmed payment -> bill downloadable
    "cancelled",
]


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    shopkeeper_id = db.Column(db.Integer, db.ForeignKey("shopkeepers.id"), nullable=False)
    status = db.Column(db.String(30), default="placed")
    total_mrp = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, default=0)  # after shopkeeper edits/discount
    discount_note = db.Column(db.String(255), default="")
    payment_screenshot = db.Column(db.String(255), nullable=True)
    payment_qr_image = db.Column(db.String(255), nullable=True)  # order-specific QR with amount locked in
    payment_method = db.Column(db.String(20), default="upi_manual")  # 'upi_manual' or 'razorpay'
    razorpay_order_id = db.Column(db.String(100), nullable=True)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    razorpay_signature = db.Column(db.String(255), nullable=True)
    bill_pdf_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    packed_at = db.Column(db.DateTime, nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)  # snapshot at order time
    unit = db.Column(db.String(20), default="pcs")
    qty = db.Column(db.Float, default=1)
    mrp = db.Column(db.Float, nullable=False)          # snapshot MRP at order time
    selling_price = db.Column(db.Float, nullable=False)  # editable by shopkeeper, defaults to mrp

    product = db.relationship("Product")
bg_image = db.Column(db.String(255), nullable=True)
bg_opacity = db.Column(db.Float, default=0.05)