"""Keyword-and-regex extraction baseline for European invoices.

Works on plain text (a PDF text layer or OCR output). The keyword lists are
written independently of the generator: they contain the usual invoice
vocabulary of the 12 benchmark languages, including many words the generator
never uses, so the baseline is a realistic rule-based system rather than one
that knows the templates.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

# --------------------------------------------------------------- vocabulary

INVOICE_NO = ("invoice no", "invoice number", "invoice #", "laskun numero", "laskunro",
              "lasku nro", "fakturanummer", "fakturanr", "rechnungsnummer", "rechnungs-nr",
              "rechnung nr", "numéro de facture", "facture n", "n° de facture", "factuurnummer",
              "factuurnr", "numero fattura", "fattura n", "número de factura", "factura n",
              "nº factura", "numer faktury", "nr faktury", "número da fatura", "fatura n",
              "číslo faktury", "faktura č", "číslo dokladu", "invoice ref")  # fmt: skip
ISSUE_DATE = ("invoice date", "date of issue", "issue date", "date", "laskun päivämäärä",
              "päiväys", "päivämäärä", "fakturadatum", "datum", "rechnungsdatum",
              "date de facture", "date d'émission", "factuurdatum", "data fattura",
              "data di emissione", "fecha de factura", "fecha de emisión", "fecha",
              "data wystawienia", "data faktury", "data da fatura", "data de emissão",
              "datum vystavení", "vystaveno", "fakturadato", "dato")  # fmt: skip
DUE_DATE = ("due date", "payment due", "due", "eräpäivä", "erääntyy", "förfallodatum",
            "förfaller", "fälligkeitsdatum", "fällig", "zahlbar bis", "date d'échéance",
            "échéance", "vervaldatum", "te betalen vóór", "te betalen voor", "data di scadenza",
            "scadenza", "fecha de vencimiento", "vencimiento", "termin płatności",
            "termin zapłaty", "data de vencimento", "vencimento", "datum splatnosti", "splatnost",
            "forfaldsdato", "betalingsfrist", "betales senest")  # fmt: skip
NET = ("subtotal", "net amount", "net total", "total excl", "veroton", "netto", "summa exkl",
       "nettobetrag", "zwischensumme", "total ht", "montant hors taxes", "subtotaal",
       "totaal excl", "imponibile", "base imponible", "razem netto", "wartość netto razem",
       "total sem iva", "valor líquido", "základ daně", "celkem bez dph", "beløb ekskl",
       "ekskl. moms")  # fmt: skip
VAT_WORDS = ("vat", "alv", "arvonlisävero", "moms", "mervärdesskatt", "mwst", "ust",
             "umsatzsteuer", "tva", "btw", "iva", "imposta", "dph", "kwota vat")  # fmt: skip
TOTAL = ("amount due", "total due", "grand total", "total", "maksettava", "yhteensä",
         "att betala", "totalt", "gesamtbetrag", "rechnungsbetrag", "endbetrag", "total ttc",
         "net à payer", "totaal incl", "te betalen", "totale fattura", "totale da pagare",
         "total factura", "total a pagar", "do zapłaty", "razem brutto", "total com iva",
         "celkem k úhradě", "k úhradě", "i alt at betale", "i alt")  # fmt: skip
BUYER = ("bill to", "billed to", "customer", "client", "buyer", "ostaja", "asiakas", "köpare",
         "kund", "kunde", "rechnungsempfänger", "facturé à", "klant", "factuuradres",
         "cliente", "cessionario", "facturar a", "nabywca", "odbiorca", "adquirente",
         "odběratel", "kupující", "faktureres til")  # fmt: skip
LEGAL_FORMS = ("oy", "oyj", "ay", "ab", "hb", "gmbh", "ag", "kg", "sas", "sarl", "sa", "b.v.",
               "n.v.", "s.r.l.", "s.p.a.", "s.l.", "s.a.", "sp. z o.o.", "lda.", "s.r.o.",
               "a.s.", "aps", "a/s", "ltd", "dac", "plc", "bv", "nv", "srl", "spa")  # fmt: skip
CURRENCY_SYMBOLS = {"€": "EUR", "zł": "PLN", "kč": "CZK"}
ISO_CURRENCIES = ("EUR", "SEK", "DKK", "PLN", "CZK", "NOK", "HUF", "RON", "BGN", "CHF", "GBP")
MONTHS: dict[str, int] = {}
for _names in (
    "january february march april may june july august september october november december",
    "tammikuuta helmikuuta maaliskuuta huhtikuuta toukokuuta kesäkuuta heinäkuuta elokuuta "
    "syyskuuta lokakuuta marraskuuta joulukuuta",
    "januari februari mars april maj juni juli augusti september oktober november december",
    "januar februar märz april mai juni juli august september oktober november dezember",
    "janvier février mars avril mai juin juillet août septembre octobre novembre décembre",
    "januari februari maart april mei juni juli augustus september oktober november december",
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
    "stycznia lutego marca kwietnia maja czerwca lipca sierpnia września października listopada grudnia",
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro",
    "ledna února března dubna května června července srpna září října listopadu prosince",
    "januar februar marts april maj juni juli august september oktober november december",
):
    for _i, _m in enumerate(_names.split(), 1):
        MONTHS.setdefault(_m, _i)

# --------------------------------------------------------------- patterns

SPACE = "[   ]"
# Grouped ("1.234,56", "1 234,56", "1,234.56") or ungrouped ("1234,56") amounts.
AMOUNT_RE = re.compile(
    rf"(?<![\d.,])-?(?:\d{{1,3}}(?:(?:[.,']|{SPACE})\d{{3}})+|\d+)[.,]\d{{2}}(?![\d])"
)
NUM_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s?[./-]\s?(\d{1,2})\s?[./-]\s?(\d{4})(?!\d)")
ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
LONG_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\.?\s+(?:de\s+)?([^\W\d_]+)\s+(?:de\s+)?(\d{4})")
# Country code, then a mostly numeric body: an optional leading letter (ES),
# 7-12 digits possibly grouped by spaces, and an optional suffix (NL "B01",
# IE check letters).
VAT_RE = re.compile(
    r"(?<![A-Za-z0-9])(FI|SE|DE|FR|NL|IT|ES|PL|PT|CZ|DK|IE|AT|BE|EE|LV|LT|SK|SI|HU|RO|BG|HR"
    r"|LU|MT|CY|EL)[  ]?([A-Z]?\d(?:[  ]?\d){6,11}(?:[  ]?B\d{2}|[A-Z]{1,2})?)(?![A-Za-z0-9])"
)
TITLE_WORDS = ("invoice", "tax invoice", "lasku", "faktura", "faktura vat", "rechnung",
               "facture", "factuur", "fattura", "factura", "fatura",
               "faktura – daňový doklad")  # fmt: skip
IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}(?:[  ]?[A-Z0-9]{1,4}){3,8})\b")
PERCENT_RE = re.compile(r"\d{1,2}(?:[.,]\d)?\s?%")


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


def _has(line: str, words: tuple[str, ...]) -> bool:
    low = _norm(line)
    return any(re.search(rf"(?<![^\W\d_]){re.escape(w)}(?![^\W\d_])", low) for w in words)


def parse_amount(token: str) -> Decimal | None:
    t = re.sub(SPACE, "", token).replace("'", "")
    # The last separator followed by exactly two digits is the decimal mark.
    m = re.match(r"^(-?[\d.,]*?)[.,](\d{2})$", t)
    if not m:
        return None
    whole = re.sub(r"[.,]", "", m.group(1))
    try:
        return Decimal(f"{whole or 0}.{m.group(2)}")
    except InvalidOperation:
        return None


def amounts_in(line: str) -> list[Decimal]:
    cleaned = PERCENT_RE.sub(" ", line)
    out = []
    for m in AMOUNT_RE.finditer(cleaned):
        value = parse_amount(m.group(0))
        if value is not None:
            out.append(value)
    return out


def dates_in(line: str) -> list[dt.date]:
    found: list[tuple[int, dt.date]] = []
    for m in ISO_DATE_RE.finditer(line):
        with contextlib.suppress(ValueError):
            found.append((m.start(), dt.date(int(m[1]), int(m[2]), int(m[3]))))
    for m in NUM_DATE_RE.finditer(line):
        # Day first everywhere in the EU.
        with contextlib.suppress(ValueError):
            found.append((m.start(), dt.date(int(m[3]), int(m[2]), int(m[1]))))
    for m in LONG_DATE_RE.finditer(line):
        month = MONTHS.get(_norm(m[2]))
        if month:
            with contextlib.suppress(ValueError):
                found.append((m.start(), dt.date(int(m[3]), month, int(m[1]))))
    return [d for _, d in sorted(found, key=lambda x: x[0])]


def _value_after(lines: list[str], i: int, words: tuple[str, ...]) -> str:
    """Text after the keyword on the same line, or the next line."""
    line = lines[i]
    low = _norm(line)
    for w in sorted(words, key=len, reverse=True):
        j = low.find(w)
        if j >= 0:
            rest = line[j + len(w) :].lstrip(" .:#°º-")
            if rest.strip():
                return rest.strip()
            break
    return lines[i + 1].strip() if i + 1 < len(lines) else ""


def _first_date_near(
    lines: list[str], words: tuple[str, ...], exclude: tuple[str, ...] = ()
) -> dt.date | None:
    for i, line in enumerate(lines):
        if _has(line, words) and not (exclude and _has(line, exclude)):
            ds = dates_in(_value_after(lines, i, words)) or dates_in(line)
            if not ds and i + 1 < len(lines):
                ds = dates_in(lines[i + 1])
            if ds:
                return ds[0]
    return None


def _after_colon(line: str) -> str:
    """Value part of a "Label: value" line."""
    return line.split(":", 1)[1].strip() if ":" in line else line


def _strip_title(line: str) -> str:
    low = _norm(line)
    for w in sorted(TITLE_WORDS, key=len, reverse=True):
        if low.startswith(w + " "):
            return line[len(w) :].strip()
    return line


def _is_company(line: str) -> bool:
    line = line.split(",")[0]  # "Name Oy, Street 1, 00100 City"
    low = _norm(line).rstrip(" ,")
    return any(low.endswith(" " + f) for f in LEGAL_FORMS) and len(line) < 80


def extract(text: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: dict[str, Any] = dict.fromkeys(("invoice_number", "issue_date", "due_date", "currency", "seller_name", "seller_vat_id", "buyer_name", "buyer_vat_id", "iban", "net_amount", "vat_amount", "total_amount"))  # fmt: skip

    for i, line in enumerate(lines):
        if _has(line, INVOICE_NO):
            value = _value_after(lines, i, INVOICE_NO)
            token = value.split()[0] if value.split() else ""
            if re.search(r"\d", token):
                out["invoice_number"] = token.rstrip(".,;")
                break

    due = _first_date_near(lines, DUE_DATE)
    issue = _first_date_near(lines, ISSUE_DATE, exclude=DUE_DATE)
    if issue is None:
        all_dates = [d for ln in lines for d in dates_in(ln)]
        issue = min(all_dates) if all_dates else None
    out["issue_date"] = issue.isoformat() if issue else None
    out["due_date"] = due.isoformat() if due and due != issue else None

    vat_ids: list[str] = []
    for line in lines:
        for m in VAT_RE.finditer(line):
            candidate = m[1] + re.sub(r"[  ]", "", m[2])
            if IBAN_RE.fullmatch(re.sub(r"[  ]", "", m[0])) and len(candidate) > 14:
                continue  # an IBAN, not a VAT number
            if candidate not in vat_ids:
                vat_ids.append(candidate)
    ibans = [re.sub(r"[  ]", "", m[1]) for ln in lines for m in IBAN_RE.finditer(ln)]
    ibans = [x for x in ibans if 15 <= len(x) <= 34]
    out["iban"] = ibans[0] if ibans else None
    # Drop VAT-looking prefixes of an IBAN ("FR46 1886 2064 ...").
    vat_ids = [v for v in vat_ids if not any(x.startswith(v) for x in ibans)]

    companies = [
        (i, _strip_title(_after_colon(ln).split(",")[0].strip()))
        for i, ln in enumerate(lines)
        if _is_company(_after_colon(ln))
    ]
    buyer_idx = next((i for i, ln in enumerate(lines) if _has(ln, BUYER)), None)
    buyer = None
    if buyer_idx is not None:
        same_line = re.sub(r"^.*?[:]\s*", "", lines[buyer_idx]) if ":" in lines[buyer_idx] else ""
        if same_line and _is_company(same_line.split(",")[0]):
            buyer = same_line.split(",")[0].strip()
        else:
            buyer = next((ln for i, ln in companies if i > buyer_idx), None)
    seller = next((ln.split(",")[0].strip() for _, ln in companies if ln != buyer), None)
    out["seller_name"] = seller
    out["buyer_name"] = buyer
    if vat_ids:
        out["seller_vat_id"] = vat_ids[0]
        if len(vat_ids) > 1:
            out["buyer_vat_id"] = vat_ids[1]

    text_all = "\n".join(lines)
    iso = [code for code in ISO_CURRENCIES if re.search(rf"\b{code}\b", text_all)]
    if iso:
        out["currency"] = iso[0]
    else:
        for line in lines:
            low = _norm(line)
            code = next(
                (c for sym, c in CURRENCY_SYMBOLS.items() if sym in low and amounts_in(line)), None
            )
            if code:
                out["currency"] = code
                break
        if out["currency"] is None and re.search(r"\d\s?kr\.?(?!\w)", _norm(text_all)):
            country = (out["seller_vat_id"] or "")[:2]
            out["currency"] = "DKK" if country == "DK" else "SEK"

    def last_amount(words: tuple[str, ...], exclude: tuple[str, ...] = ()) -> Decimal | None:
        value = None
        for line in lines:
            if _has(line, words) and not (exclude and _has(line, exclude)):
                found = amounts_in(line)
                if found:
                    value = found[-1]
        return value

    def is_vat_line(ln: str) -> bool:
        return (_has(ln, VAT_WORDS) and bool(PERCENT_RE.search(ln)) and bool(amounts_in(ln))
                and not _has(ln, NET))  # fmt: skip

    net = last_amount(NET)
    total = None
    for ln in lines:  # last total-like line that is neither a net nor a VAT line
        if _has(ln, TOTAL) and not _has(ln, NET) and not is_vat_line(ln) and amounts_in(ln):
            total = amounts_in(ln)[-1]
    vat_lines = [ln for ln in lines if is_vat_line(ln)]
    vat = sum((amounts_in(ln)[-1] for ln in vat_lines), Decimal(0)) if vat_lines else None
    if net is not None and total is not None and vat is None:
        vat = total - net
    if net is None and total is not None and vat is not None:
        net = total - vat
    if total is None and net is not None and vat is not None:
        total = net + vat
    out["net_amount"] = f"{net:.2f}" if net is not None else None
    out["vat_amount"] = f"{vat:.2f}" if vat is not None else None
    out["total_amount"] = f"{total:.2f}" if total is not None else None
    return out
