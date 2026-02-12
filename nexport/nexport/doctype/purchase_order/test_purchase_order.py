# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPurchaseOrder(FrappeTestCase):
	def test_total_computation(self) -> None:
		po = frappe.get_doc({
			"doctype": "Purchase Order",
			"supplier": "_Test Supplier",
			"currency": "THB",
			"items": [
				{"item": "TEST-001", "quantity": 10, "unit_price": 50},
				{"item": "TEST-002", "quantity": 5, "unit_price": 100},
			],
		})
		po.validate()
		self.assertEqual(po.total_amount, 1000)

	def test_supplementary_po_fields(self) -> None:
		po = frappe.get_doc({
			"doctype": "Purchase Order",
			"supplier": "_Test Supplier",
			"currency": "THB",
			"is_supplementary": 1,
			"parent_po": "NP-PO-2026-0001",
			"items": [
				{"item": "TEST-001", "quantity": 2, "unit_price": 50},
			],
		})
		self.assertTrue(po.is_supplementary)
		self.assertEqual(po.parent_po, "NP-PO-2026-0001")
