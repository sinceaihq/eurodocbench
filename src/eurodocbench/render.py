"""Render invoices to PDF with a real text layer (reportlab).

Five layouts cover the arrangements seen on European invoices: a classic
letterhead, a modern banded design, a compact label-value list, a bordered
grid and a narrow receipt-style document.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from decimal import Decimal
from importlib import resources

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from .document import Invoice, Party
from .formatting import format_amount, format_date, format_number, format_rate
from .identifiers import group4
from .locales import LOCALES, Locale

PAGE_W, PAGE_H = A4
MARGIN = 48

FONT_FILES = {
    "sans": ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
    "serif": ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf"),
    "mono": ("LiberationMono-Regular.ttf", "LiberationMono-Bold.ttf"),
}
_registered: set[str] = set()


def _register_fonts() -> None:
    if _registered:
        return
    base = resources.files("eurodocbench").joinpath("fonts")
    for family, (regular, bold) in FONT_FILES.items():
        for name, file in ((f"{family}", regular), (f"{family}-bold", bold)):
            with resources.as_file(base.joinpath(file)) as path:
                pdfmetrics.registerFont(TTFont(name, str(path)))
            _registered.add(name)


class Ctx:
    """Bundles the invoice, locale and style helpers for a layout."""

    def __init__(self, inv: Invoice, canvas: Canvas) -> None:
        self.inv = inv
        self.c = canvas
        self.loc: Locale = LOCALES[inv.locale]
        self.font = inv.style.font
        self.bold = f"{inv.style.font}-bold"

    def label(self, key: str) -> str:
        return self.loc.labels[key][self.inv.style.label_variant]

    def amount(self, value: Decimal, currency: bool = True) -> str:
        return format_amount(value, self.loc, self.inv.style.currency_style if currency else None)

    def date(self, value: object) -> str:
        return format_date(value, self.loc, self.inv.style.date_style)  # type: ignore[arg-type]

    def vat_id(self, value: str) -> str:
        if not self.inv.style.vat_id_spaced:
            return value
        body = value[2:]
        return value[:2] + " " + " ".join(body[i : i + 3] for i in range(0, len(body), 3))

    def iban(self) -> str:
        assert self.inv.iban
        return group4(self.inv.iban) if self.inv.style.iban_grouped else self.inv.iban

    def text(self, x: float, y: float, s: str, size: float = 9.5, bold: bool = False,
             align: str = "left", color: colors.Color = colors.black) -> None:  # fmt: skip
        self.c.setFillColor(color)
        self.c.setFont(self.bold if bold else self.font, size)
        if align == "right":
            self.c.drawRightString(x, y, s)
        elif align == "center":
            self.c.drawCentredString(x, y, s)
        else:
            self.c.drawString(x, y, s)

    def wrap(self, s: str, width: float, size: float, bold: bool = False) -> list[str]:
        lines: list[str] = simpleSplit(s, self.bold if bold else self.font, size, width)
        return lines

    def party_block(self, x: float, y: float, title: str, p: Party, width: float = 230) -> float:
        self.text(x, y, title, 8.5, bold=True, color=colors.HexColor("#555555"))
        y -= 13
        for i, line in enumerate(self.wrap(p.name, width, 10.5, bold=True)):
            self.text(x, y, line, 10.5, bold=True)
            y -= 13 if i == 0 else 12
        for line in (p.street, f"{p.postcode} {p.city}"):
            self.text(x, y, line)
            y -= 12
        if p.vat_id:
            self.text(x, y, f"{self.label('vat_id')}: {self.vat_id(p.vat_id)}")
            y -= 12
        return y

    def rate_label(self, rate: Decimal) -> str:
        return f"{self.label('vat')} {format_rate(rate, self.loc)}"


# ----------------------------------------------------------------- tables


def _items_table(ctx: Ctx, y: float, x0: float, x1: float, grid: bool = False,
                 header_fill: colors.Color | None = None) -> float:  # fmt: skip
    inv, c = ctx.inv, ctx.c
    multi = len(inv.vat_breakdown) > 1
    # Right edges of the numeric columns; each header is shrunk to fit its column.
    qty_x, unit_x, amt_x = x1 - 250, x1 - 165, x1 - 4
    vat_x = x1 - 88 if multi else None
    desc_x = x0 + 4
    if header_fill is not None:
        c.setFillColor(header_fill)
        c.rect(x0, y - 4, x1 - x0, 16, stroke=0, fill=1)
    ctx.text(desc_x, y, ctx.label("description"), 8.5, bold=True)
    edges = [(qty_x, "quantity", 60), (unit_x, "unit_price", 80)]
    if vat_x is not None:
        edges.append((vat_x, "vat", 72))
    edges.append((amt_x, "line_amount", 80 if multi else 150))
    for x, key, room in edges:
        label = ctx.label(key)
        size = 8.5
        while size > 6 and pdfmetrics.stringWidth(label, ctx.bold, size) > room - 6:
            size -= 0.25
        ctx.text(x, y, label, size, bold=True, align="right")
    c.setStrokeColor(colors.HexColor("#999999"))
    c.setLineWidth(0.6)
    c.line(x0, y - 6, x1, y - 6)
    y -= 20
    for ln in inv.lines:
        desc_lines = ctx.wrap(ln.description, qty_x - desc_x - 40, 9.5)
        ctx.text(desc_x, y, desc_lines[0])
        ctx.text(qty_x, y, format_number(ln.quantity, ctx.loc, decimals=0), align="right")
        ctx.text(unit_x, y, ctx.amount(ln.unit_price, currency=False), align="right")
        if vat_x is not None:
            ctx.text(vat_x, y, format_rate(ln.vat_rate, ctx.loc), align="right")
        ctx.text(amt_x, y, ctx.amount(ln.amount, currency=False), align="right")
        for extra in desc_lines[1:]:
            y -= 11
            ctx.text(desc_x, y, extra)
        if grid:
            c.setStrokeColor(colors.HexColor("#cccccc"))
            c.line(x0, y - 5, x1, y - 5)
        y -= 16
    c.setStrokeColor(colors.HexColor("#999999"))
    c.line(x0, y + 8, x1, y + 8)
    return y


def _totals(ctx: Ctx, y: float, x_label: float, x_value: float, size: float = 9.5) -> float:
    inv = ctx.inv
    ctx.text(x_label, y, ctx.label("net_amount"), size)
    ctx.text(x_value, y, ctx.amount(inv.net_amount), size, align="right")
    y -= size + 5
    for rate, _base, vat in inv.vat_breakdown:
        ctx.text(x_label, y, ctx.rate_label(rate), size)
        ctx.text(x_value, y, ctx.amount(vat), size, align="right")
        y -= size + 5
    ctx.c.setLineWidth(0.8)
    ctx.c.setStrokeColor(colors.black)
    ctx.c.line(x_label, y + size - 1, x_value, y + size - 1)
    y -= 4
    ctx.text(x_label, y, ctx.label("total"), size + 1.5, bold=True)
    ctx.text(x_value, y, ctx.amount(inv.total_amount), size + 1.5, bold=True, align="right")
    return y - (size + 8)


def _payment_footer(ctx: Ctx, y: float = 70) -> None:
    inv, c = ctx.inv, ctx.c
    c.setStrokeColor(colors.HexColor("#bbbbbb"))
    c.setLineWidth(0.5)
    c.line(MARGIN, y + 14, PAGE_W - MARGIN, y + 14)
    parts = [inv.seller.name, f"{inv.seller.street}, {inv.seller.postcode} {inv.seller.city}"]
    ctx.text(MARGIN, y, " · ".join(parts), 8, color=colors.HexColor("#444444"))
    if inv.iban:
        ctx.text(
            MARGIN,
            y - 12,
            f"{ctx.label('iban')}: {ctx.iban()}",
            8,
            color=colors.HexColor("#444444"),
        )


# ----------------------------------------------------------------- layouts


def _classic(ctx: Ctx) -> None:
    inv = ctx.inv
    top = PAGE_H - MARGIN
    y = top
    for _i, line in enumerate(ctx.wrap(inv.seller.name, 270, 14, bold=True)):
        ctx.text(MARGIN, y, line, 14, bold=True)
        y -= 16
    for line in (inv.seller.street, f"{inv.seller.postcode} {inv.seller.city}"):
        ctx.text(MARGIN, y, line)
        y -= 12
    ctx.text(MARGIN, y, f"{ctx.label('vat_id')}: {ctx.vat_id(inv.seller.vat_id or '')}")

    ctx.text(PAGE_W - MARGIN, top - 4, ctx.label("title"), 22, bold=True, align="right")
    my = top - 34
    meta = [("invoice_number", inv.invoice_number), ("issue_date", ctx.date(inv.issue_date))]
    if inv.due_date:
        meta.append(("due_date", ctx.date(inv.due_date)))
    for key, value in meta:
        ctx.text(PAGE_W - MARGIN - 120, my, f"{ctx.label(key)}:", 9, align="right")
        ctx.text(PAGE_W - MARGIN, my, value, 9.5, bold=True, align="right")
        my -= 13

    y = ctx.party_block(MARGIN, top - 130, ctx.label("buyer"), inv.buyer)
    y = _items_table(ctx, min(y, top - 215) - 20, MARGIN, PAGE_W - MARGIN)
    _totals(ctx, y - 10, PAGE_W - MARGIN - 210, PAGE_W - MARGIN)
    _payment_footer(ctx)


def _modern(ctx: Ctx) -> None:
    inv, c = ctx.inv, ctx.c
    band = colors.HexColor("#1f3a5f")
    c.setFillColor(band)
    c.rect(0, PAGE_H - 92, PAGE_W, 92, stroke=0, fill=1)
    ctx.text(MARGIN, PAGE_H - 58, ctx.label("title"), 26, bold=True, color=colors.white)
    ctx.text(PAGE_W - MARGIN, PAGE_H - 50, inv.seller.name, 12, bold=True, align="right",
             color=colors.white)  # fmt: skip
    ctx.text(PAGE_W - MARGIN, PAGE_H - 66, f"{inv.seller.city}", 9.5, align="right",
             color=colors.HexColor("#d6e2f0"))  # fmt: skip

    # Meta boxes in a row.
    meta = [("invoice_number", inv.invoice_number), ("issue_date", ctx.date(inv.issue_date))]
    if inv.due_date:
        meta.append(("due_date", ctx.date(inv.due_date)))
    box_w = (PAGE_W - 2 * MARGIN - 20) / 3
    for i, (key, value) in enumerate(meta):
        x = MARGIN + i * (box_w + 10)
        c.setFillColor(colors.HexColor("#eef2f7"))
        c.rect(x, PAGE_H - 150, box_w, 40, stroke=0, fill=1)
        ctx.text(
            x + 8,
            PAGE_H - 125,
            ctx.label(key).upper(),
            7.5,
            bold=True,
            color=colors.HexColor("#4a5a70"),
        )
        ctx.text(x + 8, PAGE_H - 141, value, 10.5, bold=True)

    y1 = ctx.party_block(MARGIN, PAGE_H - 180, ctx.label("seller"), inv.seller)
    y2 = ctx.party_block(PAGE_W / 2 + 10, PAGE_H - 180, ctx.label("buyer"), inv.buyer)
    y = _items_table(ctx, min(y1, y2) - 25, MARGIN, PAGE_W - MARGIN,
                     header_fill=colors.HexColor("#eef2f7"))  # fmt: skip
    box_top = y - 4
    c.setFillColor(colors.HexColor("#f5f7fa"))
    n_rows = 2 + len(inv.vat_breakdown)
    c.rect(
        PAGE_W - MARGIN - 230, box_top - n_rows * 15 - 12, 230, n_rows * 15 + 16, stroke=0, fill=1
    )
    _totals(ctx, box_top - 8, PAGE_W - MARGIN - 220, PAGE_W - MARGIN - 10)
    _payment_footer(ctx)


def _compact(ctx: Ctx) -> None:
    inv = ctx.inv
    y = PAGE_H - MARGIN
    ctx.text(MARGIN, y, f"{ctx.label('title')} {inv.invoice_number}", 16, bold=True)
    y -= 26
    rows: list[tuple[str, str]] = [
        (ctx.label("invoice_number"), inv.invoice_number),
        (ctx.label("issue_date"), ctx.date(inv.issue_date)),
    ]
    if inv.due_date:
        rows.append((ctx.label("due_date"), ctx.date(inv.due_date)))
    rows += [
        (
            ctx.label("seller"),
            f"{inv.seller.name}, {inv.seller.street}, {inv.seller.postcode} {inv.seller.city}",
        ),
        (f"{ctx.label('seller')} – {ctx.label('vat_id')}", ctx.vat_id(inv.seller.vat_id or "")),
        (
            ctx.label("buyer"),
            f"{inv.buyer.name}, {inv.buyer.street}, {inv.buyer.postcode} {inv.buyer.city}",
        ),
    ]
    if inv.buyer.vat_id:
        rows.append((f"{ctx.label('buyer')} – {ctx.label('vat_id')}", ctx.vat_id(inv.buyer.vat_id)))
    if inv.iban:
        rows.append((ctx.label("iban"), ctx.iban()))
    for label, value in rows:
        ctx.text(MARGIN, y, f"{label}:", 9.5, bold=True)
        for i, line in enumerate(ctx.wrap(value, PAGE_W - 2 * MARGIN - 170, 9.5)):
            if i:
                y -= 12
            ctx.text(MARGIN + 170, y, line)
        y -= 14
    y -= 10
    for ln in inv.lines:
        qty = format_number(ln.quantity, ctx.loc, decimals=0)
        ctx.text(
            MARGIN, y, f"{qty} × {ln.description} à {ctx.amount(ln.unit_price, currency=False)}"
        )
        ctx.text(PAGE_W - MARGIN, y, ctx.amount(ln.amount, currency=False), align="right")
        y -= 14
    y -= 10
    _totals(ctx, y, PAGE_W - MARGIN - 220, PAGE_W - MARGIN)


def _grid(ctx: Ctx) -> None:
    inv, c = ctx.inv, ctx.c
    y = PAGE_H - MARGIN
    ctx.text(MARGIN, y, ctx.label("title"), 20, bold=True)
    ctx.text(PAGE_W - MARGIN, y, inv.seller.name, 11, bold=True, align="right")
    y -= 30
    cells = [("invoice_number", inv.invoice_number), ("issue_date", ctx.date(inv.issue_date)),
             ("due_date", ctx.date(inv.due_date) if inv.due_date else "–")]  # fmt: skip
    if inv.iban:
        cells.append(("iban", ctx.iban()))
    col_w = (PAGE_W - 2 * MARGIN) / 2
    c.setStrokeColor(colors.HexColor("#888888"))
    c.setLineWidth(0.6)
    for i, (key, value) in enumerate(cells):
        x = MARGIN + (i % 2) * col_w
        yy = y - (i // 2) * 34
        c.rect(x, yy - 26, col_w, 34, stroke=1, fill=0)
        ctx.text(x + 6, yy - 4, ctx.label(key), 7.5, color=colors.HexColor("#555555"))
        ctx.text(x + 6, yy - 18, value, 10, bold=True)
    y -= ((len(cells) + 1) // 2) * 34 + 30
    y1 = ctx.party_block(MARGIN + 4, y, ctx.label("seller"), inv.seller)
    y2 = ctx.party_block(PAGE_W / 2 + 4, y, ctx.label("buyer"), inv.buyer)
    y = _items_table(ctx, min(y1, y2) - 25, MARGIN, PAGE_W - MARGIN, grid=True)
    _totals(ctx, y - 6, PAGE_W - MARGIN - 210, PAGE_W - MARGIN)


def _narrow(ctx: Ctx) -> None:
    inv = ctx.inv
    w = 300
    x0 = (PAGE_W - w) / 2
    x1 = x0 + w
    y = PAGE_H - MARGIN
    rule = "-" * 58
    for line in ctx.wrap(inv.seller.name, w, 11, bold=True):
        ctx.text(PAGE_W / 2, y, line, 11, bold=True, align="center")
        y -= 13
    for line in (inv.seller.street, f"{inv.seller.postcode} {inv.seller.city}",
                 f"{ctx.label('vat_id')} {ctx.vat_id(inv.seller.vat_id or '')}"):  # fmt: skip
        ctx.text(PAGE_W / 2, y, line, 8.5, align="center")
        y -= 11
    y -= 6
    ctx.text(PAGE_W / 2, y, ctx.label("title"), 12, bold=True, align="center")
    y -= 16
    meta = (
        ("invoice_number", inv.invoice_number),
        ("issue_date", ctx.date(inv.issue_date)),
        ("due_date", ctx.date(inv.due_date) if inv.due_date else None),
    )
    for key, value in meta:
        if value:
            ctx.text(x0, y, ctx.label(key), 8.5)
            ctx.text(x1, y, value, 8.5, align="right")
            y -= 11
    ctx.text(x0, y, rule, 8.5)
    y -= 12
    ctx.text(x0, y, f"{ctx.label('buyer')}: {inv.buyer.name}", 8.5)
    y -= 11
    if inv.buyer.vat_id:
        ctx.text(x0, y, f"{ctx.label('vat_id')} {ctx.vat_id(inv.buyer.vat_id)}", 8.5)
        y -= 11
    ctx.text(x0, y, rule, 8.5)
    y -= 12
    for ln in inv.lines:
        for line in ctx.wrap(ln.description, w, 8.5):
            ctx.text(x0, y, line, 8.5)
            y -= 11
        qty = format_number(ln.quantity, ctx.loc, decimals=0)
        ctx.text(x0 + 10, y, f"{qty} x {ctx.amount(ln.unit_price, currency=False)}", 8.5)
        ctx.text(x1, y, ctx.amount(ln.amount, currency=False), 8.5, align="right")
        y -= 13
    ctx.text(x0, y, rule, 8.5)
    y -= 13
    y = _totals(ctx, y, x0, x1, size=8.5)
    if inv.iban:
        ctx.text(PAGE_W / 2, y - 6, f"{ctx.label('iban')} {ctx.iban()}", 8, align="center")


LAYOUT_FUNCS: dict[str, Callable[[Ctx], None]] = {
    "classic": _classic,
    "modern": _modern,
    "compact": _compact,
    "grid": _grid,
    "narrow": _narrow,
}


def render_pdf(inv: Invoice) -> bytes:
    """Render one invoice to PDF bytes. Output is deterministic."""
    _register_fonts()
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4, invariant=1, pageCompression=1)
    # Generic metadata only: the ground truth must not leak into the file.
    c.setTitle("Invoice")
    c.setAuthor("EuroDocBench synthetic document")
    c.setCreator("EuroDocBench")
    c.setSubject("")
    LAYOUT_FUNCS[inv.style.layout](Ctx(inv, c))
    c.showPage()
    c.save()
    return buf.getvalue()
