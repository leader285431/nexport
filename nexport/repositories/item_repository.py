# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""
Item Repository — atomic data access for NexPort Item.

Uses atomic SQL (SET col = col + delta) per CONCURRENCY_CONTROL.md §1
to prevent lost-update race conditions on stock/cost fields.
"""

from __future__ import annotations

import frappe


def update_stock_atomic(
	item_name: str,
	physical_delta: float = 0.0,
	declared_delta: float = 0.0,
) -> None:
	"""Atomically update stock fields using SQL col = col + delta.

	Raises:
		frappe.ValidationError: If resulting stock would be negative.
	"""
	if physical_delta == 0.0 and declared_delta == 0.0:
		return

	frappe.db.sql(
		"""
		UPDATE `tabNexPort Item`
		SET
			stock_physical = stock_physical + %(physical_delta)s,
			stock_declared = stock_declared + %(declared_delta)s,
			modified = NOW()
		WHERE name = %(item_name)s
		""",
		{
			"item_name": item_name,
			"physical_delta": physical_delta,
			"declared_delta": declared_delta,
		},
	)

	# Post-update negative stock check
	result = frappe.db.sql(
		"""
		SELECT stock_physical, stock_declared
		FROM `tabNexPort Item`
		WHERE name = %(item_name)s
		""",
		{"item_name": item_name},
		as_dict=True,
	)

	if result:
		row = result[0]
		if row.stock_physical < 0:
			frappe.throw(
				f"Stock (Physical) for {item_name} would become negative: {row.stock_physical}",
				exc=frappe.ValidationError,
			)
		if row.stock_declared < 0:
			frappe.throw(
				f"Stock (Declared) for {item_name} would become negative: {row.stock_declared}",
				exc=frappe.ValidationError,
			)


def update_cost_atomic(
	item_name: str,
	cost_landed_delta: float = 0.0,
	cost_declared_delta: float = 0.0,
) -> None:
	"""Atomically update cost fields using SQL col = col + delta."""
	if cost_landed_delta == 0.0 and cost_declared_delta == 0.0:
		return

	frappe.db.sql(
		"""
		UPDATE `tabNexPort Item`
		SET
			cost_landed = cost_landed + %(cost_landed_delta)s,
			cost_declared = cost_declared + %(cost_declared_delta)s,
			modified = NOW()
		WHERE name = %(item_name)s
		""",
		{
			"item_name": item_name,
			"cost_landed_delta": cost_landed_delta,
			"cost_declared_delta": cost_declared_delta,
		},
	)
