# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Stock Service — Material Request auto-generation scheduler.

Runs daily. Checks all Items where stock_physical < reorder_level
and reorder_level > 0. Creates a Material Request for items that
do not already have an Open MR.
"""

from __future__ import annotations

import frappe


def auto_generate_material_requests() -> None:
	"""Scheduled daily task: create Material Requests for items below reorder level."""
	items = frappe.db.sql(
		"""
		SELECT name, stock_physical, reorder_level, reorder_qty
		FROM `tabItem`
		WHERE reorder_level > 0
		  AND stock_physical < reorder_level
		""",
		as_dict=True,
	)

	created = 0
	for item in items:
		# Skip if an Open MR already exists for this item
		existing = frappe.db.exists(
			"Material Request",
			{"item": item.name, "status": "Open"},
		)
		if existing:
			continue

		mr = frappe.get_doc({
			"doctype": "Material Request",
			"item": item.name,
			"required_qty": item.reorder_qty or 1,
			"current_stock": item.stock_physical,
			"reorder_level": item.reorder_level,
			"status": "Open",
		})
		mr.insert(ignore_permissions=True)
		frappe.db.commit()
		created += 1

	if created:
		frappe.logger().info(f"NexPort stock_service: created {created} Material Request(s)")
