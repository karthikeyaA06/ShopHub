import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from utils.timezone import format_ist


def generate_bill_pdf(order, shopkeeper, customer, save_dir, filename):
    os.makedirs(save_dir, exist_ok=True)
    full_path = os.path.join(save_dir, filename)

    doc = SimpleDocTemplate(
        full_path, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=18, spaceAfter=2)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    normal = styles["Normal"]
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT)
    center = ParagraphStyle("center", parent=styles["Normal"], alignment=TA_CENTER)

    elements = []
    elements.append(Paragraph(shopkeeper.shop_name, title_style))
    elements.append(Paragraph(shopkeeper.shop_address or "-", sub_style))
    gstin_line = f"GSTIN: {shopkeeper.gstin}" if shopkeeper.gstin else "GSTIN: Not Registered"
    elements.append(Paragraph(gstin_line, sub_style))
    elements.append(Spacer(1, 8))

    # Customer + order info table
    info_data = [
        ["Bill No:", f"SH-{order.id:06d}", "Date:", format_ist(order.confirmed_at, suffix=" IST")],
        ["Customer:", customer.name, "Phone:", customer.phone],
    ]
    info_table = Table(info_data, colWidths=[60, 180, 50, 180])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # Items table
    data = [["#", "Item", "Qty", "Unit", "MRP (Rs)", "Price (Rs)", "You Save (Rs)", "Total (Rs)"]]
    for idx, item in enumerate(order.items, start=1):
        saved = round((item.mrp - item.selling_price) * item.qty, 2)
        line_total = round(item.selling_price * item.qty, 2)
        data.append([
            str(idx), item.product_name, str(item.qty), item.unit,
            f"{item.mrp:.2f}", f"{item.selling_price:.2f}",
            f"{saved:.2f}", f"{line_total:.2f}"
        ])

    items_table = Table(data, colWidths=[20, 130, 35, 35, 55, 55, 60, 55], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 10))

    total_mrp = sum(i.mrp * i.qty for i in order.items)
    total_saved = round(total_mrp - order.total_amount, 2)

    totals_data = [
        ["Total MRP:", f"Rs {total_mrp:.2f}"],
        ["You Saved:", f"Rs {total_saved:.2f}"],
        ["Amount Paid:", f"Rs {order.total_amount:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[420, 100])
    totals_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 2), (-1, 2), 12),
        ("LINEABOVE", (0, 2), (-1, 2), 0.75, colors.black),
        ("TOPPADDING", (0, 2), (-1, 2), 6),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("This is a system-generated e-bill and does not require a signature.", sub_style))
    elements.append(Paragraph("Thank you for shopping with us! 🛍️", center))

    doc.build(elements)
    return f"bills/{filename}"
