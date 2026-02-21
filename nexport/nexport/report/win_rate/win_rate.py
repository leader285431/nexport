# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None) -> tuple[list, list]:
	columns = _get_columns()
	data = _get_data(filters or {})
	return columns, data


def get_filters() -> list[dict]:
	return [
		{
			"fieldname": "assigned_to",
			"label": _("Salesperson"),
			"fieldtype": "Link",
			"options": "User",
		},
		{
			"fieldname": "from_date",
			"label": _("From Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "to_date",
			"label": _("To Date"),
			"fieldtype": "Date",
		},
	]


def _get_columns() -> list[dict]:
	return [
		{"label": _("Salesperson"), "fieldname": "assigned_to", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": _("Won"), "fieldname": "won", "fieldtype": "Int", "width": 80},
		{"label": _("Lost"), "fieldname": "lost", "fieldtype": "Int", "width": 80},
		{"label": _("Total Closed"), "fieldname": "total", "fieldtype": "Int", "width": 110},
		{"label": _("Win Rate %"), "fieldname": "win_rate", "fieldtype": "Percent", "width": 110},
	]


def _get_data(filters: dict) -> list[dict]:
	conditions = "WHERE status IN ('Won','Lost')"
	values: dict = {}

	if filters.get("assigned_to"):
		conditions += " AND assigned_to = %(assigned_to)s"
		values["assigned_to"] = filters["assigned_to"]
	if filters.get("from_date"):
		conditions += " AND DATE(modified) >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND DATE(modified) <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	rows = frappe.db.sql(
		f"""
		SELECT
			assigned_to,
			SUM(status = 'Won')  AS won,
			SUM(status = 'Lost') AS lost,
			COUNT(*)             AS total
		FROM `tabOpportunity`
		{conditions}
		GROUP BY assigned_to
		ORDER BY won DESC
		""",
		values,
		as_dict=True,
	)
	for r in rows:
		r.win_rate = round(r.won / r.total * 100, 1) if r.total else 0
	return rows
