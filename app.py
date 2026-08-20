import os
from flask import Flask
from config import Config
from extensions import db
from models import Admin, AppSetting, Product


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["BILLS_FOLDER"], exist_ok=True)

    db.init_app(app)

    from blueprints.auth import auth_bp
    from blueprints.customer import customer_bp
    from blueprints.shopkeeper import shopkeeper_bp
    from blueprints.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(shopkeeper_bp)
    app.register_blueprint(admin_bp)

    @app.template_filter("ist")
    def ist_filter(dt, fmt="%d %b %Y, %I:%M %p"):
        """Usage in templates: {{ order.created_at | ist }} - converts the stored
        UTC timestamp to IST for display, since the app runs/stores in UTC."""
        from utils.timezone import format_ist
        return format_ist(dt, fmt)

    @app.template_global()
    def product_img_src(image_value):
        """Resolves a product/logo image field to a usable <img src>,
        whether it's a pasted external URL or a local static/ path."""
        from flask import url_for
        if not image_value:
            return url_for("static", filename="img/product_placeholder.png")
        if image_value.startswith("http://") or image_value.startswith("https://"):
            return image_value
        return url_for("static", filename=image_value)

    @app.template_global()
    def upi_pay_links(shop, order):
        """Returns UPI app deep-links (Google Pay/PhonePe/Paytm/generic) for this
        order, with the amount locked in - or None if the shop has no UPI ID."""
        if not shop or not shop.upi_id:
            return None
        from utils.qr_gen import upi_app_links
        return upi_app_links(shop.upi_id, shop.shop_name, order.total_amount, order.id)

    @app.context_processor
    def inject_razorpay_flag():
        return {"razorpay_enabled": bool(app.config.get("RAZORPAY_KEY_ID") and app.config.get("RAZORPAY_KEY_SECRET"))}

    @app.context_processor
    def inject_settings():
        settings = AppSetting.query.first()
        if not settings:
            settings = AppSetting(app_name="ShopHub")
            db.session.add(settings)
            db.session.commit()
        return {"app_settings": settings}

    with app.app_context():
        db.create_all()
        seed_data(app)

    return app


def seed_data(app):
    """Creates the one-and-only admin account and a few demo products on first run."""
    if not Admin.query.first():
        admin = Admin(email=app.config["ADMIN_EMAIL"], name="Administrator")
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        print(f"[ShopHub] Seeded admin login -> email: {app.config['ADMIN_EMAIL']}  "
              f"password: {app.config['ADMIN_PASSWORD']}")

    if not AppSetting.query.first():
        db.session.add(AppSetting(app_name="ShopHub"))

    if not Product.query.first():
        demo_products = [
            ("Toned Milk 500ml", "Dairy", 28, "ltr"),
            ("Paneer 200g", "Dairy", 90, "gm"),
            ("Butter 100g", "Dairy", 55, "gm"),
            ("Toor Dal", "Pulses", 140, "kg"),
            ("Moong Dal", "Pulses", 130, "kg"),
            ("Chana Dal", "Pulses", 110, "kg"),
            ("Turmeric Powder", "Spices", 45, "gm"),
            ("Red Chilli Powder", "Spices", 60, "gm"),
            ("Garam Masala", "Spices", 75, "gm"),
            ("Basmati Rice", "Grains", 120, "kg"),
            ("Wheat Flour (Atta)", "Grains", 55, "kg"),
            ("Sunflower Oil 1L", "Oils", 150, "ltr"),
        ]
        for name, cat, mrp, unit in demo_products:
            db.session.add(Product(name=name, category=cat, mrp=mrp, unit=unit))

    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
