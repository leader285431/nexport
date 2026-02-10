# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

from frappe.model.document import Document


def compute_line_totals(doc: Document, child_field: str = "items") -> None:
	"""Compute row amounts and document total for any doc with line items.

	Each child row must have `quantity`, `unit_price`, and `amount` fields.
	The parent doc must have a `total_amount` field.
	"""
	total = 0.0
	for row in getattr(doc, child_field, []):
		row.amount = (row.quantity or 0) * (row.unit_price or 0)
		total += row.amount
	doc.total_amount = total
