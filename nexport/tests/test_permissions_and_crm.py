# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt
from __future__ import annotations

import json
import os
import unittest

_DOCTYPE_DIR = os.path.join(os.path.dirname(__file__), "..", "nexport", "doctype")


def _load_doctype(name: str) -> dict:
	path = os.path.join(_DOCTYPE_DIR, name, name + ".json")
	with open(path, encoding="utf-8") as f:
		return json.load(f)


class TestPermissionMatrix(unittest.TestCase):
	"""Verify DocType JSON permission and permlevel settings."""

	def test_item_cost_fields_permlevel_1(self) -> None:
		doc = _load_doctype("item")
		permlevel1_fields = {
			f["fieldname"]
			for f in doc.get("fields", [])
			if f.get("permlevel", 0) == 1
		}
		for fieldname in ("cost_landed", "cost_declared", "section_cost"):
			self.assertIn(
				fieldname,
				permlevel1_fields,
				f"item.json: '{fieldname}' should have permlevel=1",
			)

	def test_item_warehouse_no_permlevel1(self) -> None:
		doc = _load_doctype("item")
		warehouse_entries = [
			p
			for p in doc.get("permissions", [])
			if p.get("role") == "NexPort Warehouse"
		]
		self.assertTrue(warehouse_entries, "item.json: no permission entry for NexPort Warehouse")
		for entry in warehouse_entries:
			self.assertEqual(
				entry.get("permlevel", 0),
				0,
				f"item.json: NexPort Warehouse entry should only have permlevel=0, got {entry}",
			)

	def test_invoice_financial_fields_permlevel_1(self) -> None:
		doc = _load_doctype("invoice")
		permlevel1_fields = {
			f["fieldname"]
			for f in doc.get("fields", [])
			if f.get("permlevel", 0) == 1
		}
		for fieldname in ("total_amount", "actual_exchange_rate"):
			self.assertIn(
				fieldname,
				permlevel1_fields,
				f"invoice.json: '{fieldname}' should have permlevel=1",
			)

	def test_purchase_order_sales_no_access(self) -> None:
		doc = _load_doctype("purchase_order")
		sales_entries = [
			p
			for p in doc.get("permissions", [])
			if p.get("role") == "NexPort Sales"
		]
		self.assertEqual(
			len(sales_entries),
			0,
			f"purchase_order.json: NexPort Sales should have no permission entry, found {sales_entries}",
		)

	def test_shipment_cost_fields_permlevel_1(self) -> None:
		doc = _load_doctype("shipment")
		permlevel1_fields = {
			f["fieldname"]
			for f in doc.get("fields", [])
			if f.get("permlevel", 0) == 1
		}
		for fieldname in ("freight_cost", "duty_cost", "total_cost_thb"):
			self.assertIn(
				fieldname,
				permlevel1_fields,
				f"shipment.json: '{fieldname}' should have permlevel=1",
			)

	def test_shipment_no_all_role(self) -> None:
		doc = _load_doctype("shipment")
		all_entries = [
			p
			for p in doc.get("permissions", [])
			if p.get("role") == "All"
		]
		self.assertEqual(
			len(all_entries),
			0,
			f"shipment.json: 'All' role should not have a permission entry, found {all_entries}",
		)


class TestCRMActivityDocType(unittest.TestCase):
	"""Verify CRM Activity DocType JSON contract."""

	_JSON_PATH = os.path.join(_DOCTYPE_DIR, "crm_activity", "crm_activity.json")

	def _load(self) -> dict:
		with open(self._JSON_PATH, encoding="utf-8") as f:
			return json.load(f)

	def test_crm_activity_json_exists(self) -> None:
		self.assertTrue(
			os.path.isfile(self._JSON_PATH),
			f"CRM Activity JSON not found at {self._JSON_PATH}",
		)

	def test_crm_activity_naming_series(self) -> None:
		doc = self._load()
		naming_field = next(
			(f for f in doc.get("fields", []) if f.get("fieldname") == "naming_series"),
			None,
		)
		self.assertIsNotNone(naming_field, "crm_activity.json: naming_series field missing")
		options = naming_field.get("options", "")
		self.assertIn(
			"NP-CRM-",
			options,
			f"crm_activity.json: naming_series options should contain 'NP-CRM-', got '{options}'",
		)

	def test_crm_activity_dynamic_link_fields(self) -> None:
		doc = self._load()
		fields_by_name = {f["fieldname"]: f for f in doc.get("fields", [])}

		self.assertIn(
			"related_entity_type",
			fields_by_name,
			"crm_activity.json: 'related_entity_type' field missing",
		)
		self.assertEqual(
			fields_by_name["related_entity_type"].get("fieldtype"),
			"Link",
			"crm_activity.json: 'related_entity_type' should be a Link field",
		)

		self.assertIn(
			"related_entity",
			fields_by_name,
			"crm_activity.json: 'related_entity' field missing",
		)
		self.assertEqual(
			fields_by_name["related_entity"].get("fieldtype"),
			"Dynamic Link",
			"crm_activity.json: 'related_entity' should be a Dynamic Link field",
		)

	def test_crm_activity_type_options(self) -> None:
		doc = self._load()
		type_field = next(
			(f for f in doc.get("fields", []) if f.get("fieldname") == "type"),
			None,
		)
		self.assertIsNotNone(type_field, "crm_activity.json: 'type' field missing")
		options = type_field.get("options", "")
		for expected in ("Call", "Email", "Visit", "Meeting"):
			self.assertIn(
				expected,
				options,
				f"crm_activity.json: type options should include '{expected}'",
			)

	def test_crm_activity_direction_options(self) -> None:
		doc = self._load()
		direction_field = next(
			(f for f in doc.get("fields", []) if f.get("fieldname") == "direction"),
			None,
		)
		self.assertIsNotNone(direction_field, "crm_activity.json: 'direction' field missing")
		options = direction_field.get("options", "")
		for expected in ("Inbound", "Outbound"):
			self.assertIn(
				expected,
				options,
				f"crm_activity.json: direction options should include '{expected}'",
			)

	def test_crm_activity_sales_has_write(self) -> None:
		doc = self._load()
		sales_entry = next(
			(p for p in doc.get("permissions", []) if p.get("role") == "NexPort Sales"),
			None,
		)
		self.assertIsNotNone(
			sales_entry,
			"crm_activity.json: NexPort Sales permission entry missing",
		)
		self.assertEqual(
			sales_entry.get("write"),
			1,
			f"crm_activity.json: NexPort Sales should have write=1, got {sales_entry}",
		)

	def test_crm_activity_warehouse_no_access(self) -> None:
		doc = self._load()
		warehouse_entries = [
			p
			for p in doc.get("permissions", [])
			if p.get("role") == "NexPort Warehouse"
		]
		self.assertEqual(
			len(warehouse_entries),
			0,
			f"crm_activity.json: NexPort Warehouse should have no permission entry, found {warehouse_entries}",
		)


if __name__ == "__main__":
	unittest.main()
