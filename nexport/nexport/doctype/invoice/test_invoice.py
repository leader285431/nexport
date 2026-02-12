# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestInvoice(FrappeTestCase):
	def test_entity_type_auto_set_ap(self) -> None:
		inv = frappe.get_doc({
			"doctype": "Invoice",
			"type": "AP",
			"entity_type": "Supplier",
			"entity": "_Test Supplier",
		})
		inv.validate()
		self.assertEqual(inv.entity_type, "Supplier")

	def test_entity_type_auto_set_ar(self) -> None:
		inv = frappe.get_doc({
			"doctype": "Invoice",
			"type": "AR",
			"entity_type": "Customer",
			"entity": "_Test Customer",
		})
		inv.validate()
		self.assertEqual(inv.entity_type, "Customer")
