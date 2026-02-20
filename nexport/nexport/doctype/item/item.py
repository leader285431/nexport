# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document

from nexport.constants import DEFAULT_FALLBACK_CODE, SETTINGS_DOCTYPE


class Item(Document):
	def before_insert(self) -> None:
		if not self.sku:
			self.sku = generate_sku(
				category=self.category,
				sub_category=self.sub_category,
			)

		if not self.markup_multiplier:
			settings = frappe.get_single(SETTINGS_DOCTYPE)
			self.markup_multiplier = settings.default_markup_multiplier or 1.0

	def on_trash(self) -> None:
		"""Retire the SKU so it can never be reused."""
		if self.name and frappe.db.exists("DocType", "Retired SKU"):
			frappe.get_doc({
				"doctype": "Retired SKU",
				"sku": self.name,
				"retired_on": frappe.utils.today(),
				"original_item_name": self.item_name or "",
			}).insert(ignore_permissions=True)


def generate_sku(
	category: str | None = None,
	sub_category: str | None = None,
) -> str:
	"""Generate a unique SKU in the format CATSUBNNN (no separators).

	The sequence number is the lowest positive integer not already used by
	either an active Item or a Retired SKU with the same prefix.
	"""
	cat_code = _get_category_code(category)
	sub_code = _get_subcategory_code(sub_category)
	prefix = f"{cat_code}{sub_code}"

	used = _get_used_sequence_numbers(prefix)

	n = 1
	while n in used:
		n += 1
	return f"{prefix}{n:03d}"


def _get_category_code(category: str | None) -> str:
	if not category:
		return DEFAULT_FALLBACK_CODE
	code = frappe.db.get_value("Item Category", category, "code")
	return code or DEFAULT_FALLBACK_CODE


def _get_subcategory_code(sub_category: str | None) -> str:
	if not sub_category:
		return DEFAULT_FALLBACK_CODE
	code = frappe.db.get_value("Item Subcategory", sub_category, "code")
	return code or DEFAULT_FALLBACK_CODE


def _table_exists(table_name: str) -> bool:
	rows = frappe.db.sql(
		"""
		SELECT 1 FROM information_schema.tables
		WHERE table_schema = DATABASE() AND table_name = %s
		LIMIT 1
		""",
		(table_name,),
	)
	return bool(rows)


def _get_used_sequence_numbers(prefix: str) -> set[int]:
	"""Return all sequence numbers (int) already taken under this prefix."""
	active = frappe.db.sql(
		"SELECT name FROM `tabItem` WHERE name LIKE %s",
		(f"{prefix}%",),
		as_list=True,
	)

	retired: list[tuple[str]] = []
	if _table_exists("tabRetired SKU"):
		retired = frappe.db.sql(
			"SELECT name FROM `tabRetired SKU` WHERE name LIKE %s",
			(f"{prefix}%",),
			as_list=True,
		)

	used: set[int] = set()
	for (name,) in active + retired:
		suffix = name[len(prefix):]
		if suffix.isdigit():
			used.add(int(suffix))
	return used
