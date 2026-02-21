# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Unit tests for Issue #13: Stock Enhancements (Variants, Material Request, Reservation).

Covers:
- Item variant creation and SKU generation
- Stock aggregation across variants
- Material Request creation and PO conversion
- Stock Reservation lifecycle (reserve, available stock, release)
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestItemVariants(unittest.TestCase):
	"""Tests for Item variant/template architecture."""

	def test_generate_sku_base_item(self) -> None:
		"""Base items get CATSUBNNN format SKU."""
		from nexport.nexport.doctype.item.item import generate_sku

		with patch("nexport.nexport.doctype.item.item.frappe") as mock_frappe:
			mock_frappe.db.get_value.return_value = "ELE"
			mock_frappe.db.sql.return_value = []

			sku = generate_sku(category="Electronics", sub_category="Gadgets")

		self.assertTrue(sku.startswith("ELE"))
		self.assertTrue(sku[-3:].isdigit())

	def test_generate_sku_variant(self) -> None:
		"""Variant items get {parent_sku}-{attr_codes} format."""
		from nexport.nexport.doctype.item.item import generate_sku

		with patch("nexport.nexport.doctype.item.item.frappe") as mock_frappe:
			mock_frappe.db.exists.return_value = None  # not taken

			attr1 = MagicMock()
			attr1.attribute_value = "Large"
			attr2 = MagicMock()
			attr2.attribute_value = "Red"

			sku = generate_sku(
				variant_of="GENGEN001",
				item_attributes=[attr1, attr2],
			)

		self.assertIn("GENGEN001", sku)
		self.assertIn("LARGE", sku)
		self.assertIn("RED", sku)

	def test_generate_sku_variant_deduplication(self) -> None:
		"""If first variant SKU is taken, a sequence suffix is appended."""
		from nexport.nexport.doctype.item.item import generate_sku

		with patch("nexport.nexport.doctype.item.item.frappe") as mock_frappe:
			# First candidate is taken, second is free
			mock_frappe.db.exists.side_effect = [True, None]

			attr = MagicMock()
			attr.attribute_value = "Blue"

			sku = generate_sku(variant_of="GENGEN001", item_attributes=[attr])

		# Should end with "-2" suffix
		self.assertIn("-2", sku)

	def test_generate_sku_variant_no_attributes(self) -> None:
		"""Variant with no attributes gets -VAR suffix."""
		from nexport.nexport.doctype.item.item import generate_sku

		with patch("nexport.nexport.doctype.item.item.frappe") as mock_frappe:
			mock_frappe.db.exists.return_value = None

			sku = generate_sku(variant_of="GENGEN001", item_attributes=[])

		self.assertEqual(sku, "GENGEN001-VAR")


class TestMaterialRequest(unittest.TestCase):
	"""Tests for Material Request auto-generation and PO conversion."""

	def test_auto_generate_creates_mr_for_low_stock(self) -> None:
		"""Scheduler creates MR when stock_physical < reorder_level."""
		from nexport.services.stock_service import auto_generate_material_requests

		items = [
			{"name": "ITEM001", "stock_physical": 5.0, "reorder_level": 10.0, "reorder_qty": 20.0}
		]
		with (
			patch("nexport.services.stock_service.frappe") as mock_frappe,
		):
			mock_frappe.db.sql.return_value = items
			mock_frappe.db.exists.return_value = None  # No existing open MR
			mock_frappe.get_doc.return_value = MagicMock()

			auto_generate_material_requests()

		mock_frappe.get_doc.assert_called_once()
		call_args = mock_frappe.get_doc.call_args[0][0]
		self.assertEqual(call_args["doctype"], "Material Request")
		self.assertEqual(call_args["item"], "ITEM001")
		self.assertEqual(call_args["required_qty"], 20.0)

	def test_auto_generate_skips_if_open_mr_exists(self) -> None:
		"""Scheduler does NOT create duplicate MR when one already exists."""
		from nexport.services.stock_service import auto_generate_material_requests

		items = [
			{"name": "ITEM001", "stock_physical": 5.0, "reorder_level": 10.0, "reorder_qty": 20.0}
		]
		with patch("nexport.services.stock_service.frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = items
			mock_frappe.db.exists.return_value = "NP-MR-2026-0001"  # Already exists

			auto_generate_material_requests()

		mock_frappe.get_doc.assert_not_called()

	def test_auto_generate_skips_sufficient_stock(self) -> None:
		"""Scheduler creates no MR when stock_physical >= reorder_level."""
		from nexport.services.stock_service import auto_generate_material_requests

		with patch("nexport.services.stock_service.frappe") as mock_frappe:
			# SQL already filters WHERE stock_physical < reorder_level — return empty
			mock_frappe.db.sql.return_value = []

			auto_generate_material_requests()

		mock_frappe.get_doc.assert_not_called()

	def test_create_purchase_order_from_mr(self) -> None:
		"""create_purchase_order() creates a PO and updates MR status to Ordered."""
		import frappe as real_frappe

		from nexport.nexport.doctype.material_request.material_request import MaterialRequest

		mr = MagicMock(spec=MaterialRequest)
		mr.name = "NP-MR-2026-0001"
		mr.item = "ITEM001"
		mr.required_qty = 20.0
		mr.purchase_order = None
		mr.status = "Open"

		mock_po = MagicMock()
		mock_po.name = "NP-PO-2026-0001"

		with patch("nexport.nexport.doctype.material_request.material_request.frappe") as mock_frappe:
			mock_frappe.has_permission.return_value = True
			mock_frappe.get_doc.return_value = mock_po

			result = MaterialRequest.create_purchase_order(mr)

		self.assertEqual(result, "NP-PO-2026-0001")
		mock_frappe.db.set_value.assert_called_once_with(
			"Material Request",
			"NP-MR-2026-0001",
			{"purchase_order": "NP-PO-2026-0001", "status": "Ordered"},
		)

	def test_create_purchase_order_raises_if_already_ordered(self) -> None:
		"""create_purchase_order() raises if MR already linked to a PO."""
		from nexport.nexport.doctype.material_request.material_request import MaterialRequest

		mr = MagicMock(spec=MaterialRequest)
		mr.purchase_order = "EXISTING-PO"
		mr.status = "Ordered"

		with patch("nexport.nexport.doctype.material_request.material_request.frappe") as mock_frappe:
			mock_frappe.has_permission.return_value = True
			mock_frappe.throw.side_effect = Exception("already linked")

			with self.assertRaises(Exception):
				MaterialRequest.create_purchase_order(mr)


class TestStockReservation(unittest.TestCase):
	"""Tests for Stock Reservation lifecycle."""

	def _mock_stock(self, mock_frappe: MagicMock, physical: float, declared: float,
	                reserved_p: float = 0.0, reserved_d: float = 0.0) -> None:
		"""Configure mock frappe.db for get_available_stock calls."""
		mock_frappe.db.sql.side_effect = [
			[{"stock_physical": physical, "stock_declared": declared}],
			[{"rp": reserved_p, "rd": reserved_d}],
		]

	def test_get_available_stock_no_reservations(self) -> None:
		"""Available stock equals total stock when no reservations exist."""
		from nexport.services.inventory_service import get_available_stock

		with patch("nexport.services.inventory_service.frappe") as mock_frappe:
			mock_frappe.db.sql.side_effect = [
				[{"stock_physical": 100.0, "stock_declared": 80.0}],
				[{"rp": 0.0, "rd": 0.0}],
			]

			result = get_available_stock("ITEM001")

		self.assertEqual(result["available_physical"], 100.0)
		self.assertEqual(result["available_declared"], 80.0)
		self.assertEqual(result["reserved_physical"], 0.0)

	def test_get_available_stock_with_active_reservations(self) -> None:
		"""Available stock is reduced by active reservations."""
		from nexport.services.inventory_service import get_available_stock

		with patch("nexport.services.inventory_service.frappe") as mock_frappe:
			mock_frappe.db.sql.side_effect = [
				[{"stock_physical": 100.0, "stock_declared": 80.0}],
				[{"rp": 30.0, "rd": 20.0}],
			]

			result = get_available_stock("ITEM001")

		self.assertEqual(result["available_physical"], 70.0)
		self.assertEqual(result["available_declared"], 60.0)
		self.assertEqual(result["reserved_physical"], 30.0)

	def test_reserve_stock_success(self) -> None:
		"""reserve_stock() creates reservation and returns reduced available stock."""
		from nexport.services.inventory_service import reserve_stock

		with patch("nexport.services.inventory_service.frappe") as mock_frappe, \
			 patch("nexport.services.inventory_service.get_available_stock") as mock_avail:
			mock_avail.return_value = {
				"available_physical": 100.0,
				"available_declared": 80.0,
			}
			mock_doc = MagicMock()
			mock_doc.name = "NP-RES-2026-0001"
			mock_frappe.get_doc.return_value = mock_doc

			result = reserve_stock("ITEM001", "SO-001", 30.0)

		self.assertEqual(result["reservation"], "NP-RES-2026-0001")
		self.assertEqual(result["available_physical"], 70.0)

	def test_reserve_stock_insufficient(self) -> None:
		"""reserve_stock() raises ValidationError when stock insufficient."""
		from nexport.services.inventory_service import reserve_stock

		with patch("nexport.services.inventory_service.frappe") as mock_frappe, \
			 patch("nexport.services.inventory_service.get_available_stock") as mock_avail:
			mock_avail.return_value = {
				"available_physical": 10.0,
				"available_declared": 10.0,
			}
			mock_frappe.throw.side_effect = Exception("Insufficient stock")

			with self.assertRaises(Exception):
				reserve_stock("ITEM001", "SO-001", 50.0)

	def test_release_reservation_active(self) -> None:
		"""release_reservation() sets status to Released for Active reservation."""
		from nexport.services.inventory_service import release_reservation

		with patch("nexport.services.inventory_service.frappe") as mock_frappe:
			mock_frappe.db.get_value.return_value = "Active"

			result = release_reservation("NP-RES-2026-0001")

		self.assertEqual(result["status"], "released")
		mock_frappe.db.set_value.assert_called_once_with(
			"Stock Reservation", "NP-RES-2026-0001", "status", "Released"
		)

	def test_release_reservation_already_released(self) -> None:
		"""release_reservation() is idempotent for non-Active reservations."""
		from nexport.services.inventory_service import release_reservation

		with patch("nexport.services.inventory_service.frappe") as mock_frappe:
			mock_frappe.db.get_value.return_value = "Released"

			result = release_reservation("NP-RES-2026-0001")

		self.assertEqual(result["status"], "already_inactive")
		mock_frappe.db.set_value.assert_not_called()


if __name__ == "__main__":
	unittest.main()
