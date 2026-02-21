# Copyright (c) 2026, NexPort and contributors
from __future__ import annotations
import frappe
from frappe.utils import nowdate


def execute(filters: dict | None = None) -> tuple[list, list]:
	columns = _get_columns()
	data = _get_data(filters or {})
	return columns, data


def _get_columns() -> list[dict]:
	cols = [{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Data", "width": 180}]
	for month in range(1, 13):
		cols.append({
			"label": f"Month {month:02d}",
			"fieldname": f"m{month:02d}",
			"fieldtype": "Currency",
			"width": 110,
		})
	cols.append({"label": "Total", "fieldname": "total", "fieldtype": "Currency", "width": 130})
	return cols


def _get_data(filters: dict) -> list[dict]:
	year = filters.get("year") or nowdate()[:4]

	rows = frappe.db.sql("""
		SELECT
			i.supplier,
			SUM(CASE WHEN MONTH(ps.due_date) = 1  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m01,
			SUM(CASE WHEN MONTH(ps.due_date) = 2  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m02,
			SUM(CASE WHEN MONTH(ps.due_date) = 3  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m03,
			SUM(CASE WHEN MONTH(ps.due_date) = 4  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m04,
			SUM(CASE WHEN MONTH(ps.due_date) = 5  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m05,
			SUM(CASE WHEN MONTH(ps.due_date) = 6  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m06,
			SUM(CASE WHEN MONTH(ps.due_date) = 7  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m07,
			SUM(CASE WHEN MONTH(ps.due_date) = 8  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m08,
			SUM(CASE WHEN MONTH(ps.due_date) = 9  THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m09,
			SUM(CASE WHEN MONTH(ps.due_date) = 10 THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m10,
			SUM(CASE WHEN MONTH(ps.due_date) = 11 THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m11,
			SUM(CASE WHEN MONTH(ps.due_date) = 12 THEN (ps.amount - ps.paid_amount) ELSE 0 END) AS m12,
			SUM(ps.amount - ps.paid_amount) AS total
		FROM `tabPayment Schedule` ps
		JOIN `tabInvoice` i ON i.name = ps.parent
		WHERE YEAR(ps.due_date) = %(year)s
		  AND ps.status IN ('Pending', 'Overdue')
		GROUP BY i.supplier
		ORDER BY i.supplier
	""", {"year": year}, as_dict=True)
	return rows
