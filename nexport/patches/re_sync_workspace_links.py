# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Patch: re-sync workspace links to remove ALL legacy sales DocType name variants."""

from __future__ import annotations

import json

import frappe

PATCH_TITLE = "nexport.patches.re_sync_workspace_links"
WORKSPACE_NAME = "NexPort"

# Superset of sync_workspace_links_after_sales_doctype_rename — covers both
# "NexPort" and "Nexport" (lower-p) legacy name variants.
LEGACY_LINK_RENAMES = {
	"Nexport Quote": "Quote",
	"Nexport Sales Order": "Sales Order",
	"Nexport Delivery Note": "Delivery Note",
	"NexPort Quote": "Quote",
	"NexPort Sales Order": "Sales Order",
	"NexPort Delivery Note": "Delivery Note",
}


def _get_value(row, key: str):  # noqa: ANN001
	if isinstance(row, dict):
		return row.get(key)
	return getattr(row, key, None)


def _set_value(row, key: str, value: str) -> None:  # noqa: ANN001
	if isinstance(row, dict):
		row[key] = value
		return
	setattr(row, key, value)


def _sync_row_links(rows) -> bool:  # noqa: ANN001
	changed = False
	for row in rows or []:
		link_to = _get_value(row, "link_to")
		if link_to not in LEGACY_LINK_RENAMES:
			continue
		_set_value(row, "link_to", LEGACY_LINK_RENAMES[link_to])
		changed = True
	return changed


def _sync_content_json(raw_content: str) -> tuple[str, bool]:
	if not raw_content:
		return raw_content, False

	try:
		blocks = json.loads(raw_content)
	except (TypeError, ValueError):
		return raw_content, False

	changed = False
	for block in blocks:
		if not isinstance(block, dict):
			continue
		data = block.get("data")
		if not isinstance(data, dict):
			continue
		link_to = data.get("link_to")
		if link_to in LEGACY_LINK_RENAMES:
			data["link_to"] = LEGACY_LINK_RENAMES[link_to]
			changed = True

	if not changed:
		return raw_content, False

	return json.dumps(blocks, separators=(",", ":")), True


def execute() -> None:
	"""Re-sync workspace links to remove ALL legacy sales DocType name variants.

	Idempotent: safe to run multiple times. Extends and supersedes
	sync_workspace_links_after_sales_doctype_rename by also covering the
	"NexPort" (capital-P) prefix variants.
	"""
	try:
		if not frappe.db.exists("Workspace", WORKSPACE_NAME):
			return

		workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
		changed = _sync_row_links(getattr(workspace, "links", []))
		changed = _sync_row_links(getattr(workspace, "shortcuts", [])) or changed

		content, content_changed = _sync_content_json(getattr(workspace, "content", ""))
		if content_changed:
			workspace.content = content
			changed = True

		if changed:
			workspace.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), PATCH_TITLE)
		raise
