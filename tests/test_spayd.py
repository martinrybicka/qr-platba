import unittest

from spayd import PaymentError, account_to_iban, generate_spayd, valid_iban, valid_vs


class SPAYDTests(unittest.TestCase):
    def test_czech_account_to_iban_and_mod97(self):
        self.assertEqual(account_to_iban("1265098001/5500"), "CZ5855000000001265098001")
        self.assertEqual(account_to_iban("0-1265098001/5500"), "CZ5855000000001265098001")
        self.assertTrue(valid_iban("CZ58 5500 0000 0012 6509 8001"))
        self.assertFalse(valid_iban("CZ5955000000001265098001"))
        with self.assertRaises(PaymentError):
            account_to_iban("1265098002/5500")

    def test_variable_symbol(self):
        self.assertTrue(valid_vs(""))
        self.assertTrue(valid_vs("0000000000"))
        self.assertFalse(valid_vs("12345678901"))
        self.assertFalse(valid_vs("12A3"))
        self.assertFalse(valid_vs("１２３"))

    def test_spayd_output(self):
        value, iban = generate_spayd("1265098001/5500", "1 250,00", vs="202600123", message="Platba za zboží")
        self.assertEqual(iban, "CZ5855000000001265098001")
        self.assertEqual(value, "SPD*1.0*ACC:CZ5855000000001265098001*AM:1250.00*CC:CZK*X-VS:202600123*MSG:PLATBA ZA ZBOZI")

    def test_amount_limits_and_message(self):
        for amount in ("1,234", "10000000", "0", "-1", "1e3"):
            with self.subTest(amount=amount), self.assertRaises(PaymentError):
                generate_spayd("CZ5855000000001265098001", amount)
        with self.assertRaises(PaymentError):
            generate_spayd("CZ5855000000001265098001", "1", message="x" * 61)
        with self.assertRaises(PaymentError):
            generate_spayd("CZ5855000000001265098001", "1", currency="EUR")


if __name__ == "__main__":
    unittest.main()
