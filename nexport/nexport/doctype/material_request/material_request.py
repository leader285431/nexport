# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class MaterialRequest(Document):
	def before_save(self) -> None:
		"""Populate current_stock from Item."""
		if self.item:
			self.current_stock = frappe.db.get_value("Item", self.item, "stock_physical") or 0

	@frappe.whitelist()
	def create_purchase_order(self) -> str:
		"""Convert this Material Request into a Purchase Order.

		Returns:
			Name of the created Purchase Order.

		Raises:
			frappe.ValidationError: If already linked to a PO or not in Open status.
		"""
		frappe.has_permission("Purchase Order", ptype="create", raise_exception=True)

		if self.purchase_order:
			frappe.throw(f"Already linked to Purchase Order {self.purchase_order}")
		if self.status != "Open":
			frappe.throw(f"Cannot create PO from a {self.status} Material Request")

		po = frappe.get_doc({
			"doctype": "Purchase Order",
			"items": [
				{
					"doctype": "Purchase Order Item",
					"item_code": self.item,
					"qty": self.required_qty,
				}
			],
		})
		po.insert(ignore_permissions=True)

		frappe.db.set_value("Material Request", self.name, {
			"purchase_order": po.name,
			"status": "Ordered",
		})
		return po.name
