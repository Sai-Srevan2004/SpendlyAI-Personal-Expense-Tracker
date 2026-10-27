
import unittest

from app.tools.transaction_tools import (
    validate_batch,
    validate_transaction_update,
    validate_transaction_date,
)


class TestTransactionValidation(unittest.TestCase):

    def test_update_rejects_negative_amount(self):
        result = validate_transaction_update(amount=-500)
        self.assertIsNotNone(result)

    def test_update_rejects_zero_amount(self):
        result = validate_transaction_update(amount=0)
        self.assertIsNotNone(result)

    def test_update_accepts_positive_amount(self):
        result = validate_transaction_update(amount=500)
        self.assertIsNone(result)

    def test_update_rejects_blank_category(self):
        result = validate_transaction_update(category="   ")
        self.assertIsNotNone(result)

    def test_update_rejects_blank_description(self):
        result = validate_transaction_update(description="   ")
        self.assertIsNotNone(result)

    def test_date_accepts_iso_format(self):
        result = validate_transaction_date("2026-10-27")
        self.assertIsNone(result)

    def test_date_rejects_invalid_calendar_date(self):
        result = validate_transaction_date("2026-02-30")
        self.assertIsNotNone(result)

    def test_date_accepts_relative_dates(self):
        for value in ("today", "yesterday", "tomorrow"):
            with self.subTest(value=value):
                self.assertIsNone(validate_transaction_date(value))


if __name__ == "__main__":
    unittest.main()
