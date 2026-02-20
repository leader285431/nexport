# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Customs Service -- FIFO customs gap resolution (Rule 3)."""

from __future__ import annotations

from collections import defaultdict
from typing import TypedDict

import frappe
from frappe import _
from frappe.utils import flt

from nexport.repositories.gap_repository import get_pending_gaps_for_update, update_gap_resolved
from nexport.repositories.item_repository import update_stock_atomic


_LOCK_TIMEOUT_MARKERS = ("lock wait timeout exceeded", "deadlock found")


class ResolveGapsResult(TypedDict):
	"""Result payload for FIFO gap resolution."""

	resolved_count: int
	remaining_qty: float
	gaps_affected: list[str]


def resolve_gaps(
	customs_name: str,
	declaration_qty: float,
	declaration_ref: str,
) -> ResolveGapsResult:
	"""Resolve pending customs gaps FIFO by customs_name (Rule 3).

	Locks gaps via SELECT ... FOR UPDATE, consumes declaration quantity
	oldest-first, updates gap status and Item.stock_declared atomically.

	Args:
		customs_name: The general_name (customs_name) to match gaps against
		declaration_qty: Total quantity being declared
		declaration_ref: Customs declaration reference number

	Returns:
		ResolveGapsResult with resolved_count, remaining_qty, gaps_affected

	Raises:
		frappe.ValidationError: On lock timeout — caller should retry
	"""
	qty_to_consume = flt(declaration_qty)
	if qty_to_consume <= 0:
		frappe.msgprint(
			_("Declaration quantity must be greater than 0."),
			indicator="orange",
			alert=True,
		)
		return {"resolved_count": 0, "remaining_qty": 0.0, "gaps_affected": []}

	try:
		frappe.db.begin()
		gaps = get_pending_gaps_for_update(customs_name)
		result = _consume_gaps(gaps, qty_to_consume, declaration_ref)
		frappe.db.commit()
		return result
	except Exception as exc:
		frappe.db.rollback()
		lowered = str(exc).lower()
		if any(marker in lowered for marker in _LOCK_TIMEOUT_MARKERS):
			frappe.throw(_("Please try again"), exc=frappe.ValidationError)
		raise


def _consume_gaps(
	gaps: list[dict],
	qty_to_consume: float,
	declaration_ref: str,
) -> ResolveGapsResult:
	"""Inner FIFO consumption loop. Must run within an active transaction."""
	remaining = qty_to_consume
	gaps_affected: list[str] = []
	item_declared_delta: dict[str, float] = defaultdict(float)

	for gap in gaps:
		if remaining <= 0:
			break
		gap_remaining = flt(gap["gap_qty"]) - flt(gap["resolved_qty"])
		if gap_remaining <= 0:
			continue

		to_resolve = min(gap_remaining, remaining)
		will_fully_resolve = (flt(gap["resolved_qty"]) + to_resolve) >= flt(gap["gap_qty"])
		new_status = "Resolved" if will_fully_resolve else "Partial"

		update_gap_resolved(gap["name"], to_resolve, new_status, declaration_ref)
		remaining -= to_resolve
		gaps_affected.append(gap["name"])
		item_declared_delta[gap["product"]] += to_resolve

	# Lock ordering: items by name ASC (CONCURRENCY_CONTROL.md §4)
	for item_name in sorted(item_declared_delta):
		update_stock_atomic(item_name, declared_delta=item_declared_delta[item_name])

	if remaining > 0:
		frappe.msgprint(
			_("Declaration quantity exceeds available gaps. Unmatched quantity: {0}").format(remaining),
			indicator="orange",
			alert=True,
		)

	return {
		"resolved_count": len(gaps_affected),
		"remaining_qty": remaining,
		"gaps_affected": gaps_affected,
	}
