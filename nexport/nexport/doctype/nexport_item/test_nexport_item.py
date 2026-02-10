# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from nexport.nexport.doctype.nexport_item.nexport_item import _to_code, generate_sku


class TestNexPortItem(FrappeTestCase):
	def test_to_code(self) -> None:
		self.assertEqual(_to_code("Supplier A"), "SUP")
		self.assertEqual(_to_code("Electronics"), "ELE")
		self.assertEqual(_to_code("AB"), "AB")
		self.assertEqual(_to_code(""), "GEN")

	def test_generate_sku_format(self) -> None:
		sku = generate_sku(supplier="Acme Corp", category="Bolts", sub_category="M8")
		self.assertRegex(sku, r"^ACM-BOL-M8-\d{4}$")

	def test_generate_sku_defaults(self) -> None:
		sku = generate_sku()
		self.assertRegex(sku, r"^GEN-GEN-GEN-\d{4}$")

	def test_generate_sku_increments(self) -> None:
		"""Two SKUs with same prefix get sequential numbers."""
		sku1 = generate_sku(supplier="Test", category="Cat", sub_category="Sub")
		# Create an item so next call finds it
		item = frappe.get_doc({
			"doctype": "NexPort Item",
			"item_name": "Test Item",
			"customs_name": "Test",
			"sku": sku1,
		})
		item.db_insert()

		sku2 = generate_sku(supplier="Test", category="Cat", sub_category="Sub")
		seq1 = int(sku1.rsplit("-", 1)[-1])
		seq2 = int(sku2.rsplit("-", 1)[-1])
		self.assertEqual(seq2, seq1 + 1)

	def test_item_creation_auto_sku(self) -> None:
		"""Item gets auto-generated SKU on insert."""
		item = frappe.get_doc({
			"doctype": "NexPort Item",
			"item_name": "Auto SKU Test",
			"customs_name": "Test Product",
			"supplier": None,
			"category": "Widgets",
			"sub_category": "Small",
		})
		item.insert()
		self.assertIsNotNone(item.sku)
		self.assertIn("WID-SMA", item.sku)
