# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Inventory Service -- Dual-track receipt logic (Rule 1).

Handles formal and informal shipment receipt with atomic stock updates.
Formal receipts increase both physical and declared stock. Informal
receipts increase only physical stock and create Customs Gaps for later
FIFO resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

from nexport.repositories.gap_repository import create_gap
from nexport.repositories.item_repository import update_stock_atomic
from nexport.repositories.po_repository import (
    POItemRecord,
    POStatusAndInvoice,
    get_po_item,
    get_po_status_and_invoice,
    increment_received_qty,
)
from nexport.repositories.shipment_repository import mark_receipt_processed

if TYPE_CHECKING:
    from frappe.model.document import Document


ALLOWED_PO_RECEIPT_STATUSES = frozenset({"Ordered", "Confirmed", "Shipped", "Received"})
DEFAULT_GAP_DEADLINE_DAYS = 30
ERR_SHIPMENT_NOT_SUBMITTED = _("Shipment must be submitted before receipt")
ERR_SHIPMENT_NO_ITEMS = _("Shipment has no items")
ERR_FORMAL_RATE_REQUIRED = _("Formal shipment requires customs_exchange_rate > 0")
ERR_PO_ITEM_INVOICE_FIELD_MISSING = _(
    "Purchase Order missing invoice_id field configuration; cannot process receipt"
)
ERR_MISSING_CUSTOMS_NAME_TEMPLATE = _(
    "Item {0} has no customs_name. Required for informal receipt (Gap FIFO matching)."
)
ERR_RECEIPT_FAILED_TEMPLATE = _("Shipment receipt failed. Error logged. Ref: {0}")
ERR_OVER_RECEIPT_RETRY = "Logged for retry"
LOG_TITLE_RECEIPT_FAILED = "Receipt failed: {shipment_id}"
LOG_TITLE_OVER_RECEIPT_FAILED = "Over-receipt failed: PO {po_id}, Shipment {shipment_id}"
MSG_ALREADY_PROCESSED = "Already processed"


class ReceiptItemResult(TypedDict):
    """Processed shipment item payload."""

    item: str
    qty: float
    po: str


class OverReceiptItemResult(TypedDict):
    """Over-receipt item payload for procurement handler."""

    item: str
    over_qty: float


class OverReceiptErrorResult(TypedDict):
    """Fallback payload when over-receipt handling fails."""

    success: bool
    error: str


class OverReceiptHandledResult(TypedDict, total=False):
    """Successful over-receipt handler payload."""

    success: bool
    message: str
    supplementary_po: str | None
    supplementary_invoice: str
    already_existed: bool


OverReceiptResult = OverReceiptHandledResult | OverReceiptErrorResult
OverReceiptResultsMap = dict[str, OverReceiptResult]


class ProcessReceiptResult(TypedDict, total=False):
    """Response payload for process_receipt."""

    success: bool
    items: list[ReceiptItemResult]
    over_receipts: OverReceiptResultsMap
    message: str
    already_existed: bool


@frappe.whitelist()
def process_receipt(shipment_id: str) -> ProcessReceiptResult:
    """Process dual-track receipt for a shipment.

    Formal receipts increase both physical and declared stock.
    Informal receipts increase only physical stock and create Customs Gaps.

    Trigger: Shipment workflow transitions to Released.
    Idempotency: receipt_processed flag prevents double execution.

    Args:
        shipment_id: Shipment document name

    Returns:
        Dict with success status, processed items, and over-receipt results
    """
    frappe.has_permission("Shipment", "write", throw=True)

    shipment = frappe.get_doc("Shipment", shipment_id)

    if shipment.receipt_processed:
        return _build_already_processed_result()

    customs_name_by_item = _validate_shipment_for_receipt(shipment)

    gap_deadline_days = (
        frappe.db.get_single_value("NexPort Settings", "default_gap_deadline_days")
        or DEFAULT_GAP_DEADLINE_DAYS
    )

    try:
        results = _execute_receipt_transaction(
            shipment,
            shipment_id,
            gap_deadline_days,
            customs_name_by_item=customs_name_by_item,
        )
        mark_receipt_processed(shipment_id)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title=LOG_TITLE_RECEIPT_FAILED.format(shipment_id=shipment_id),
        )
        frappe.throw(ERR_RECEIPT_FAILED_TEMPLATE.format(shipment_id))

    over_receipt_results = _check_over_receipts(shipment, shipment_id)

    return _build_process_receipt_result(results, over_receipt_results)


def _build_already_processed_result() -> ProcessReceiptResult:
    """Build idempotent response payload for already-processed shipment."""
    return {
        "success": True,
        "message": MSG_ALREADY_PROCESSED,
        "already_existed": True,
    }


def _build_process_receipt_result(
    items: list[ReceiptItemResult],
    over_receipts: OverReceiptResultsMap,
) -> ProcessReceiptResult:
    """Build response payload for process_receipt.

    Receipt posting can succeed while over-receipt compensation fails for one
    or more POs. Surface that partial failure to callers instead of reporting
    a full success.
    """
    has_over_receipt_errors = _has_over_receipt_failures(over_receipts)
    result: ProcessReceiptResult = {
        "success": not has_over_receipt_errors,
        "items": items,
        "over_receipts": over_receipts,
    }
    if has_over_receipt_errors:
        result["message"] = _("Receipt posted, but over-receipt follow-up failed for one or more POs")
    return result


def _has_over_receipt_failures(over_receipts: OverReceiptResultsMap) -> bool:
    """Return True when any over-receipt handler reports failure."""
    return any(not bool(result.get("success")) for result in over_receipts.values())


def _throw_validation(message: str) -> None:
    """Raise a standardized validation error."""
    frappe.throw(message, exc=frappe.ValidationError)


def _missing_customs_name_error(item_code: str) -> str:
    """Build validation message for informal receipt without customs_name."""
    return ERR_MISSING_CUSTOMS_NAME_TEMPLATE.format(item_code)


def _validate_shipment_for_receipt(shipment: Document) -> dict[str, str]:
    """Validate shipment is eligible for receipt processing.

    Args:
        shipment: Shipment document instance

    Returns:
        Mapping of item code to customs_name (only for informal shipments)

    Raises:
        frappe.ValidationError: If any validation fails
    """
    if shipment.docstatus != 1:
        _throw_validation(ERR_SHIPMENT_NOT_SUBMITTED)

    if not shipment.items:
        _throw_validation(ERR_SHIPMENT_NO_ITEMS)

    po_data_by_id: dict[str, POStatusAndInvoice | None] = {}
    customs_name_by_item: dict[str, str] = {}

    for item_row in shipment.items:
        _validate_item_row_for_receipt(item_row)
        po_data = _get_po_data_cached(item_row.po, po_data_by_id)
        _validate_po_data_for_receipt(item_row.po, po_data)

    _validate_formal_exchange_rate(shipment)
    _validate_informal_customs_names(shipment, customs_name_by_item)

    return customs_name_by_item


def _validate_item_row_for_receipt(item_row: Any) -> None:
    """Validate required per-row fields before PO checks."""
    if not item_row.quantity or flt(item_row.quantity) <= 0:
        _throw_validation(_("Invalid quantity for item {0}").format(item_row.item))
    if not item_row.po:
        _throw_validation(_("Shipment item {0} has no linked PO").format(item_row.item))


def _get_po_data_cached(
    po_id: str,
    po_data_by_id: dict[str, POStatusAndInvoice | None],
) -> POStatusAndInvoice | None:
    """Get PO metadata with simple in-memory caching for repeated POs."""
    if po_id not in po_data_by_id:
        po_data_by_id[po_id] = get_po_status_and_invoice(po_id)
    return po_data_by_id[po_id]


def _validate_po_data_for_receipt(po_id: str, po_data: POStatusAndInvoice | None) -> None:
    """Validate PO status and invoice linkage required for receipt processing."""
    if not po_data:
        _throw_validation(_("PO {0} not found").format(po_id))
    po_status = po_data.get("status")
    if po_status not in ALLOWED_PO_RECEIPT_STATUSES:
        _throw_validation(_("PO {0} is in status '{1}', cannot receive").format(po_id, po_status))
    if not po_data.get("invoice_field_exists", True):
        _throw_validation(ERR_PO_ITEM_INVOICE_FIELD_MISSING)
    if not po_data.get("invoice_id"):
        _throw_validation(_("PO {0} missing invoice link; cannot process receipt").format(po_id))


def _validate_formal_exchange_rate(shipment: Document) -> None:
    """Ensure formal shipment has a valid exchange rate."""
    if shipment.is_formal and (
        not shipment.customs_exchange_rate
        or flt(shipment.customs_exchange_rate) <= 0
    ):
        _throw_validation(ERR_FORMAL_RATE_REQUIRED)


def _validate_informal_customs_names(
    shipment: Document,
    customs_name_by_item: dict[str, str],
) -> None:
    """Ensure every informal shipment item has a customs_name for FIFO gap matching."""
    if shipment.is_formal:
        return

    for item_row in shipment.items:
        customs_name = _resolve_customs_name(item_row.item, customs_name_by_item)
        if not customs_name:
            _throw_validation(_missing_customs_name_error(item_row.item))
        customs_name_by_item[item_row.item] = customs_name


def _execute_receipt_transaction(
    shipment: Document,
    shipment_id: str,
    gap_deadline_days: int,
    customs_name_by_item: dict[str, str] | None = None,
) -> list[ReceiptItemResult]:
    """Execute the core receipt transaction (stock updates + gap creation).

    Called within Frappe's request transaction context.

    Args:
        shipment: Shipment document instance
        shipment_id: Shipment document name
        gap_deadline_days: Days until gap deadline
        customs_name_by_item: Optional item-to-customs-name cache

    Returns:
        List of processed item dicts
    """
    results: list[ReceiptItemResult] = []
    gap_deadline = add_days(today(), gap_deadline_days)

    for item_row in shipment.items:
        qty = flt(item_row.quantity)

        if shipment.is_formal:
            update_stock_atomic(item_row.item, physical_delta=qty, declared_delta=qty)
        else:
            update_stock_atomic(item_row.item, physical_delta=qty, declared_delta=0)

            customs_name = _resolve_customs_name(item_row.item, customs_name_by_item)
            create_gap(
                product=item_row.item,
                shipment=shipment_id,
                po=item_row.po,
                general_name=customs_name,
                gap_qty=qty,
                deadline=gap_deadline,
            )

        increment_received_qty(po=item_row.po, item=item_row.item, qty_delta=qty)
        results.append({"item": item_row.item, "qty": qty, "po": item_row.po})

    return results


def _resolve_customs_name(item_code: str, customs_name_by_item: dict[str, str] | None = None) -> str | None:
    """Resolve customs_name with optional in-memory cache."""
    if customs_name_by_item is not None and item_code in customs_name_by_item:
        return customs_name_by_item[item_code]

    customs_name = frappe.db.get_value("Item", item_code, "customs_name")
    if customs_name_by_item is not None and customs_name:
        customs_name_by_item[item_code] = customs_name
    return customs_name


def _check_over_receipts(
    shipment: Document,
    shipment_id: str,
) -> OverReceiptResultsMap:
    """Check for and handle over-receipts after transaction completes.

    Args:
        shipment: Shipment document instance
        shipment_id: Shipment document name

    Returns:
        Dict mapping PO names to over-receipt handling results
    """
    over_items_by_po = _collect_over_receipt_items(shipment)

    over_receipt_results: OverReceiptResultsMap = {}
    for po_id, over_items in over_items_by_po.items():
        over_receipt_results[po_id] = _handle_over_receipt_for_po(po_id, shipment_id, over_items)

    return over_receipt_results


def _collect_over_receipt_items(shipment: Document) -> dict[str, list[OverReceiptItemResult]]:
    """Build over-receipt payload grouped by PO."""
    over_items_by_po: dict[str, list[OverReceiptItemResult]] = {}
    for item_row in shipment.items:
        po_item: POItemRecord | None = get_po_item(po=item_row.po, item=item_row.item)
        if not po_item:
            continue
        over_qty = flt(po_item.get("received_qty")) - flt(po_item.get("quantity"))
        if over_qty <= 0:
            continue
        over_items_by_po.setdefault(item_row.po, []).append({
            "item": item_row.item,
            "over_qty": over_qty,
        })
    return over_items_by_po


def _handle_over_receipt_for_po(
    po_id: str,
    shipment_id: str,
    over_items: list[OverReceiptItemResult],
) -> OverReceiptResult:
    """Handle over-receipt for one PO with fail-safe error logging."""
    try:
        from nexport.services.procurement_service import handle_over_receipt

        return handle_over_receipt(po_id, shipment_id, over_items)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title=LOG_TITLE_OVER_RECEIPT_FAILED.format(po_id=po_id, shipment_id=shipment_id),
        )
        return {"success": False, "error": ERR_OVER_RECEIPT_RETRY}


def deduct_stock(delivery_note: Document) -> None:
    """Deduct outbound stock when Delivery Note is submitted.

    Normal shipment: deduct physical + declared.
    Lending shipment: deduct physical only.
    """
    if not delivery_note.items:
        frappe.throw(_("Delivery Note has no items"), exc=frappe.ValidationError)

    for row in delivery_note.items:
        qty = flt(row.quantity)
        if qty <= 0:
            frappe.throw(_("Invalid quantity for item {0}").format(row.item), exc=frappe.ValidationError)

        declared_delta = 0 if delivery_note.is_lending else -qty
        update_stock_atomic(
            item_name=row.item,
            physical_delta=-qty,
            declared_delta=declared_delta,
        )


# ---------------------------------------------------------------------------
# Stock Reservation (FR-1.5.12)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_available_stock(item: str) -> dict:
    """Return available (unreserved) dual-track stock for an item.

    Available = total_stock - sum(active_reserved)

    Args:
        item: Item document name

    Returns:
        dict with keys: physical_total, declared_total,
        reserved_physical, reserved_declared,
        available_physical, available_declared
    """
    frappe.has_permission("Item", "read", throw=True)

    row = frappe.db.sql(
        "SELECT stock_physical, stock_declared FROM `tabItem` WHERE name = %s",
        (item,),
        as_dict=True,
    )
    if not row:
        frappe.throw(_("Item {0} not found").format(item), exc=frappe.ValidationError)

    physical_total = flt(row[0].stock_physical)
    declared_total = flt(row[0].stock_declared)

    reserved = frappe.db.sql(
        """
        SELECT COALESCE(SUM(reserved_physical), 0) AS rp,
               COALESCE(SUM(reserved_declared), 0) AS rd
        FROM `tabStock Reservation`
        WHERE item = %s AND status = 'Active'
        """,
        (item,),
        as_dict=True,
    )
    reserved_physical = flt(reserved[0].rp) if reserved else 0.0
    reserved_declared = flt(reserved[0].rd) if reserved else 0.0

    return {
        "physical_total": physical_total,
        "declared_total": declared_total,
        "reserved_physical": reserved_physical,
        "reserved_declared": reserved_declared,
        "available_physical": physical_total - reserved_physical,
        "available_declared": declared_total - reserved_declared,
    }


@frappe.whitelist()
def reserve_stock(item: str, sales_order: str, qty: float) -> dict:
    """Atomically reserve dual-track stock for a Sales Order.

    Prevents over-selling: rejects if available physical stock < qty.
    Reserves equal quantities from both physical and declared tracks.

    Args:
        item: Item document name
        sales_order: Sales Order document name
        qty: Quantity to reserve

    Returns:
        dict with keys: reservation (name), available_physical (after reserve)

    Raises:
        frappe.ValidationError: If insufficient available stock
    """
    frappe.has_permission("Stock Reservation", ptype="create", raise_exception=True)

    qty = flt(qty)
    if qty <= 0:
        frappe.throw(_("Reserve quantity must be positive"), exc=frappe.ValidationError)

    stock = get_available_stock(item)
    if stock["available_physical"] < qty:
        frappe.throw(
            _("Insufficient stock for {0}. Available: {1}, Requested: {2}").format(
                item, stock["available_physical"], qty
            ),
            exc=frappe.ValidationError,
        )

    reservation = frappe.get_doc({
        "doctype": "Stock Reservation",
        "item": item,
        "sales_order": sales_order,
        "reserved_physical": qty,
        "reserved_declared": min(qty, stock["available_declared"]),
        "status": "Active",
    })
    reservation.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "reservation": reservation.name,
        "available_physical": stock["available_physical"] - qty,
    }


@frappe.whitelist()
def release_reservation(reservation: str) -> dict:
    """Release an active Stock Reservation on delivery or SO cancellation.

    Idempotent: no-op if reservation is already Released or Cancelled.

    Args:
        reservation: Stock Reservation document name

    Returns:
        dict with keys: status ("released" or "already_inactive")
    """
    frappe.has_permission("Stock Reservation", ptype="write", raise_exception=True)

    current_status = frappe.db.get_value("Stock Reservation", reservation, "status")
    if not current_status:
        frappe.throw(_("Stock Reservation {0} not found").format(reservation))

    if current_status != "Active":
        return {"status": "already_inactive", "reservation": reservation}

    frappe.db.set_value("Stock Reservation", reservation, "status", "Released")
    frappe.db.commit()
    return {"status": "released", "reservation": reservation}
