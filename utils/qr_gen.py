import os
import urllib.parse
import qrcode


def build_upi_params(upi_id: str, shop_name: str, amount: float = None, order_id: int = None) -> dict:
    """Builds the standard UPI intent parameters, shared by both the QR code
    and the direct app-launch links, so they always stay identical."""
    params = {"pa": upi_id, "pn": shop_name, "cu": "INR"}
    if amount is not None:
        params["am"] = f"{amount:.2f}"
    if order_id is not None:
        params["tn"] = f"ShopHub Order {order_id}"
        params["tr"] = f"SHOPHUB{order_id}"
    return params


def generate_upi_qr(upi_id: str, shop_name: str, save_dir: str, filename: str) -> str:
    """
    Generates a scannable UPI QR code PNG from a UPI ID and saves it.
    No fixed amount - used as the shop's general/profile QR.
    Returns the relative path (from /static) to store in the DB.
    """
    upi_uri = "upi://pay?" + urllib.parse.urlencode(build_upi_params(upi_id, shop_name))
    img = qrcode.make(upi_uri)

    os.makedirs(save_dir, exist_ok=True)
    full_path = os.path.join(save_dir, filename)
    img.save(full_path)

    # Always return forward-slash path for use in url_for('static', filename=...) -
    # os.path.join would use backslashes on Windows, which breaks browser URLs.
    return f"uploads/qr/{filename}"


def generate_order_payment_qr(upi_id: str, shop_name: str, amount: float, order_id: int,
                               save_dir: str, filename: str) -> str:
    """
    Generates a QR for one specific order with the amount locked in via the UPI 'am' parameter.
    Most UPI apps (Google Pay, PhonePe, Paytm, etc.) treat a pre-filled amount as non-editable
    when it arrives this way, so the customer can't change how much they pay.
    Returns the relative path (from /static) to store in the DB.
    """
    params = build_upi_params(upi_id, shop_name, amount, order_id)
    upi_uri = "upi://pay?" + urllib.parse.urlencode(params)
    img = qrcode.make(upi_uri)

    os.makedirs(save_dir, exist_ok=True)
    full_path = os.path.join(save_dir, filename)
    img.save(full_path)

    return f"uploads/qr/{filename}"


def upi_app_links(upi_id: str, shop_name: str, amount: float, order_id: int) -> dict:
    """
    Returns deep links that open specific UPI apps directly (instead of scanning a QR),
    all pre-filled with the shopkeeper's UPI ID and this order's locked amount.
    Only works on mobile devices with the corresponding app installed.
    """
    params = build_upi_params(upi_id, shop_name, amount, order_id)
    qs = urllib.parse.urlencode(params)
    return {
        "generic": f"upi://pay?{qs}",     # lets the phone show its own app-chooser
        "gpay": f"tez://upi/pay?{qs}",     # Google Pay's legacy "Tez" scheme
        "phonepe": f"phonepe://pay?{qs}",
        "paytm": f"paytmmp://pay?{qs}",
    }
