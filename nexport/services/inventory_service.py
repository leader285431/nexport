# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""
Inventory Service — handles stock deduction/restoration for delivery notes.

Delegates to item_repository for atomic SQL operations per CONCURRENCY_CONTROL.md §1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe

from nexport.repositories.item_repository import update_stock_atomic

if TYPE_CHECKING:
	from nexport.nexport.doctype.nexport_delivery_note.nexport_delivery_note import (
		NexPortDeliveryNote,
	)


def deduct_stock(dn: NexPortDeliveryNote) -> None:
	"""Deduct stock for all items in a Delivery Note.

	- Normal: deduct both physical and declared
	- Lending: deduct only physical
	"""
	for row in dn.items:
		# Validate physical stock before deduction
		current = frappe.db.get_value(
			"NexPort Item", row.item, "stock_physical"
		)
		if (current or 0) < row.quantity:
			frappe.throw(
				f"Insufficient physical stock for {row.item}: "
				f"available {current}, requested {row.quantity}"
			)

		physical_delta = -row.quantity
		declared_delta = 0.0 if dn.is_lending else -row.quantity

		update_stock_atomic(
			item_name=row.item,
			physical_delta=physical_delta,
			declared_delta=declared_delta,
		)


def restore_stock(dn: NexPortDeliveryNote) -> None:
	"""Restore stock when a Delivery Note is cancelled (reverse of deduct)."""
	for row in dn.items:
		physical_delta = row.quantity
		declared_delta = 0.0 if dn.is_lending else row.quantity

		update_stock_atomic(
			item_name=row.item,
			physical_delta=physical_delta,
			declared_delta=declared_delta,
		)
