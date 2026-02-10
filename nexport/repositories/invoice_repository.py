# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""
Invoice Repository — data access for NexPort Invoice.

Stub for future payment queries and AP/AR operations.
"""

from __future__ import annotations

import frappe


def get_unpaid_invoices(entity_type: str, entity: str) -> list[dict]:
	"""Get all unpaid/partial invoices for an entity."""
	return frappe.get_all(
		"NexPort Invoice",
		filters={
			"entity_type": entity_type,
			"entity": entity,
			"status": ["in", ["Unpaid", "Partial", "Overdue"]],
		},
		fields=["name", "total_amount", "status", "invoice_date", "currency"],
		order_by="invoice_date asc",
	)
