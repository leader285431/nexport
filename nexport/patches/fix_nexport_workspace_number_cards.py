# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Patch: backfill NexPort workspace number cards."""

from __future__ import annotations

import frappe

PATCH_TITLE = "nexport.patches.fix_nexport_workspace_number_cards"


def execute() -> None:
    """Ensure NexPort workspace has valid number_card_name rows."""
    workspace_name = "NexPort"
    if not frappe.db.exists("Workspace", workspace_name):
        return

    desired = [
        "Inventory Dual-Track Value",
        "Pending Customs Gaps",
        "Pending AP Invoices",
    ]

    try:
        rows = frappe.get_all(
            "Workspace Number Card",
            filters={"parent": workspace_name},
            fields=["name", "label"],
            order_by="idx asc",
            limit_page_length=100,
        )
        if not rows:
            return

        existing = {r["label"]: r["name"] for r in rows if r.get("label")}
        for card_label in desired:
            if card_label in existing:
                frappe.db.set_value(
                    "Workspace Number Card",
                    existing[card_label],
                    "number_card_name",
                    card_label,
                    update_modified=False,
                )
            else:
                frappe.log_error(f"Number card not found: {card_label}", PATCH_TITLE)
    except Exception:
        frappe.log_error(frappe.get_traceback(), PATCH_TITLE)
        raise
