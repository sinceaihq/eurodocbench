"""Synthetic VAT numbers and IBANs that cannot belong to anyone.

Each generator produces an identifier with the right national *format* and
then deliberately breaks its official check digit, so a synthetic document
can never quote a real company's VAT registration or a real bank account.
The ``is_valid_*`` functions implement the national checksum rules and are
used by the tests to prove it.
"""

from __future__ import annotations

import random
import string

# --------------------------------------------------------------------- VAT


def _digits(rng: random.Random, n: int, first_nonzero: bool = False) -> str:
    out = [str(rng.randint(1 if first_nonzero else 0, 9))]
    out += [str(rng.randint(0, 9)) for _ in range(n - 1)]
    return "".join(out)


def _luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _fi_ok(body: str) -> bool:
    if len(body) != 8 or not body.isdigit():
        return False
    s = sum(int(d) * w for d, w in zip(body[:7], (7, 9, 10, 5, 8, 4, 2), strict=True)) % 11
    if s == 1:
        return False
    return int(body[7]) == (0 if s == 0 else 11 - s)


def _de_ok(body: str) -> bool:
    if len(body) != 9 or not body.isdigit():
        return False
    product = 10
    for ch in body[:8]:
        s = (int(ch) + product) % 10 or 10
        product = (2 * s) % 11
    check = 11 - product
    return int(body[8]) == (0 if check == 10 else check)


def _fr_ok(body: str) -> bool:
    if len(body) != 11 or not body.isdigit():
        return False
    siren = int(body[2:])
    return int(body[:2]) == (12 + 3 * (siren % 97)) % 97


def _nl_ok(body: str) -> bool:
    # Post-2020 numbers validate with ISO 7064 mod 97-10 over "NL" + body;
    # older ones with the 11-test on the first nine digits. Accept either.
    if len(body) != 12 or body[9] != "B" or not (body[:9] + body[10:]).isdigit():
        return False
    eleven = sum(int(d) * w for d, w in zip(body[:8], range(9, 1, -1), strict=True))
    if (eleven - int(body[8])) % 11 == 0:
        return True
    numeric = "".join(str(int(c, 36)) for c in "NL" + body)
    return int(numeric) % 97 == 1


def _pl_ok(body: str) -> bool:
    if len(body) != 10 or not body.isdigit():
        return False
    s = sum(int(d) * w for d, w in zip(body[:9], (6, 5, 7, 2, 3, 4, 5, 6, 7), strict=True)) % 11
    return s != 10 and s == int(body[9])


def _pt_ok(body: str) -> bool:
    if len(body) != 9 or not body.isdigit():
        return False
    s = sum(int(d) * w for d, w in zip(body[:8], range(9, 1, -1), strict=True))
    check = 11 - s % 11
    return int(body[8]) == (0 if check >= 10 else check)


def _cz_ok(body: str) -> bool:
    if len(body) != 8 or not body.isdigit():
        return False
    s = sum(int(d) * w for d, w in zip(body[:7], range(8, 1, -1), strict=True))
    check = (11 - s % 11) % 10
    return int(body[7]) == check


def _dk_ok(body: str) -> bool:
    if len(body) != 8 or not body.isdigit() or body[0] == "0":
        return False
    return sum(int(d) * w for d, w in zip(body, (2, 7, 6, 5, 4, 3, 2, 1), strict=True)) % 11 == 0


_IE_LETTERS = "WABCDEFGHIJKLMNOPQRSTUV"


def _ie_ok(body: str) -> bool:
    if len(body) not in (8, 9) or not body[:7].isdigit() or not body[7].isalpha():
        return False
    s = sum(int(d) * w for d, w in zip(body[:7], range(8, 1, -1), strict=True))
    if len(body) == 9:
        s += 9 * _IE_LETTERS.index(body[8]) if body[8] in _IE_LETTERS else 10**6
    return body[7] == _IE_LETTERS[s % 23]


_ES_CIF_LETTERS = "ABCDEFGHJNPQRSUVW"
_ES_CONTROL_LETTERS = "JABCDEFGHI"


def _es_ok(body: str) -> bool:
    # Company identifiers (CIF): letter + 7 digits + control digit or letter.
    if len(body) != 9 or body[0] not in _ES_CIF_LETTERS or not body[1:8].isdigit():
        return False
    digits = body[1:8]
    even = sum(int(d) for d in digits[1::2])
    odd = sum(sum(divmod(int(d) * 2, 10)) for d in digits[0::2])
    c = (10 - (even + odd) % 10) % 10
    return body[8] in (str(c), _ES_CONTROL_LETTERS[c])


def _it_ok(body: str) -> bool:
    return len(body) == 11 and body.isdigit() and _luhn_ok(body)


def _se_ok(body: str) -> bool:
    return len(body) == 12 and body.isdigit() and body.endswith("01") and _luhn_ok(body[:10])


VAT_VALIDATORS = {
    "FI": _fi_ok, "SE": _se_ok, "DE": _de_ok, "FR": _fr_ok, "NL": _nl_ok, "IT": _it_ok,
    "ES": _es_ok, "PL": _pl_ok, "PT": _pt_ok, "CZ": _cz_ok, "DK": _dk_ok, "IE": _ie_ok,
}  # fmt: skip


def _vat_body(rng: random.Random, country: str) -> str:
    if country == "FI":
        return _digits(rng, 8)
    if country == "SE":
        return _digits(rng, 10, first_nonzero=True) + "01"
    if country == "DE":
        return _digits(rng, 9, first_nonzero=True)
    if country == "FR":
        return _digits(rng, 2) + _digits(rng, 9, first_nonzero=True)
    if country == "NL":
        return _digits(rng, 9) + "B" + rng.choice(["01", "02", "03"])
    if country == "IT":
        return _digits(rng, 11)
    if country == "ES":
        return rng.choice("ABB") + _digits(rng, 7) + str(rng.randint(0, 9))
    if country == "PL":
        return _digits(rng, 10, first_nonzero=True)
    if country == "PT":
        return rng.choice("5") + _digits(rng, 8)
    if country == "CZ":
        return _digits(rng, 8, first_nonzero=True)
    if country == "DK":
        return _digits(rng, 8, first_nonzero=True)
    if country == "IE":
        return _digits(rng, 7) + rng.choice(_IE_LETTERS[1:]) + rng.choice(["", "H"])
    raise ValueError(country)


def synthetic_vat_id(rng: random.Random, country: str) -> str:
    """Canonical (no spaces, upper case) VAT number that fails its checksum."""
    validator = VAT_VALIDATORS[country]
    for _ in range(1000):
        body = _vat_body(rng, country)
        if not validator(body):
            return country + body
    raise RuntimeError(f"could not generate an invalid {country} VAT number")


def is_valid_vat_id(vat_id: str) -> bool:
    vat_id = vat_id.replace(" ", "").upper()
    validator = VAT_VALIDATORS.get(vat_id[:2])
    return bool(validator and validator(vat_id[2:]))


# --------------------------------------------------------------------- IBAN


def _iban_mod97(iban: str) -> int:
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97


def is_valid_iban(iban: str) -> bool:
    iban = iban.replace(" ", "").upper()
    return len(iban) >= 15 and iban[:2].isalpha() and _iban_mod97(iban) == 1


def synthetic_iban(rng: random.Random, country: str, length: int) -> str:
    """Canonical IBAN of the right length whose check digits are wrong."""
    n = length - 4
    if country == "NL":
        bban = "".join(rng.choice(string.ascii_uppercase) for _ in range(4)) + _digits(rng, n - 4)
    else:
        bban = _digits(rng, n)
    correct = 98 - _iban_mod97(country + "00" + bban)
    wrong = correct
    while wrong == correct:
        wrong = rng.randint(2, 98)
    iban = f"{country}{wrong:02d}{bban}"
    assert not is_valid_iban(iban)
    return iban


def group4(value: str) -> str:
    return " ".join(value[i : i + 4] for i in range(0, len(value), 4))
