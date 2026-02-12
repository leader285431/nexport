# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


class Item(Document):
	def before_insert(self) -> None:
		if not self.sku:
			self.sku = generate_sku(
				supplier=self.supplier,
				category=self.category,
				sub_category=self.sub_category,
			)

		if not self.markup_multiplier:
			settings = frappe.get_single("NexPort Settings")
			self.markup_multiplier = settings.default_markup_multiplier or 1.0


def generate_sku(
	supplier: str | None = None,
	category: str | None = None,
	sub_category: str | None = None,
) -> str:
	"""Generate SKU in format: {Supplier}-{Category}-{SubCategory}-{Sequence}."""
	supplier_code = _to_code(supplier) if supplier else "GEN"
	category_code = _to_code(category) if category else "GEN"
	sub_category_code = _to_code(sub_category) if sub_category else "GEN"

	prefix = f"{supplier_code}-{category_code}-{sub_category_code}"

	# Find max existing sequence for this prefix (use REGEXP for exact match)
	result = frappe.db.sql(
		"""
		SELECT sku FROM `tabItem`
		WHERE sku REGEXP %s
		ORDER BY sku DESC
		LIMIT 1
		""",
		(f"^{prefix}-[0-9]+$",),
		as_dict=True,
	)

	if result:
		last_sku = result[0].sku
		try:
			last_seq = int(last_sku.rsplit("-", 1)[-1])
		except (ValueError, IndexError):
			last_seq = 0
		next_seq = last_seq + 1
	else:
		next_seq = 1

	return f"{prefix}-{next_seq:04d}"


def _to_code(value: str) -> str:
	"""Convert a value to uppercase code, keeping first 3 chars of alphanumeric."""
	cleaned = "".join(c for c in value if c.isalnum())
	return cleaned[:3].upper() or "GEN"
