# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Gap Repository -- Data access layer for Customs Gap.

Provides atomic operations for gap creation and FIFO resolution.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import frappe
from frappe.utils import flt


class PendingGapRecord(TypedDict):
    """Locked gap row used during FIFO resolution."""

    name: str
    product: str
    gap_qty: float
    resolved_qty: float


GapStatus = Literal["Pending", "Partial", "Resolved"]

_SELECT_PENDING_GAPS_SQL = """
    SELECT name, product, gap_qty, resolved_qty
    FROM `tabCustoms Gap`
    WHERE general_name = %(name)s AND status IN ('Pending', 'Partial')
    ORDER BY creation ASC
    FOR UPDATE
"""

_UPDATE_GAP_RESOLVED_SQL = """
    UPDATE `tabCustoms Gap`
    SET resolved_qty = resolved_qty + %(qty)s,
        status = %(status)s,
        resolution_ref = %(resolution_ref)s,
        modified = NOW()
    WHERE name = %(gap_id)s
"""


def create_gap(
    product: str,
    shipment: str,
    po: str,
    general_name: str,
    gap_qty: float,
    deadline: str,
) -> str:
    """Create a new Customs Gap record.

    Args:
        product: Item name
        shipment: Shipment name
        po: Purchase Order name
        general_name: Customs name (from Item.customs_name)
        gap_qty: Quantity of the gap
        deadline: Deadline date for resolution

    Returns:
        Name of the created gap document
    """
    gap = frappe.get_doc({
        "doctype": "Customs Gap",
        "product": product,
        "shipment": shipment,
        "po": po,
        "general_name": general_name,
        "gap_qty": flt(gap_qty),
        "resolved_qty": 0,
        "status": "Pending",
        "deadline": deadline,
    })
    gap.insert(ignore_permissions=True)
    return gap.name


def get_pending_gaps_for_update(customs_name: str) -> list[PendingGapRecord]:
    """Fetch pending/partial gaps for a customs name with row-level locks.

    Uses SELECT ... FOR UPDATE to prevent double-spend during FIFO resolution.
    Should run within an active transaction/savepoint context.

    Args:
        customs_name: The general_name to match gaps against

    Returns:
        List of gap dicts ordered by creation ASC (oldest first for FIFO)
    """
    return frappe.db.sql(_SELECT_PENDING_GAPS_SQL, {"name": customs_name}, as_dict=True)


def update_gap_resolved(
    gap_name: str,
    resolved_qty: float,
    new_status: GapStatus,
    resolution_ref: str = "",
) -> None:
    """Atomically update a gap's resolved quantity, status, and resolution ref.

    Args:
        gap_name: Name of the gap document
        resolved_qty: Additional quantity resolved (delta, not absolute)
        new_status: New status ('Partial' or 'Resolved')
        resolution_ref: Customs declaration reference (stored for audit trail)
    """
    frappe.db.sql(
        _UPDATE_GAP_RESOLVED_SQL,
        {"qty": flt(resolved_qty), "status": new_status, "gap_id": gap_name, "resolution_ref": resolution_ref},
    )
