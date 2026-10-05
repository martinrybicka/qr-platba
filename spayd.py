"""Offline Czech QR Platba / SPAYD validation and encoding."""

from decimal import Decimal, InvalidOperation
import re
import unicodedata


class PaymentError(ValueError):
    pass


def _mod97(value: str) -> int:
    remainder = 0
    for char in value:
        digits = char if char.isdigit() else str(ord(char) - 55)
        for digit in digits:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder


def valid_iban(value: str) -> bool:
    value = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", value):
        return False
    if value.startswith("CZ") and not re.fullmatch(r"CZ[0-9]{22}", value):
        return False
    return _mod97(value[4:] + value[:4]) == 1


def _czech_checksum(value: str, weights: list[int]) -> bool:
    padded = value.zfill(len(weights))
    return sum(int(digit) * weight for digit, weight in zip(padded, weights)) % 11 == 0


def account_to_iban(value: str) -> str:
    compact = re.sub(r"\s+", "", value).upper()
    if re.match(r"^[A-Z]{2}", compact):
        if not valid_iban(compact):
            raise PaymentError("IBAN má neplatný tvar nebo kontrolní číslice (MOD 97).")
        return compact
    match = re.fullmatch(r"(?:(\d{1,6})-)?(\d{1,10})/(\d{4})", compact)
    if not match:
        raise PaymentError("Číslo účtu musí mít tvar 1234567890/3030 nebo 123456-1234567890/3030.")
    prefix, number, bank = match.groups()
    prefix = prefix or ""
    if not _czech_checksum(prefix, [10, 5, 8, 4, 2, 1]) or not _czech_checksum(number, [6, 3, 7, 9, 10, 5, 8, 4, 2, 1]):
        raise PaymentError("České číslo účtu nemá platnou kontrolní číslici.")
    bban = bank + prefix.zfill(6) + number.zfill(10)
    check = 98 - _mod97(bban + "123500")  # CZ → 12 35; provisional check digits 00
    iban = f"CZ{check:02d}{bban}"
    if not valid_iban(iban):
        raise PaymentError("IBAN se nepodařilo ověřit.")
    return iban


def valid_vs(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9]{0,10}", value))


def normalize_message(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.upper())
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^A-Z0-9 $%+./:-]", " ", ascii_value).split())


def generate_spayd(account: str, amount: str, currency: str = "CZK", vs: str = "", message: str = "") -> tuple[str, str]:
    iban = account_to_iban(account)
    if currency != "CZK":
        raise PaymentError("Pro tuzemskou QR Platbu je podporována měna CZK.")
    if not valid_vs(vs):
        raise PaymentError("Variabilní symbol může obsahovat jen číslice, nejvýše 10 znaků.")
    compact_amount = re.sub(r"[ \u00a0\u202f]", "", str(amount)).replace(",", ".")
    if not re.fullmatch(r"[0-9]{1,7}(?:\.[0-9]{1,2})?", compact_amount):
        raise PaymentError("Částka musí mít nejvýše dvě desetinná místa.")
    try:
        decimal = Decimal(compact_amount)
    except InvalidOperation as exc:
        raise PaymentError("Neplatná částka.") from exc
    if not Decimal("0.01") <= decimal <= Decimal("9999999.99"):
        raise PaymentError("Částka musí být od 0,01 do 9 999 999,99 Kč.")
    normalized_message = normalize_message(message)
    if len(normalized_message) > 60:
        raise PaymentError("Zpráva může mít nejvýše 60 znaků po převodu bez diakritiky.")
    parts = ["SPD", "1.0", f"ACC:{iban}", f"AM:{decimal:.2f}", "CC:CZK"]
    if vs:
        parts.append(f"X-VS:{vs}")
    if normalized_message:
        parts.append(f"MSG:{normalized_message}")
    return "*".join(parts), iban
