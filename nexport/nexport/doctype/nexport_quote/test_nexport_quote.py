# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestNexPortQuote(FrappeTestCase):
	def test_total_computation(self) -> None:
		quote = frappe.get_doc({
			"doctype": "NexPort Quote",
			"customer": "_Test Customer",
			"items": [
				{"item": "TEST-001", "quantity": 10, "unit_price": 100},
				{"item": "TEST-002", "quantity": 5, "unit_price": 200},
			],
		})
		quote.validate()
		self.assertEqual(quote.total_amount, 2000)
		self.assertEqual(quote.items[0].amount, 1000)
		self.assertEqual(quote.items[1].amount, 1000)

	def test_create_so_requires_accepted(self) -> None:
		quote = frappe.get_doc({
			"doctype": "NexPort Quote",
			"customer": "_Test Customer",
			"status": "Draft",
			"items": [
				{"item": "TEST-001", "quantity": 1, "unit_price": 100},
			],
		})
		quote.insert()
		self.assertRaises(frappe.ValidationError, quote.create_sales_order)
