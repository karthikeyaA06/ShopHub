from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import db
from models import Customer, Shopkeeper, Admin

auth_bp = Blueprint("auth", __name__)


def clear_session():
    for key in ("role", "user_id", "user_name", "shop_id"):
        session.pop(key, None)


@auth_bp.route("/")
def splash():
    return render_template("auth/splash.html")


@auth_bp.route("/select-role")
def select_role():
    return render_template("auth/role_select.html")


@auth_bp.route("/logout")
def logout():
    clear_session()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.select_role"))


# ---------------- CUSTOMER ----------------

@auth_bp.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        cust = Customer.query.filter_by(phone=phone).first()
        if cust and cust.check_password(password):
            clear_session()
            session["role"] = "customer"
            session["user_id"] = cust.id
            session["user_name"] = cust.name
            return redirect(url_for("customer.welcome"))
        flash("Invalid phone number or password.", "error")
    return render_template("auth/customer_login.html")


@auth_bp.route("/customer/register", methods=["GET", "POST"])
def customer_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        sec_q = request.form.get("security_question", "").strip()
        sec_a = request.form.get("security_answer", "").strip()

        if not (name and phone and password and sec_a):
            flash("Please fill in all required fields.", "error")
            return render_template("auth/customer_register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/customer_register.html")
        if Customer.query.filter_by(phone=phone).first():
            flash("An account with this phone number already exists.", "error")
            return render_template("auth/customer_register.html")

        cust = Customer(name=name, phone=phone, email=email, security_question=sec_q or "What is your favourite food?")
        cust.set_password(password)
        cust.set_security_answer(sec_a)
        db.session.add(cust)
        db.session.commit()
        flash("Registration successful! Please log in. 🎉", "success")
        return redirect(url_for("auth.customer_login"))
    return render_template("auth/customer_register.html")


@auth_bp.route("/customer/forgot", methods=["GET", "POST"])
def customer_forgot():
    step = request.form.get("step", "find")
    cust = None
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        cust = Customer.query.filter_by(phone=phone).first()
        if step == "find":
            if not cust:
                flash("No account found with that phone number.", "error")
                return render_template("auth/customer_forgot.html")
            return render_template("auth/customer_forgot.html", found=cust, phone=phone)
        elif step == "verify":
            answer = request.form.get("security_answer", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")
            if not cust or not cust.check_security_answer(answer):
                flash("Incorrect answer to the security question.", "error")
                return render_template("auth/customer_forgot.html")
            if new_pw != confirm_pw or len(new_pw) < 4:
                flash("Passwords do not match or are too short.", "error")
                return render_template("auth/customer_forgot.html", found=cust, phone=phone)
            cust.set_password(new_pw)
            db.session.commit()
            flash("Password reset successful! Please log in. ✅", "success")
            return redirect(url_for("auth.customer_login"))
    return render_template("auth/customer_forgot.html")


# ---------------- SHOPKEEPER ----------------

@auth_bp.route("/shopkeeper/login", methods=["GET", "POST"])
def shopkeeper_login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        shop = Shopkeeper.query.filter_by(phone=phone).first()
        if shop and shop.check_password(password):
            if not shop.is_active:
                flash("Your shop account has been deactivated. Contact admin.", "error")
                return render_template("auth/shopkeeper_login.html")
            clear_session()
            session["role"] = "shopkeeper"
            session["user_id"] = shop.id
            session["user_name"] = shop.shop_name
            return redirect(url_for("shopkeeper.welcome"))
        flash("Invalid phone number or password.", "error")
    return render_template("auth/shopkeeper_login.html")


@auth_bp.route("/shopkeeper/register", methods=["GET", "POST"])
def shopkeeper_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        shop_name = request.form.get("shop_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip() or None
        gstin = request.form.get("gstin", "").strip() or None  # optional - can register w/o GSTIN
        shop_address = request.form.get("shop_address", "").strip()
        location_area = request.form.get("location_area", "").strip()
        upi_id = request.form.get("upi_id", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        sec_q = request.form.get("security_question", "").strip()
        sec_a = request.form.get("security_answer", "").strip()

        if not (name and shop_name and phone and password and sec_a):
            flash("Please fill in all required fields.", "error")
            return render_template("auth/shopkeeper_register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/shopkeeper_register.html")
        if Shopkeeper.query.filter_by(phone=phone).first():
            flash("An account with this phone number already exists.", "error")
            return render_template("auth/shopkeeper_register.html")

        shop = Shopkeeper(
            name=name, shop_name=shop_name, phone=phone, email=email,
            gstin=gstin, shop_address=shop_address, location_area=location_area,
            upi_id=upi_id, security_question=sec_q or "What is your favourite food?"
        )
        shop.set_password(password)
        shop.set_security_answer(sec_a)
        db.session.add(shop)
        db.session.commit()
        flash("Shop registered successfully! Please log in. 🎉", "success")
        return redirect(url_for("auth.shopkeeper_login"))
    return render_template("auth/shopkeeper_register.html")


@auth_bp.route("/shopkeeper/forgot", methods=["GET", "POST"])
def shopkeeper_forgot():
    step = request.form.get("step", "find")
    shop = None
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        shop = Shopkeeper.query.filter_by(phone=phone).first()
        if step == "find":
            if not shop:
                flash("No shop account found with that phone number.", "error")
                return render_template("auth/shopkeeper_forgot.html")
            return render_template("auth/shopkeeper_forgot.html", found=shop, phone=phone)
        elif step == "verify":
            answer = request.form.get("security_answer", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")
            if not shop or not shop.check_security_answer(answer):
                flash("Incorrect answer to the security question.", "error")
                return render_template("auth/shopkeeper_forgot.html")
            if new_pw != confirm_pw or len(new_pw) < 4:
                flash("Passwords do not match or are too short.", "error")
                return render_template("auth/shopkeeper_forgot.html", found=shop, phone=phone)
            shop.set_password(new_pw)
            db.session.commit()
            flash("Password reset successful! Please log in. ✅", "success")
            return redirect(url_for("auth.shopkeeper_login"))
    return render_template("auth/shopkeeper_forgot.html")


# ---------------- ADMIN (login only, no registration) ----------------

@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(email=email).first()
        if admin and admin.check_password(password):
            clear_session()
            session["role"] = "admin"
            session["user_id"] = admin.id
            session["user_name"] = admin.name
            return redirect(url_for("admin.dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("auth/admin_login.html")
