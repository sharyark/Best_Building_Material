"""Printable documents: challan, invoice/bill, payment voucher (HTML -> PDF)."""

import html

from fastapi import Response
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.core.config import get_settings
from app.modules.common import get_or_404
from app.modules.deliveries.models import Delivery
from app.modules.invoices import service as invoice_service
from app.modules.invoices.models import Invoice
from app.modules.masters.models import Material, MoneyAccount, Party, Site, Staff, Vehicle
from app.modules.payments.models import Payment
from app.modules.reports.table import fmt_date, fmt_money, fmt_qty

CSS = """
@page { size: A5 landscape; margin: 10mm; }
@page :first { }
body { font-family: DejaVu Sans, Arial, sans-serif; font-size: 10pt; color: #111; }
h1 { font-size: 16pt; margin: 0; } .sub { color: #555; margin-bottom: 8px; }
.head { display: flex; justify-content: space-between; border-bottom: 2px solid #1f4e79; padding-bottom: 6px; margin-bottom: 10px; }
.grid { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
.grid td { padding: 3px 6px; vertical-align: top; } .k { color: #666; width: 22%; }
table.items { width: 100%; border-collapse: collapse; }
table.items th { background: #1f4e79; color: #fff; padding: 4px 6px; text-align: left; }
table.items td { padding: 4px 6px; border-bottom: 1px solid #ddd; }
.r { text-align: right; } .tot td { font-weight: bold; border-top: 2px solid #333; }
.sign { margin-top: 28px; display: flex; justify-content: space-between; color: #555; }
"""
A4 = "@page { size: A4; margin: 14mm; }"


def _page(title: str, number: str, body: str, *, a4: bool = False) -> bytes:
    biz = html.escape(get_settings().business_name)
    css = CSS + (A4 if a4 else "")
    doc = (
        f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
        f"<div class='head'><div><h1>{biz}</h1><div class='sub'>{html.escape(title)}</div></div>"
        f"<div style='text-align:right'><b>{html.escape(number)}</b></div></div>{body}"
        "<div class='sign'><span>Receiver signature</span><span>Authorised signature</span></div></body></html>"
    )
    return HTML(string=doc).write_pdf()


def _kv(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(f"<tr><td class='k'>{html.escape(k)}</td><td>{html.escape(v or '-')}</td></tr>" for k, v in pairs)
    return f"<table class='grid'>{rows}</table>"


def _pdf(content: bytes, name: str) -> Response:
    return Response(
        content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'}
    )


def challan_pdf(db: Session, delivery_id: int) -> Response:
    d = get_or_404(db, Delivery, delivery_id, "Challan")
    customer = db.get(Party, d.customer_id)
    material = db.get(Material, d.material_id)
    site = db.get(Site, d.site_id) if d.site_id else None
    vehicle = db.get(Vehicle, d.vehicle_id) if d.vehicle_id else None
    driver = db.get(Staff, d.driver_id) if d.driver_id else None
    status = (
        "<p style='color:#b00;font-weight:bold'>VOID: " + html.escape(d.void_reason or "") + "</p>"
        if d.status == "void"
        else ""
    )
    body = (
        status
        + _kv(
            [
                ("Date", fmt_date(d.date)),
                ("Customer", customer.name),
                ("Site", site.name if site else ""),
                ("Vehicle", vehicle.name if vehicle else ""),
                ("Driver", driver.name if driver else ""),
            ]
        )  # fmt: skip
        + "<table class='items'><tr><th>Material</th><th class='r'>Qty</th><th class='r'>Rate</th><th class='r'>Amount</th></tr>"
        f"<tr><td>{html.escape(material.name)}</td><td class='r'>{fmt_qty(d.qty)} {d.unit}</td>"
        f"<td class='r'>{fmt_money(d.sale_rate)}</td><td class='r'>{fmt_money(d.sale_amount)}</td></tr>"
        + (
            f"<tr><td>Freight (bhara)</td><td></td><td></td><td class='r'>{fmt_money(d.freight_amount)}</td></tr>"
            if d.freight_amount
            else ""
        )
        + f"<tr class='tot'><td colspan='3'>Total</td><td class='r'>{fmt_money(d.sale_amount + d.freight_amount)}</td></tr></table>"
    )
    return _pdf(_page("Delivery challan", d.challan_no, body), f"{d.challan_no.replace('/', '_')}.pdf")


def invoice_pdf(db: Session, invoice_id: int) -> Response:
    inv = get_or_404(db, Invoice, invoice_id, "Invoice")
    customer = db.get(Party, inv.customer_id)
    site = db.get(Site, inv.site_id) if inv.site_id else None
    lines = invoice_service.lines_of(db, inv) if inv.status == "active" else []
    rows = "".join(
        f"<tr><td>{fmt_date(ln.date)}</td><td>{html.escape(ln.doc_no)}</td><td>{html.escape(ln.description)}</td>"
        f"<td class='r'>{fmt_qty(ln.qty)} {ln.unit}</td><td class='r'>{fmt_money(ln.rate)}</td>"
        f"<td class='r'>{fmt_money(ln.amount)}</td></tr>"
        for ln in lines
    )
    tax_rows = (
        f"<tr><td colspan='5' class='r'>Tax ({inv.tax_rate}%)</td><td class='r'>{fmt_money(inv.tax_amount)}</td></tr>"
        if inv.is_tax_invoice
        else ""
    )
    status = (
        "<p style='color:#b00;font-weight:bold'>VOID: " + html.escape(inv.void_reason or "") + "</p>"
        if inv.status == "void"
        else ""
    )
    body = (
        status
        + _kv(
            [
                ("Bill to", customer.name),
                ("Tax no.", customer.tax_no or ""),
                ("Site", site.name if site else "All sites"),
                ("Bill date", fmt_date(inv.date)),
                ("Period", f"{fmt_date(inv.period_from)} to {fmt_date(inv.period_to)}"),
            ]
        )  # fmt: skip
        + "<table class='items'><tr><th>Date</th><th>Challan</th><th>Details</th><th class='r'>Qty</th>"
        "<th class='r'>Rate</th><th class='r'>Amount</th></tr>"
        + rows
        + f"<tr><td colspan='5' class='r'>Subtotal</td><td class='r'>{fmt_money(inv.subtotal)}</td></tr>"
        + tax_rows
        + f"<tr class='tot'><td colspan='5' class='r'>Total</td><td class='r'>{fmt_money(inv.total)}</td></tr></table>"
    )
    title = "Tax invoice" if inv.is_tax_invoice else "Bill"
    return _pdf(_page(title, inv.invoice_no, body, a4=True), f"{inv.invoice_no.replace('/', '_')}.pdf")


def payment_pdf(db: Session, payment_id: int) -> Response:
    p = get_or_404(db, Payment, payment_id, "Payment")
    who = db.get(Party, p.party_id).name if p.party_id else db.get(Staff, p.staff_id).name
    account = db.get(MoneyAccount, p.money_account_id)
    title = "Receipt voucher" if p.direction == "in" else "Payment voucher"
    body = _kv([
        ("Date", fmt_date(p.date)), ("Received from" if p.direction == "in" else "Paid to", who),
        ("Amount", f"{fmt_money(p.amount)} {get_settings().currency_symbol}"), ("Mode", p.mode),
        ("Account", account.name), ("Reference", p.ref_no or ""), ("Notes", p.notes or ""),
    ])  # fmt: skip
    return _pdf(_page(title, p.voucher_no, body), f"{p.voucher_no.replace('/', '_')}.pdf")
