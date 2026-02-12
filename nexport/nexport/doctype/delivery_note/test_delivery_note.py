# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDeliveryNote(FrappeTestCase):
	def test_provisional_dn_no_so_required(self) -> None:
		"""Provisional DN should not require a Sales Order."""
		dn = frappe.get_doc({
			"doctype": "Delivery Note",
			"customer": "_Test Customer",
			"is_provisional": 1,
			"items": [
				{"item": "TEST-001", "quantity": 1},
			],
		})
		# Should not throw - provisional doesn't need SO
		dn.validate()

	def test_non_provisional_requires_so(self) -> None:
		"""Non-provisional DN must have a Sales Order."""
		dn = frappe.get_doc({
			"doctype": "Delivery Note",
			"customer": "_Test Customer",
			"is_provisional": 0,
			"items": [
				{"item": "TEST-001", "quantity": 1},
			],
		})
		self.assertRaises(frappe.ValidationError, dn.validate)
