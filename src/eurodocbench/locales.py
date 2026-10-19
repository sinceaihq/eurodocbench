"""Locale conventions used to render the synthetic documents.

Number and date formats follow common business practice in each country
(CLDR conventions, with the variations seen on real invoices). VAT rates are
the 2026 standard and reduced rates. Field labels come in two variants per
language so that a system cannot rely on a single fixed string.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

FIELD_LABELS = (
    "title",
    "invoice_number",
    "issue_date",
    "due_date",
    "seller",
    "buyer",
    "vat_id",
    "iban",
    "description",
    "quantity",
    "unit_price",
    "line_amount",
    "net_amount",
    "vat",
    "total",
)


@dataclass(frozen=True)
class Locale:
    code: str
    language: str
    country: str
    currency: str
    currency_symbol: str
    symbol_before: bool
    decimal_sep: str
    group_sep: str
    date_short: str  # placeholders {d} {dd} {m} {mm} {yyyy}
    date_long: str  # placeholders {d} {month} {yyyy}
    months: tuple[str, ...]
    vat_rates: tuple[Decimal, ...]  # standard rate first
    labels: dict[str, tuple[str, str]]
    items: tuple[str, ...]
    legal_forms: tuple[str, ...]
    sectors: tuple[str, ...]
    streets: tuple[str, ...]  # patterns with {stem} / {Stem} and {n}
    cities: tuple[str, ...]
    postcode: str  # pattern: 9 = digit, A = letter, other characters literal
    vat_prefix: str
    iban_length: int
    amount_scale: int = 1  # typical magnitude relative to EUR


def _d(*values: str) -> tuple[Decimal, ...]:
    return tuple(Decimal(v) for v in values)


# Items are in the same order in every language (see ITEM_KEYS).
ITEM_KEYS = (
    "consulting",
    "software_licence",
    "office_supplies",
    "cleaning",
    "freight",
    "maintenance",
    "training",
    "printer_paper",
    "laptop",
    "monitor",
    "web_hosting",
    "translation",
    "office_chair",
    "catering",
)
# Items that use the first reduced rate on multi-rate invoices.
REDUCED_RATE_ITEMS = frozenset({"training", "catering"})

LOCALES: dict[str, Locale] = {}


def _add(loc: Locale) -> None:
    assert set(loc.labels) == set(FIELD_LABELS), loc.code
    assert len(loc.items) == len(ITEM_KEYS), loc.code
    assert len(loc.months) == 12, loc.code
    LOCALES[loc.code] = loc


_add(
    Locale(
        code="fi-FI", language="fi", country="FI", currency="EUR", currency_symbol="€",
        symbol_before=False, decimal_sep=",", group_sep=" ",
        date_short="{d}.{m}.{yyyy}", date_long="{d}. {month} {yyyy}",
        months=("tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta", "toukokuuta",
                "kesäkuuta", "heinäkuuta", "elokuuta", "syyskuuta", "lokakuuta",
                "marraskuuta", "joulukuuta"),
        vat_rates=_d("25.5", "13.5", "10"),
        labels={
            "title": ("Lasku", "LASKU"),
            "invoice_number": ("Laskun numero", "Laskunro"),
            "issue_date": ("Laskun päivämäärä", "Päiväys"),
            "due_date": ("Eräpäivä", "Erääntyy"),
            "seller": ("Myyjä", "Laskuttaja"),
            "buyer": ("Ostaja", "Asiakas"),
            "vat_id": ("ALV-numero", "ALV-tunniste"),
            "iban": ("IBAN", "Tilinumero (IBAN)"),
            "description": ("Kuvaus", "Tuote"),
            "quantity": ("Määrä", "Kpl"),
            "unit_price": ("à-hinta", "Yksikköhinta"),
            "line_amount": ("Summa", "Rivisumma"),
            "net_amount": ("Veroton summa", "Veroton yhteensä"),
            "vat": ("ALV", "Arvonlisävero"),
            "total": ("Yhteensä", "Maksettava yhteensä"),
        },
        items=("Konsultointipalvelut", "Ohjelmistolisenssi (vuosi)", "Toimistotarvikkeet",
               "Siivouspalvelut", "Rahtikuljetus", "Laitteiden huolto", "Henkilöstökoulutus",
               "Tulostinpaperi A4 (laatikko)", "Kannettava tietokone", "Tietokonenäyttö",
               "Verkkosivujen ylläpito (kk)", "Käännöspalvelut", "Toimistotuoli", "Pitopalvelu"),
        legal_forms=("Oy", "Ay"),
        sectors=("Tekniikka", "Logistiikka", "Palvelut", "Rakennus", "Konsultointi"),
        streets=("{Stem}katu {n}", "{Stem}tie {n}"),
        cities=("Helsinki", "Espoo", "Tampere", "Turku", "Oulu"),
        postcode="99999", vat_prefix="FI", iban_length=18,
    )
)  # fmt: skip

_add(
    Locale(
        code="sv-SE", language="sv", country="SE", currency="SEK", currency_symbol="kr",
        symbol_before=False, decimal_sep=",", group_sep=" ",
        date_short="{yyyy}-{mm}-{dd}", date_long="{d} {month} {yyyy}",
        months=("januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti",
                "september", "oktober", "november", "december"),
        vat_rates=_d("25", "12", "6"),
        labels={
            "title": ("Faktura", "FAKTURA"),
            "invoice_number": ("Fakturanummer", "Fakturanr"),
            "issue_date": ("Fakturadatum", "Datum"),
            "due_date": ("Förfallodatum", "Förfaller"),
            "seller": ("Säljare", "Leverantör"),
            "buyer": ("Köpare", "Kund"),
            "vat_id": ("Momsreg.nr", "VAT-nummer"),
            "iban": ("IBAN", "Bankkonto (IBAN)"),
            "description": ("Beskrivning", "Artikel"),
            "quantity": ("Antal", "Ant."),
            "unit_price": ("À-pris", "Styckpris"),
            "line_amount": ("Belopp", "Summa"),
            "net_amount": ("Netto", "Summa exkl. moms"),
            "vat": ("Moms", "Mervärdesskatt"),
            "total": ("Att betala", "Totalt inkl. moms"),
        },
        items=("Konsulttjänster", "Programvarulicens (år)", "Kontorsmaterial", "Städtjänster",
               "Godstransport", "Underhåll av utrustning", "Personalutbildning",
               "Skrivarpapper A4 (kartong)", "Bärbar dator", "Datorskärm", "Webbhotell (månad)",
               "Översättningstjänster", "Kontorsstol", "Catering"),
        legal_forms=("AB", "HB"),
        sectors=("Teknik", "Logistik", "Tjänster", "Bygg", "Konsult"),
        streets=("{Stem}gatan {n}", "{Stem}vägen {n}"),
        cities=("Stockholm", "Göteborg", "Malmö", "Uppsala", "Västerås"),
        postcode="999 99", vat_prefix="SE", iban_length=24, amount_scale=10,
    )
)  # fmt: skip

_add(
    Locale(
        code="de-DE", language="de", country="DE", currency="EUR", currency_symbol="€",
        symbol_before=False, decimal_sep=",", group_sep=".",
        date_short="{dd}.{mm}.{yyyy}", date_long="{d}. {month} {yyyy}",
        months=("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
                "September", "Oktober", "November", "Dezember"),
        vat_rates=_d("19", "7"),
        labels={
            "title": ("Rechnung", "RECHNUNG"),
            "invoice_number": ("Rechnungsnummer", "Rechnungs-Nr."),
            "issue_date": ("Rechnungsdatum", "Datum"),
            "due_date": ("Fälligkeitsdatum", "Zahlbar bis"),
            "seller": ("Rechnungssteller", "Lieferant"),
            "buyer": ("Rechnungsempfänger", "Kunde"),
            "vat_id": ("USt-IdNr.", "Umsatzsteuer-ID"),
            "iban": ("IBAN", "Bankverbindung (IBAN)"),
            "description": ("Beschreibung", "Leistung"),
            "quantity": ("Menge", "Anz."),
            "unit_price": ("Einzelpreis", "E-Preis"),
            "line_amount": ("Betrag", "Gesamt"),
            "net_amount": ("Nettobetrag", "Zwischensumme (netto)"),
            "vat": ("MwSt.", "Umsatzsteuer"),
            "total": ("Gesamtbetrag", "Rechnungsbetrag"),
        },
        items=("Beratungsleistungen", "Softwarelizenz (jährlich)", "Büromaterial",
               "Reinigungsleistungen", "Frachttransport", "Wartung von Geräten",
               "Mitarbeiterschulung", "Druckerpapier A4 (Karton)", "Laptop", "Computermonitor",
               "Webhosting (monatlich)", "Übersetzungsleistungen", "Bürostuhl", "Catering"),
        legal_forms=("GmbH", "AG", "KG"),
        sectors=("Technik", "Logistik", "Dienstleistungen", "Bau", "Beratung"),
        streets=("{Stem}straße {n}", "{Stem}weg {n}"),
        cities=("Berlin", "Hamburg", "München", "Köln", "Leipzig"),
        postcode="99999", vat_prefix="DE", iban_length=22,
    )
)  # fmt: skip

_add(
    Locale(
        code="fr-FR", language="fr", country="FR", currency="EUR", currency_symbol="€",
        symbol_before=False, decimal_sep=",", group_sep=" ",
        date_short="{dd}/{mm}/{yyyy}", date_long="{d} {month} {yyyy}",
        months=("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                "septembre", "octobre", "novembre", "décembre"),
        vat_rates=_d("20", "10", "5.5"),
        labels={
            "title": ("Facture", "FACTURE"),
            "invoice_number": ("Numéro de facture", "Facture n°"),
            "issue_date": ("Date de facture", "Date d'émission"),
            "due_date": ("Date d'échéance", "Échéance"),
            "seller": ("Émetteur", "Fournisseur"),
            "buyer": ("Client", "Facturé à"),
            "vat_id": ("N° TVA intracommunautaire", "N° TVA"),
            "iban": ("IBAN", "Coordonnées bancaires (IBAN)"),
            "description": ("Désignation", "Description"),
            "quantity": ("Quantité", "Qté"),
            "unit_price": ("Prix unitaire HT", "P.U. HT"),
            "line_amount": ("Montant HT", "Total HT ligne"),
            "net_amount": ("Total HT", "Montant hors taxes"),
            "vat": ("TVA", "Montant TVA"),
            "total": ("Total TTC", "Net à payer"),
        },
        items=("Prestations de conseil", "Licence logicielle (annuelle)", "Fournitures de bureau",
               "Services de nettoyage", "Transport de marchandises", "Maintenance des équipements",
               "Formation du personnel", "Papier d'imprimante A4 (carton)", "Ordinateur portable",
               "Écran d'ordinateur", "Hébergement web (mensuel)", "Services de traduction",
               "Chaise de bureau", "Service traiteur"),
        legal_forms=("SAS", "SARL", "SA"),
        sectors=("Technologies", "Logistique", "Services", "Bâtiment", "Conseil"),
        streets=("{n} rue {Stem}", "{n} avenue {Stem}"),
        cities=("Paris", "Lyon", "Marseille", "Toulouse", "Nantes"),
        postcode="99999", vat_prefix="FR", iban_length=27,
    )
)  # fmt: skip

_add(
    Locale(
        code="nl-NL", language="nl", country="NL", currency="EUR", currency_symbol="€",
        symbol_before=True, decimal_sep=",", group_sep=".",
        date_short="{dd}-{mm}-{yyyy}", date_long="{d} {month} {yyyy}",
        months=("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                "september", "oktober", "november", "december"),
        vat_rates=_d("21", "9"),
        labels={
            "title": ("Factuur", "FACTUUR"),
            "invoice_number": ("Factuurnummer", "Factuurnr."),
            "issue_date": ("Factuurdatum", "Datum"),
            "due_date": ("Vervaldatum", "Te betalen vóór"),
            "seller": ("Leverancier", "Van"),
            "buyer": ("Klant", "Factuuradres"),
            "vat_id": ("Btw-nummer", "Btw-id"),
            "iban": ("IBAN", "Rekeningnummer (IBAN)"),
            "description": ("Omschrijving", "Artikel"),
            "quantity": ("Aantal", "Aant."),
            "unit_price": ("Prijs per stuk", "Stukprijs"),
            "line_amount": ("Bedrag", "Totaal"),
            "net_amount": ("Subtotaal", "Totaal excl. btw"),
            "vat": ("Btw", "Btw-bedrag"),
            "total": ("Totaal incl. btw", "Te betalen"),
        },
        items=("Adviesdiensten", "Softwarelicentie (jaarlijks)", "Kantoorartikelen",
               "Schoonmaakdiensten", "Vrachtvervoer", "Onderhoud van apparatuur",
               "Personeelstraining", "Printpapier A4 (doos)", "Laptop", "Computermonitor",
               "Webhosting (maandelijks)", "Vertaaldiensten", "Bureaustoel", "Catering"),
        legal_forms=("B.V.", "N.V."),
        sectors=("Techniek", "Logistiek", "Diensten", "Bouw", "Advies"),
        streets=("{Stem}straat {n}", "{Stem}weg {n}"),
        cities=("Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"),
        postcode="9999 AA", vat_prefix="NL", iban_length=18,
    )
)  # fmt: skip

_add(
    Locale(
        code="it-IT", language="it", country="IT", currency="EUR", currency_symbol="€",
        symbol_before=False, decimal_sep=",", group_sep=".",
        date_short="{dd}/{mm}/{yyyy}", date_long="{d} {month} {yyyy}",
        months=("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
                "agosto", "settembre", "ottobre", "novembre", "dicembre"),
        vat_rates=_d("22", "10", "5"),
        labels={
            "title": ("Fattura", "FATTURA"),
            "invoice_number": ("Numero fattura", "Fattura n."),
            "issue_date": ("Data fattura", "Data di emissione"),
            "due_date": ("Data di scadenza", "Scadenza"),
            "seller": ("Fornitore", "Cedente"),
            "buyer": ("Cliente", "Cessionario"),
            "vat_id": ("Partita IVA", "P. IVA"),
            "iban": ("IBAN", "Coordinate bancarie (IBAN)"),
            "description": ("Descrizione", "Articolo"),
            "quantity": ("Quantità", "Q.tà"),
            "unit_price": ("Prezzo unitario", "Prezzo unit."),
            "line_amount": ("Importo", "Totale riga"),
            "net_amount": ("Imponibile", "Totale imponibile"),
            "vat": ("IVA", "Imposta"),
            "total": ("Totale fattura", "Totale da pagare"),
        },
        items=("Servizi di consulenza", "Licenza software (annuale)", "Articoli per ufficio",
               "Servizi di pulizia", "Trasporto merci", "Manutenzione delle attrezzature",
               "Formazione del personale", "Carta per stampante A4 (scatola)",
               "Computer portatile", "Monitor per computer", "Hosting web (mensile)",
               "Servizi di traduzione", "Sedia da ufficio", "Servizio di catering"),
        legal_forms=("S.r.l.", "S.p.A."),
        sectors=("Tecnologie", "Logistica", "Servizi", "Costruzioni", "Consulenza"),
        streets=("Via {Stem} {n}", "Corso {Stem} {n}"),
        cities=("Milano", "Roma", "Torino", "Bologna", "Firenze"),
        postcode="99999", vat_prefix="IT", iban_length=27,
    )
)  # fmt: skip

_add(
    Locale(
        code="es-ES", language="es", country="ES", currency="EUR", currency_symbol="€",
        symbol_before=False, decimal_sep=",", group_sep=".",
        date_short="{dd}/{mm}/{yyyy}", date_long="{d} de {month} de {yyyy}",
        months=("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"),
        vat_rates=_d("21", "10"),
        labels={
            "title": ("Factura", "FACTURA"),
            "invoice_number": ("Número de factura", "Factura n.º"),
            "issue_date": ("Fecha de factura", "Fecha de emisión"),
            "due_date": ("Fecha de vencimiento", "Vencimiento"),
            "seller": ("Emisor", "Proveedor"),
            "buyer": ("Cliente", "Facturar a"),
            "vat_id": ("NIF-IVA", "Número de IVA"),
            "iban": ("IBAN", "Cuenta bancaria (IBAN)"),
            "description": ("Descripción", "Concepto"),
            "quantity": ("Cantidad", "Cant."),
            "unit_price": ("Precio unitario", "Precio unit."),
            "line_amount": ("Importe", "Total línea"),
            "net_amount": ("Base imponible", "Subtotal"),
            "vat": ("IVA", "Cuota de IVA"),
            "total": ("Total factura", "Total a pagar"),
        },
        items=("Servicios de consultoría", "Licencia de software (anual)", "Material de oficina",
               "Servicios de limpieza", "Transporte de mercancías", "Mantenimiento de equipos",
               "Formación del personal", "Papel de impresora A4 (caja)", "Ordenador portátil",
               "Monitor de ordenador", "Alojamiento web (mensual)", "Servicios de traducción",
               "Silla de oficina", "Servicio de catering"),
        legal_forms=("S.L.", "S.A."),
        sectors=("Tecnología", "Logística", "Servicios", "Construcciones", "Consultoría"),
        streets=("Calle {Stem} {n}", "Avenida {Stem} {n}"),
        cities=("Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"),
        postcode="99999", vat_prefix="ES", iban_length=24,
    )
)  # fmt: skip

_add(
    Locale(
        code="pl-PL", language="pl", country="PL", currency="PLN", currency_symbol="zł",
        symbol_before=False, decimal_sep=",", group_sep=" ",
        date_short="{dd}.{mm}.{yyyy}", date_long="{d} {month} {yyyy}",
        months=("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
                "sierpnia", "września", "października", "listopada", "grudnia"),
        vat_rates=_d("23", "8", "5"),
        labels={
            "title": ("Faktura VAT", "FAKTURA"),
            "invoice_number": ("Numer faktury", "Nr faktury"),
            "issue_date": ("Data wystawienia", "Data faktury"),
            "due_date": ("Termin płatności", "Termin zapłaty"),
            "seller": ("Sprzedawca", "Wystawca"),
            "buyer": ("Nabywca", "Odbiorca"),
            "vat_id": ("NIP UE", "Numer VAT UE"),
            "iban": ("IBAN", "Nr konta (IBAN)"),
            "description": ("Nazwa towaru lub usługi", "Opis"),
            "quantity": ("Ilość", "Ilość szt."),
            "unit_price": ("Cena jedn. netto", "Cena jednostkowa"),
            "line_amount": ("Wartość netto", "Wartość"),
            "net_amount": ("Razem netto", "Wartość netto razem"),
            "vat": ("Kwota VAT", "VAT"),
            "total": ("Do zapłaty", "Razem brutto"),
        },
        items=("Usługi doradcze", "Licencja na oprogramowanie (roczna)", "Artykuły biurowe",
               "Usługi sprzątania", "Transport towarów", "Konserwacja sprzętu",
               "Szkolenie pracowników", "Papier do drukarki A4 (karton)", "Laptop",
               "Monitor komputerowy", "Hosting stron WWW (miesięczny)", "Usługi tłumaczeniowe",
               "Krzesło biurowe", "Usługi cateringowe"),
        legal_forms=("Sp. z o.o.", "S.A."),
        sectors=("Technika", "Logistyka", "Usługi", "Budownictwo", "Doradztwo"),
        streets=("ul. {Stem} {n}", "al. {Stem} {n}"),
        cities=("Warszawa", "Kraków", "Wrocław", "Gdańsk", "Poznań"),
        postcode="99-999", vat_prefix="PL", iban_length=28, amount_scale=4,
    )
)  # fmt: skip

_add(
    Locale(
        code="pt-PT", language="pt", country="PT", currency="EUR", currency_symbol="€",
        symbol_before=False, decimal_sep=",", group_sep=" ",
        date_short="{dd}/{mm}/{yyyy}", date_long="{d} de {month} de {yyyy}",
        months=("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                "setembro", "outubro", "novembro", "dezembro"),
        vat_rates=_d("23", "13", "6"),
        labels={
            "title": ("Fatura", "FATURA"),
            "invoice_number": ("Número da fatura", "Fatura n.º"),
            "issue_date": ("Data da fatura", "Data de emissão"),
            "due_date": ("Data de vencimento", "Vencimento"),
            "seller": ("Fornecedor", "Emitente"),
            "buyer": ("Cliente", "Adquirente"),
            "vat_id": ("N.º de IVA", "NIF-IVA"),
            "iban": ("IBAN", "Conta bancária (IBAN)"),
            "description": ("Descrição", "Artigo"),
            "quantity": ("Quantidade", "Qtd."),
            "unit_price": ("Preço unitário", "Preço unit."),
            "line_amount": ("Valor", "Total linha"),
            "net_amount": ("Total sem IVA", "Valor líquido"),
            "vat": ("IVA", "Total IVA"),
            "total": ("Total a pagar", "Total com IVA"),
        },
        items=("Serviços de consultoria", "Licença de software (anual)", "Material de escritório",
               "Serviços de limpeza", "Transporte de mercadorias", "Manutenção de equipamentos",
               "Formação de pessoal", "Papel de impressora A4 (caixa)", "Computador portátil",
               "Monitor de computador", "Alojamento web (mensal)", "Serviços de tradução",
               "Cadeira de escritório", "Serviço de catering"),
        legal_forms=("Lda.", "S.A."),
        sectors=("Tecnologia", "Logística", "Serviços", "Construções", "Consultoria"),
        streets=("Rua {Stem} {n}", "Avenida {Stem} {n}"),
        cities=("Lisboa", "Porto", "Braga", "Coimbra", "Faro"),
        postcode="9999-999", vat_prefix="PT", iban_length=25,
    )
)  # fmt: skip

_add(
    Locale(
        code="cs-CZ", language="cs", country="CZ", currency="CZK", currency_symbol="Kč",
        symbol_before=False, decimal_sep=",", group_sep=" ",
        date_short="{d}. {m}. {yyyy}", date_long="{d}. {month} {yyyy}",
        months=("ledna", "února", "března", "dubna", "května", "června", "července", "srpna",
                "září", "října", "listopadu", "prosince"),
        vat_rates=_d("21", "12"),
        labels={
            "title": ("Faktura – daňový doklad", "FAKTURA"),
            "invoice_number": ("Číslo faktury", "Faktura č."),
            "issue_date": ("Datum vystavení", "Vystaveno"),
            "due_date": ("Datum splatnosti", "Splatnost"),
            "seller": ("Dodavatel", "Prodávající"),
            "buyer": ("Odběratel", "Kupující"),
            "vat_id": ("DIČ", "DIČ (VAT)"),
            "iban": ("IBAN", "Bankovní účet (IBAN)"),
            "description": ("Popis", "Položka"),
            "quantity": ("Množství", "Počet"),
            "unit_price": ("Cena za jednotku", "Jedn. cena"),
            "line_amount": ("Částka", "Celkem"),
            "net_amount": ("Základ daně", "Celkem bez DPH"),
            "vat": ("DPH", "Výše DPH"),
            "total": ("Celkem k úhradě", "K úhradě"),
        },
        items=("Poradenské služby", "Softwarová licence (roční)", "Kancelářské potřeby",
               "Úklidové služby", "Nákladní doprava", "Údržba zařízení", "Školení zaměstnanců",
               "Papír do tiskárny A4 (karton)", "Notebook", "Počítačový monitor",
               "Webhosting (měsíční)", "Překladatelské služby", "Kancelářská židle",
               "Cateringové služby"),
        legal_forms=("s.r.o.", "a.s."),
        sectors=("Technika", "Logistika", "Služby", "Stavby", "Poradenství"),
        streets=("{Stem}ova {n}", "Na {Stem} {n}"),
        cities=("Praha", "Brno", "Ostrava", "Plzeň", "Olomouc"),
        postcode="999 99", vat_prefix="CZ", iban_length=24, amount_scale=25,
    )
)  # fmt: skip

_add(
    Locale(
        code="da-DK", language="da", country="DK", currency="DKK", currency_symbol="kr.",
        symbol_before=False, decimal_sep=",", group_sep=".",
        date_short="{dd}.{mm}.{yyyy}", date_long="{d}. {month} {yyyy}",
        months=("januar", "februar", "marts", "april", "maj", "juni", "juli", "august",
                "september", "oktober", "november", "december"),
        vat_rates=_d("25"),
        labels={
            "title": ("Faktura", "FAKTURA"),
            "invoice_number": ("Fakturanummer", "Fakturanr."),
            "issue_date": ("Fakturadato", "Dato"),
            "due_date": ("Forfaldsdato", "Betalingsfrist"),
            "seller": ("Leverandør", "Afsender"),
            "buyer": ("Kunde", "Faktureres til"),
            "vat_id": ("Momsnr.", "CVR/moms-nr."),
            "iban": ("IBAN", "Bankkonto (IBAN)"),
            "description": ("Beskrivelse", "Varetekst"),
            "quantity": ("Antal", "Stk."),
            "unit_price": ("Stykpris", "Enhedspris"),
            "line_amount": ("Beløb", "I alt"),
            "net_amount": ("Subtotal", "Beløb ekskl. moms"),
            "vat": ("Moms", "Moms i alt"),
            "total": ("Total", "I alt at betale"),
        },
        items=("Konsulentydelser", "Softwarelicens (årlig)", "Kontorartikler", "Rengøringsydelser",
               "Godstransport", "Vedligeholdelse af udstyr", "Medarbejderuddannelse",
               "Printerpapir A4 (kasse)", "Bærbar computer", "Computerskærm",
               "Webhosting (månedlig)", "Oversættelsesydelser", "Kontorstol", "Catering"),
        legal_forms=("ApS", "A/S"),
        sectors=("Teknik", "Logistik", "Service", "Byg", "Rådgivning"),
        streets=("{Stem}vej {n}", "{Stem}gade {n}"),
        cities=("København", "Aarhus", "Odense", "Aalborg", "Esbjerg"),
        postcode="9999", vat_prefix="DK", iban_length=18, amount_scale=7,
    )
)  # fmt: skip

_add(
    Locale(
        code="en-IE", language="en", country="IE", currency="EUR", currency_symbol="€",
        symbol_before=True, decimal_sep=".", group_sep=",",
        date_short="{dd}/{mm}/{yyyy}", date_long="{d} {month} {yyyy}",
        months=("January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December"),
        vat_rates=_d("23", "13.5", "9"),
        labels={
            "title": ("Invoice", "TAX INVOICE"),
            "invoice_number": ("Invoice number", "Invoice no."),
            "issue_date": ("Invoice date", "Date of issue"),
            "due_date": ("Due date", "Payment due"),
            "seller": ("Supplier", "From"),
            "buyer": ("Customer", "Bill to"),
            "vat_id": ("VAT number", "VAT reg. no."),
            "iban": ("IBAN", "Bank account (IBAN)"),
            "description": ("Description", "Item"),
            "quantity": ("Quantity", "Qty"),
            "unit_price": ("Unit price", "Rate"),
            "line_amount": ("Amount", "Line total"),
            "net_amount": ("Subtotal", "Net amount"),
            "vat": ("VAT", "VAT amount"),
            "total": ("Total", "Amount due"),
        },
        items=("Consulting services", "Software licence (annual)", "Office supplies",
               "Cleaning services", "Freight transport", "Equipment maintenance",
               "Staff training", "Printer paper A4 (box)", "Laptop computer", "Computer monitor",
               "Web hosting (monthly)", "Translation services", "Office chair",
               "Catering services"),
        legal_forms=("Ltd", "DAC"),
        sectors=("Technologies", "Logistics", "Services", "Construction", "Consulting"),
        streets=("{n} {Stem} Street", "{n} {Stem} Road"),
        cities=("Dublin", "Cork", "Galway", "Limerick", "Waterford"),
        postcode="A99 A9A9", vat_prefix="IE", iban_length=22,
    )
)  # fmt: skip
