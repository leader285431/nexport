# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None) -> tuple[list, list]:
	columns = _get_columns()
	data = _get_data()
	return columns, data


def _get_columns() -> list[dict]:
	return [
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 140},
		{"label": _("Count"), "fieldname": "count", "fieldtype": "Int", "width": 100},
		{"label": _("% of Total"), "fieldname": "pct", "fieldtype": "Percent", "width": 110},
	]


def _get_data() -> list[dict]:
	rows = frappe.db.sql(
		"""
		SELECT status, COUNT(*) AS cnt
		FROM `tabLead`
		GROUP BY status
		ORDER BY FIELD(status, 'New','Contacted','Qualified','Converted','Lost')
		""",
		as_dict=True,
	)
	total = sum(r.cnt for r in rows)
	return [
		{
			"status": r.status,
			"count": r.cnt,
			"pct": round(r.cnt / total * 100, 1) if total else 0,
		}
		for r in rows
	]
