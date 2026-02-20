# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Convenience test suite entrypoint for local/CI runs."""

from __future__ import annotations

import unittest

TEST_MODULES = [
    "nexport.tests.test_inventory_service",
    "nexport.tests.test_procurement_service",
    "nexport.tests.test_payment_service",
    "nexport.tests.test_po_repository",
    "nexport.tests.test_item_repository",
    "nexport.tests.test_invoice_repository",
    "nexport.tests.test_gap_repository",
    "nexport.tests.test_shipment_repository",
    "nexport.tests.test_cost_engine",
    "nexport.tests.test_finance_service",
    "nexport.tests.test_services_init",
    "nexport.tests.test_order_service",
    "nexport.tests.test_report_labels",
    "nexport.tests.test_report_row_contracts",
    "nexport.tests.test_dashboard_page",
    "nexport.tests.test_cash_flow_30day_report",
    "nexport.tests.test_patch_scripts",
    "nexport.tests.test_doctype_contracts",
    "nexport.tests.test_workspace_contracts",
    "nexport.tests.test_suite_contract",
    "nexport.tests.test_customs_service",
]


def load_tests(loader: unittest.TestLoader, tests, pattern):  # noqa: ARG001
    """Build a deterministic suite from the maintained unit test modules."""
    suite = unittest.TestSuite()
    for module in TEST_MODULES:
        suite.addTests(loader.loadTestsFromName(module))
    return suite
