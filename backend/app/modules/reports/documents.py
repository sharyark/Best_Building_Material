"""Printable documents: challan, invoice/bill, payment voucher (HTML -> PDF).

Challans and vouchers also print on thermal receipt printers (80mm / 58mm rolls): one narrow column, black only,
and a page exactly as long as the content so no paper is wasted.
"""

import html
from typing import Literal

from fastapi import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.common import get_or_404
from app.modules.deliveries.models import Delivery
from app.modules.invoices import service as invoice_service
from app.modules.invoices.models import Invoice
from app.modules.masters.models import Material, MoneyAccount, Party, Site, Staff, Vehicle
from app.modules.payments.models import Payment
from app.modules.reports.table import fmt_date, fmt_money, fmt_qty

CSS = """
@page { size: A5 landscape; margin: 10mm 12mm; }
body { font-family: DejaVu Sans, Arial, sans-serif; font-size: 10pt; color: #111; }
h1 { font-size: 16pt; margin: 0; } .sub { color: #555; margin-bottom: 8px; }
.head { display: flex; justify-content: space-between; border-bottom: 2px solid #1f4e79; padding-bottom: 6px; margin-bottom: 12px; }
.grid { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
.grid td { padding: 3px 8px 3px 0; vertical-align: top; } .k { color: #666; width: 22%; }
table.items { width: 100%; border-collapse: collapse; }
table.items th { background: #1f4e79; color: #fff; padding: 5px 8px; text-align: left; }
table.items td { padding: 5px 8px; border-bottom: 1px solid #ddd; vertical-align: top; }
table.items .r { text-align: right; white-space: nowrap; }
table.items .n { white-space: nowrap; }
.tot td { font-weight: bold; border-top: 2px solid #333; }
.sign { margin-top: 32px; display: flex; justify-content: space-between; color: #555; }
"""
A4 = "@page { size: A4; margin: 14mm 14mm 16mm; } body { font-size: 9pt; }"


def _page(title: str, number: str, body: str, *, a4: bool = False) -> bytes:
    biz = html.escape(get_settings().business_name)
    css = CSS + (A4 if a4 else "")
    doc = (
        f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>"
        f"<div class='head'><div><h1>{biz}</h1><div class='sub'>{html.escape(title)}</div></div>"
        f"<div style='text-align:right'><b>{html.escape(number)}</b></div></div>{body}"
        "<div class='sign'><span>Receiver signature</span><span>Authorised signature</span></div></body></html>"
    )
    # Imported here so the API still starts where WeasyPrint's native libs are missing (e.g. Windows without GTK).
    from weasyprint import HTML

    return HTML(string=doc).write_pdf()


Paper = Literal["a5", "80mm", "58mm"]

# Printable width, font size (pt) and side margin for each roll: 80mm printers print ~72mm, 58mm ones ~48mm.
THERMAL = {"80mm": (80, 10, 4), "58mm": (58, 8.5, 3)}

THERMAL_CSS = """
@page { size: %(w)smm %(h)s; margin: 3mm %(m)smm 8mm %(m)smm; }
body { font-family: DejaVu Sans, Arial, sans-serif; font-size: %(f)spt; color: #000; margin: 0; line-height: 1.3; }
.c { text-align: center; } .biz { font-size: 1.35em; font-weight: bold; }
.title { font-weight: bold; margin-top: 2px; } .no { font-size: 1.1em; font-weight: bold; }
hr { border: 0; border-top: 1px dashed #000; margin: 5px 0; }
table { width: 100%%; border-collapse: collapse; } td { padding: 1px 0; vertical-align: top; }
.k { width: 38%%; } .r { text-align: right; white-space: nowrap; }
.item { font-weight: bold; } .calc td { padding-bottom: 3px; }
.total td { font-size: 1.3em; font-weight: bold; padding-top: 3px; }
.void { font-weight: bold; text-align: center; border: 2px solid #000; padding: 3px; margin: 4px 0; }
.sign { margin-top: 18px; border-top: 1px solid #000; padding-top: 2px; text-align: center; }
"""


def _thermal(paper: str, title: str, number: str, body: str, *, void_reason: str | None = None) -> bytes:
    """One narrow receipt. Rendered twice: once on a very tall page to measure, then cut to the content."""
    from weasyprint import HTML

    width, font, margin = THERMAL[paper]
    biz = html.escape(get_settings().business_name)
    void = f"<div class='void'>VOID: {html.escape(void_reason or '')}</div>" if void_reason is not None else ""
    content = (
        f"<div class='c'><div class='biz'>{biz}</div><div class='title'>{html.escape(title)}</div>"
        f"<div class='no'>{html.escape(number)}</div></div>{void}<hr>{body}"
    )

    def render(height: str):
        css = THERMAL_CSS % {"w": width, "h": height, "m": margin, "f": font}
        return HTML(
            string=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{content}</body></html>"
        )

    tall = render("2000mm").render()
    content_px = tall.pages[0]._page_box.children[0].margin_height()
    # CSS px are 1/96 inch; add the 3mm top + 8mm bottom page margins (bottom leaves room for the cutter).
    height_mm = content_px * 25.4 / 96 + 11 + 1
    return render(f"{height_mm:.1f}mm").write_pdf()


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "".join(f"<tr><td class='k'>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in pairs if v)


def _kv(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(f"<tr><td class='k'>{html.escape(k)}</td><td>{html.escape(v or '-')}</td></tr>" for k, v in pairs)
    return f"<table class='grid'>{rows}</table>"


def _pdf(content: bytes, name: str) -> Response:
    return Response(
        content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'}
    )


def challan_pdf(db: Session, delivery_id: int, paper: Paper = "a5") -> Response:
    d = get_or_404(db, Delivery, delivery_id, "Challan")
    customer = db.get(Party, d.customer_id)
    material = db.get(Material, d.material_id)
    extra = db.get(Material, d.extra_material_id) if d.extra_material_id else None
    site = db.get(Site, d.site_id) if d.site_id else None
    vehicle = db.get(Vehicle, d.vehicle_id) if d.vehicle_id else None
    driver = db.get(Staff, d.driver_id) if d.driver_id else None
    name = f"{d.challan_no.replace('/', '_')}.pdf"
    if paper != "a5":
        return _pdf(_challan_thermal(db, d, paper, customer, material, extra, site, vehicle, driver), name)
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
        f"<tr><td>{html.escape(material.name)}{' (half load)' if d.load_size == 'half' else ''}</td><td class='r'>{fmt_qty(d.qty)} {d.unit}</td>"
        f"<td class='r'>{fmt_money(d.sale_rate)}</td><td class='r'>{fmt_money(d.sale_amount)}</td></tr>"
        + (
            f"<tr><td>{html.escape(extra.name)}</td><td class='r'>{fmt_qty(d.extra_qty)} {d.extra_unit}</td>"
            f"<td class='r'>{fmt_money(d.extra_rate)}</td><td class='r'>{fmt_money(d.extra_amount)}</td></tr>"
            if extra
            else ""
        )
        + (
            f"<tr><td>Freight (bhara)</td><td></td><td></td><td class='r'>{fmt_money(d.freight_amount)}</td></tr>"
            if d.freight_amount
            else ""
        )
        + f"<tr class='tot'><td colspan='3'>Total</td><td class='r'>{fmt_money(d.sale_amount + d.freight_amount + d.extra_amount)}</td></tr></table>"
    )
    return _pdf(_page("Delivery challan", d.challan_no, body), name)


def _challan_thermal(db: Session, d: Delivery, paper: str, customer, material, extra, site, vehicle, driver) -> bytes:
    cur = get_settings().currency_symbol

    def item(label: str, qty_text: str, rate, amount) -> str:
        return (
            f"<tr><td colspan='2' class='item'>{html.escape(label)}</td></tr>"
            f"<tr class='calc'><td>{html.escape(qty_text)} x {fmt_money(rate)}</td><td class='r'>{fmt_money(amount)}</td></tr>"
        )

    lines = item(
        material.name + (" (half load)" if d.load_size == "half" else ""),
        f"{fmt_qty(d.qty)} {d.unit}",
        d.sale_rate,
        d.sale_amount,
    )
    if extra:
        lines += item(extra.name, f"{fmt_qty(d.extra_qty)} {d.extra_unit}", d.extra_rate, d.extra_amount)
    if d.freight_amount:
        lines += f"<tr><td>Freight (bhara)</td><td class='r'>{fmt_money(d.freight_amount)}</td></tr>"
    total = d.sale_amount + d.freight_amount + d.extra_amount
    paid = db.get(Payment, d.receipt_id) if d.receipt_id else None
    paid_rows = (
        f"<tr><td>Paid now</td><td class='r'>{fmt_money(paid.amount)}</td></tr>"
        f"<tr><td>Balance (udhaar)</td><td class='r'>{fmt_money(total - paid.amount)}</td></tr>"
        if paid and paid.status == "active"
        else ""
    )
    body = (
        "<table>"
        + _rows(
            [
                ("Date", fmt_date(d.date)),
                ("Customer", customer.name),
                ("Site", site.name if site else ""),
                ("Vehicle", vehicle.name if vehicle else ""),
                ("Driver", driver.name if driver else ""),
            ]
        )  # fmt: skip
        + "</table><hr><table>"
        + lines
        + f"</table><hr><table><tr class='total'><td>TOTAL {cur}</td><td class='r'>{fmt_money(total)}</td></tr>"
        + paid_rows
        + "</table>"
        + (f"<hr><div>{html.escape(d.notes)}</div>" if d.notes else "")
        + "<div class='sign'>Receiver signature</div>"
    )
    return _thermal(
        paper, "Delivery challan", d.challan_no, body, void_reason=d.void_reason if d.status == "void" else None
    )


def invoice_pdf(db: Session, invoice_id: int) -> Response:
    inv = get_or_404(db, Invoice, invoice_id, "Invoice")
    customer = db.get(Party, inv.customer_id)
    site = db.get(Site, inv.site_id) if inv.site_id else None
    lines = invoice_service.lines_of(db, inv) if inv.status == "active" else []
    rows = "".join(
        f"<tr><td class='n'>{fmt_date(ln.date)}</td><td class='n'>{html.escape(ln.doc_no)}</td><td>{html.escape(ln.description)}</td>"
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


def payment_pdf(db: Session, payment_id: int, paper: Paper = "a5") -> Response:
    p = get_or_404(db, Payment, payment_id, "Payment")
    who = db.get(Party, p.party_id).name if p.party_id else db.get(Staff, p.staff_id).name
    account = db.get(MoneyAccount, p.money_account_id)
    title = "Receipt voucher" if p.direction == "in" else "Payment voucher"
    name = f"{p.voucher_no.replace('/', '_')}.pdf"
    # Salary and trip money paid together: show both parts so the worker sees what each was for.
    split = (
        [("Salary", fmt_money(p.amount - p.trip_amount)), ("Trip money", fmt_money(p.trip_amount))]
        if p.purpose == "sal_trip"
        else []
    )
    if paper != "a5":
        cur = get_settings().currency_symbol
        body = (
            "<table>"
            + _rows(
                [
                    ("Date", fmt_date(p.date)),
                    ("Received from" if p.direction == "in" else "Paid to", who),
                    ("Mode", p.mode),
                    ("Account", account.name),
                    ("Reference", p.ref_no or ""),
                    *split,
                ]
            )  # fmt: skip
            + f"</table><hr><table><tr class='total'><td>AMOUNT {cur}</td><td class='r'>{fmt_money(p.amount)}</td></tr></table>"
            + (f"<hr><div>{html.escape(p.notes)}</div>" if p.notes else "")
            + f"<div class='sign'>{'Received by' if p.direction == 'out' else 'Authorised signature'}</div>"
        )
        void = p.void_reason if p.status == "void" else None
        return _pdf(_thermal(paper, title, p.voucher_no, body, void_reason=void), name)
    body = _kv([
        ("Date", fmt_date(p.date)), ("Received from" if p.direction == "in" else "Paid to", who),
        ("Amount", f"{fmt_money(p.amount)} {get_settings().currency_symbol}"), *split, ("Mode", p.mode),
        ("Account", account.name), ("Reference", p.ref_no or ""), ("Notes", p.notes or ""),
    ])  # fmt: skip
    return _pdf(_page(title, p.voucher_no, body), name)
