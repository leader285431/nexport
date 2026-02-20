# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call

import nexport.services.customs_service as customs_service

_SERVICE = "nexport.services.customs_service"


class TestResolveGapsSingle(unittest.TestCase):
	"""Single gap scenarios."""

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_single_gap_fully_resolved(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Single gap fully consumed → status Resolved, declared stock updated."""
		mock_get_gaps.return_value = [
			{"name": "GAP-001", "product": "ITEM-A", "gap_qty": 10.0, "resolved_qty": 0.0}
		]

		result = customs_service.resolve_gaps("CN-001", 10.0, "DECL-001")

		mock_update_gap.assert_called_once_with("GAP-001", 10.0, "Resolved", "DECL-001")
		mock_update_stock.assert_called_once_with("ITEM-A", declared_delta=10.0)
		self.assertEqual(result["resolved_count"], 1)
		self.assertEqual(result["remaining_qty"], 0.0)
		self.assertEqual(result["gaps_affected"], ["GAP-001"])
		mock_frappe.db.commit.assert_called_once()

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_single_gap_partially_resolved(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Declaration qty smaller than gap → status Partial."""
		mock_get_gaps.return_value = [
			{"name": "GAP-001", "product": "ITEM-A", "gap_qty": 10.0, "resolved_qty": 0.0}
		]

		result = customs_service.resolve_gaps("CN-001", 4.0, "DECL-002")

		mock_update_gap.assert_called_once_with("GAP-001", 4.0, "Partial", "DECL-002")
		mock_update_stock.assert_called_once_with("ITEM-A", declared_delta=4.0)
		self.assertEqual(result["resolved_count"], 1)
		self.assertEqual(result["remaining_qty"], 0.0)

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_declaration_exceeds_gaps(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Declaration qty > total gap qty → resolves all, reports remainder."""
		mock_get_gaps.return_value = [
			{"name": "GAP-001", "product": "ITEM-A", "gap_qty": 5.0, "resolved_qty": 0.0}
		]

		result = customs_service.resolve_gaps("CN-001", 15.0, "DECL-003")

		mock_update_gap.assert_called_once_with("GAP-001", 5.0, "Resolved", "DECL-003")
		self.assertEqual(result["remaining_qty"], 10.0)
		mock_frappe.msgprint.assert_called_once()


class TestResolveGapsFIFO(unittest.TestCase):
	"""FIFO ordering with multiple gaps."""

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_fifo_order(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Oldest gaps consumed first (FIFO)."""
		mock_get_gaps.return_value = [
			{"name": "GAP-001", "product": "ITEM-A", "gap_qty": 5.0, "resolved_qty": 0.0},
			{"name": "GAP-002", "product": "ITEM-A", "gap_qty": 5.0, "resolved_qty": 0.0},
		]

		result = customs_service.resolve_gaps("CN-001", 7.0, "DECL-004")

		calls = mock_update_gap.call_args_list
		self.assertEqual(calls[0], call("GAP-001", 5.0, "Resolved", "DECL-004"))
		self.assertEqual(calls[1], call("GAP-002", 2.0, "Partial", "DECL-004"))
		self.assertEqual(result["resolved_count"], 2)
		self.assertEqual(result["remaining_qty"], 0.0)

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_multi_product_declared_stock(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Multiple products with same customs_name each get correct declared delta."""
		mock_get_gaps.return_value = [
			{"name": "GAP-001", "product": "ITEM-A", "gap_qty": 3.0, "resolved_qty": 0.0},
			{"name": "GAP-002", "product": "ITEM-B", "gap_qty": 4.0, "resolved_qty": 0.0},
		]

		customs_service.resolve_gaps("CN-SHARED", 10.0, "DECL-005")

		# Items updated in sorted order (ITEM-A before ITEM-B)
		stock_calls = mock_update_stock.call_args_list
		self.assertEqual(stock_calls[0], call("ITEM-A", declared_delta=3.0))
		self.assertEqual(stock_calls[1], call("ITEM-B", declared_delta=4.0))

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_partial_gap_already_resolved(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Partial gap (already has resolved_qty) is consumed correctly."""
		mock_get_gaps.return_value = [
			{"name": "GAP-001", "product": "ITEM-A", "gap_qty": 10.0, "resolved_qty": 6.0}
		]

		result = customs_service.resolve_gaps("CN-001", 5.0, "DECL-006")

		# Only 4 remaining in gap, declare 5 → resolves 4, remainder 1
		mock_update_gap.assert_called_once_with("GAP-001", 4.0, "Resolved", "DECL-006")
		self.assertEqual(result["remaining_qty"], 1.0)


class TestResolveGapsEdgeCases(unittest.TestCase):
	"""Edge cases and error handling."""

	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_zero_qty_noop(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
	) -> None:
		"""Zero declaration quantity → no-op, no DB calls."""
		result = customs_service.resolve_gaps("CN-001", 0.0, "DECL-007")

		mock_get_gaps.assert_not_called()
		self.assertEqual(result["resolved_count"], 0)

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_no_gaps_returns_empty(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""No open gaps → nothing resolved."""
		mock_get_gaps.return_value = []

		result = customs_service.resolve_gaps("CN-NONE", 5.0, "DECL-008")

		mock_update_gap.assert_not_called()
		mock_update_stock.assert_not_called()
		self.assertEqual(result["resolved_count"], 0)
		self.assertEqual(result["remaining_qty"], 5.0)

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_lock_timeout_raises_validation_error(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Lock wait timeout → frappe.throw called, rollback called."""
		mock_get_gaps.side_effect = Exception("Lock wait timeout exceeded; try restarting transaction")
		mock_frappe.throw.side_effect = Exception("Please try again")

		with self.assertRaises(Exception):
			customs_service.resolve_gaps("CN-001", 5.0, "DECL-009")

		mock_frappe.db.rollback.assert_called_once()
		mock_frappe.throw.assert_called_once()

	@patch(f"{_SERVICE}.update_stock_atomic")
	@patch(f"{_SERVICE}.update_gap_resolved")
	@patch(f"{_SERVICE}.get_pending_gaps_for_update")
	@patch(f"{_SERVICE}.frappe")
	def test_other_exception_rollback_reraise(
		self,
		mock_frappe: MagicMock,
		mock_get_gaps: MagicMock,
		mock_update_gap: MagicMock,
		mock_update_stock: MagicMock,
	) -> None:
		"""Non-lock exception → rollback and re-raise without frappe.throw."""
		mock_get_gaps.side_effect = Exception("Some other DB error")

		with self.assertRaises(Exception):
			customs_service.resolve_gaps("CN-001", 5.0, "DECL-010")

		mock_frappe.db.rollback.assert_called_once()
		mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
	unittest.main()
