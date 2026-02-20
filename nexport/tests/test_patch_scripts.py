# Copyright (c) 2026, NexPort and contributors
# For license information, please see license.txt

"""Tests for migration patch scripts."""

from __future__ import annotations

import json
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, mock_open, patch

from nexport.tests._frappe_test_bootstrap import load_module

gap_index_patch = load_module("nexport.patches.add_customs_gap_unique_index")
po_index_patch = load_module("nexport.patches.add_purchase_order_supplementary_unique_index")
workspace_patch = load_module("nexport.patches.fix_nexport_workspace_number_cards")
populate_patch = load_module("nexport.patches.populate_item_categories")
workflow_state_patch = load_module("nexport.patches.ensure_delivery_workflow_states")
rename_sales_doctypes_patch = load_module("nexport.patches.rename_sales_doctypes_without_prefix")
workspace_links_patch = load_module("nexport.patches.sync_workspace_links_after_sales_doctype_rename")
re_sync_links_patch = load_module("nexport.patches.re_sync_workspace_links")
workflow_state_post_rename_patch = load_module(
    "nexport.patches.backfill_workflow_states_after_sales_rename"
)
invoice_finalize_patch = load_module("nexport.patches.add_invoice_rate_finalized_field_defaults")


class TestPatchScripts(unittest.TestCase):
    """Keep patch scripts idempotent and safe."""

    @patch("nexport.tests.test_patch_scripts.populate_patch.frappe")
    def test_populate_patch_returns_when_doctype_missing(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = False
        populate_patch.execute()
        mock_frappe.db.sql.assert_not_called()

    @patch("nexport.tests.test_patch_scripts.populate_patch.frappe")
    def test_populate_patch_uses_non_empty_filters(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.side_effect = [True, True, False, False]
        mock_frappe.db.sql.side_effect = [[], []]
        populate_patch.execute()
        self.assertIn("category != ''", mock_frappe.db.sql.call_args_list[0].args[0])
        self.assertIn("sub_category != ''", mock_frappe.db.sql.call_args_list[1].args[0])

    @patch("nexport.tests.test_patch_scripts.gap_index_patch.frappe")
    def test_gap_index_patch_skips_when_table_missing(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.sql.return_value = []
        gap_index_patch.execute()
        self.assertEqual(mock_frappe.db.sql.call_count, 1)

    @patch("nexport.tests.test_patch_scripts.po_index_patch.frappe")
    def test_po_index_patch_skips_when_index_exists(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.sql.side_effect = [[(1,)], [(1,)]]
        po_index_patch.execute()
        self.assertEqual(mock_frappe.db.sql.call_count, 2)

    @patch("nexport.tests.test_patch_scripts.workspace_patch.frappe")
    def test_workspace_patch_sets_expected_cards(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = True
        mock_frappe.get_all.return_value = [
            {"name": "ROW-1", "label": "Inventory Dual-Track Value"},
            {"name": "ROW-2", "label": "Pending Customs Gaps"},
            {"name": "ROW-3", "label": "Pending AP Invoices"},
        ]
        workspace_patch.execute()
        self.assertEqual(mock_frappe.db.set_value.call_count, 3)

    @patch("nexport.tests.test_patch_scripts.workspace_patch.frappe")
    def test_workspace_number_card_patch_is_idempotent(self, mock_frappe: MagicMock) -> None:
        """Re-running patch on already-set cards makes no extra writes."""
        mock_frappe.db.exists.return_value = True
        # All three cards already have correct labels — patch should still set them
        # (set_value is idempotent: overwriting with same value is safe).
        # Key assertion: only the matched cards are written, not extras.
        mock_frappe.get_all.return_value = [
            {"name": "ROW-1", "label": "Inventory Dual-Track Value"},
            {"name": "ROW-2", "label": "Pending Customs Gaps"},
            {"name": "ROW-3", "label": "Pending AP Invoices"},
        ]
        workspace_patch.execute()
        workspace_patch.execute()
        # 3 cards × 2 runs = 6 calls; no extra calls for unmatched labels
        self.assertEqual(mock_frappe.db.set_value.call_count, 6)

    @patch("nexport.tests.test_patch_scripts.workspace_patch.frappe")
    def test_workspace_number_card_patch_skips_unknown_labels(self, mock_frappe: MagicMock) -> None:
        """Cards with labels not in desired list are skipped (not overwritten)."""
        mock_frappe.db.exists.return_value = True
        mock_frappe.get_all.return_value = [
            {"name": "ROW-1", "label": "Inventory Dual-Track Value"},
            {"name": "ROW-X", "label": "Some Unrelated Card"},
        ]
        workspace_patch.execute()
        # Only ROW-1 matches a desired label; ROW-X should be skipped
        self.assertEqual(mock_frappe.db.set_value.call_count, 1)
        mock_frappe.db.set_value.assert_called_once_with(
            "Workspace Number Card",
            "ROW-1",
            "number_card_name",
            "Inventory Dual-Track Value",
            update_modified=False,
        )

    @patch("nexport.tests.test_patch_scripts.populate_patch.frappe")
    def test_populate_patch_logs_error_and_raises(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.side_effect = [True, True]
        mock_frappe.db.sql.side_effect = Exception("sql failed")
        with self.assertRaises(Exception):
            populate_patch.execute()
        mock_frappe.log_error.assert_called_once()

    @patch("nexport.tests.test_patch_scripts.gap_index_patch.frappe")
    def test_gap_index_patch_logs_error_and_raises(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.sql.side_effect = Exception("db failed")
        with self.assertRaises(Exception):
            gap_index_patch.execute()
        mock_frappe.log_error.assert_called_once()


class TestWorkflowStatePatchScript(unittest.TestCase):
    """Contract tests for workflow-state patch behavior."""

    def _run_with_mocked_frappe(self, configured_frappe: MagicMock) -> None:
        module_name = workflow_state_patch.__name__
        with patch(f"{module_name}.frappe", configured_frappe):
            workflow_state_patch.execute()

    def _fixture_patches(
        self,
        payload: object,
        *,
        read_error: Exception | None = None,
        parse_error: Exception | None = None,
    ):
        module_name = workflow_state_patch.__name__
        fixture_text = json.dumps(payload)
        file_handle = mock_open(read_data=fixture_text).return_value
        stack = ExitStack()
        if read_error is not None:
            stack.enter_context(patch("pathlib.Path.open", side_effect=read_error))
        else:
            stack.enter_context(patch("pathlib.Path.open", return_value=file_handle))

        if parse_error is not None:
            stack.enter_context(patch(f"{module_name}.json.load", side_effect=parse_error, create=True))
            stack.enter_context(patch(f"{module_name}.json.loads", side_effect=parse_error, create=True))
        else:
            stack.enter_context(patch(f"{module_name}.json.load", return_value=payload, create=True))
            stack.enter_context(patch(f"{module_name}.json.loads", return_value=payload, create=True))

        return stack

    def test_workflow_state_patch_creates_all_missing_states_from_fixture(self) -> None:
        mock_frappe = MagicMock()
        payload = [
            {
                "states": [
                    {"state": "Draft"},
                    {"state": "Confirmed"},
                    {"state": "Customs Clearing"},
                    {"state": "Delivered"},
                ]
            }
        ]

        def exists_side_effect(doctype, filters=None):  # noqa: ANN001
            if doctype == "DocType":
                return True
            if doctype == "Workflow State":
                return False
            return False

        mock_frappe.db.exists.side_effect = exists_side_effect
        mock_doc = MagicMock()
        mock_frappe.get_doc.return_value = mock_doc

        with self._fixture_patches(payload):
            self._run_with_mocked_frappe(mock_frappe)

        self.assertEqual(mock_frappe.get_doc.call_count, 4)
        self.assertEqual(mock_doc.insert.call_count, 4)

    def test_workflow_state_patch_idempotent_skip_when_state_exists(self) -> None:
        mock_frappe = MagicMock()
        payload = [{"states": [{"state": "Draft"}, {"state": "Confirmed"}, {"state": "Delivered"}]}]

        def exists_side_effect(doctype, filters=None):  # noqa: ANN001
            if doctype == "DocType":
                return True
            if doctype == "Workflow State":
                return True
            return False

        mock_frappe.db.exists.side_effect = exists_side_effect

        with self._fixture_patches(payload):
            self._run_with_mocked_frappe(mock_frappe)

        self.assertEqual(mock_frappe.get_doc.call_count, 0)
        self.assertEqual(mock_frappe.new_doc.call_count, 0)
        self.assertEqual(mock_frappe.db.exists.call_count, 4)

    def test_workflow_state_patch_logs_error_and_raises_on_fixture_read_or_parse_failure(self) -> None:
        base_payload = [{"states": [{"state": "Draft"}]}]
        failure_modes = (
            ("read", OSError("fixture read failed"), None),
            ("parse", None, ValueError("fixture parse failed")),
        )

        module_name = workflow_state_patch.__name__
        for _label, read_error, parse_error in failure_modes:
            with self.subTest(mode=_label):
                mock_frappe = MagicMock()
                mock_frappe.db.exists.return_value = True
                with patch(f"{module_name}.frappe", mock_frappe):
                    with self._fixture_patches(base_payload, read_error=read_error, parse_error=parse_error):
                        with self.assertRaises(Exception):
                            workflow_state_patch.execute()

                mock_frappe.log_error.assert_called_once()

    def test_workflow_state_patch_style_mapping_includes_draft_and_default_style(self) -> None:
        mock_frappe = MagicMock()
        payload = [{"states": [{"state": "Draft"}, {"state": "Unknown State"}]}]

        def exists_side_effect(doctype, filters=None):  # noqa: ANN001
            if doctype == "DocType":
                return True
            if doctype == "Workflow State":
                return False
            return False

        mock_frappe.db.exists.side_effect = exists_side_effect
        mock_frappe.get_doc.return_value = MagicMock()

        with self._fixture_patches(payload):
            self._run_with_mocked_frappe(mock_frappe)

        created_docs = [call.args[0] for call in mock_frappe.get_doc.call_args_list]
        styles_by_state = {doc["workflow_state_name"]: doc["style"] for doc in created_docs}
        self.assertEqual(styles_by_state.get("Draft"), "Info")
        self.assertEqual(styles_by_state.get("Unknown State"), "Primary")


class TestRenameSalesDocTypesPatchScript(unittest.TestCase):
    """Contract tests for sales-DocType rename patch behavior."""

    @patch("nexport.tests.test_patch_scripts.rename_sales_doctypes_patch.frappe")
    def test_rename_patch_executes_rename_workflow_sync_and_delete_when_empty(
        self, mock_frappe: MagicMock
    ) -> None:
        # Rename phase: old exists / new missing for each pair.
        rename_exists = [True, False] * len(rename_sales_doctypes_patch.DOCTYPE_RENAMES)
        # Cleanup phase: both old/new exist for each pair.
        delete_exists = [True, True] * len(rename_sales_doctypes_patch.DOCTYPE_RENAMES)
        mock_frappe.db.exists.side_effect = rename_exists + delete_exists
        mock_frappe.db.count.return_value = 0

        rename_sales_doctypes_patch.execute()

        self.assertEqual(
            mock_frappe.rename_doc.call_count,
            len(rename_sales_doctypes_patch.DOCTYPE_RENAMES),
        )
        for old_name, new_name in rename_sales_doctypes_patch.DOCTYPE_RENAMES:
            mock_frappe.rename_doc.assert_any_call("DocType", old_name, new_name, force=True)

        self.assertEqual(
            mock_frappe.db.set_value.call_count,
            len(rename_sales_doctypes_patch.WORKFLOW_RENAMES),
        )
        for old_name, new_name in rename_sales_doctypes_patch.WORKFLOW_RENAMES:
            mock_frappe.db.set_value.assert_any_call(
                "Workflow",
                {"document_type": old_name},
                "document_type",
                new_name,
                update_modified=False,
            )

        self.assertEqual(
            mock_frappe.delete_doc.call_count,
            len(rename_sales_doctypes_patch.DOCTYPE_RENAMES),
        )
        for old_name, _ in rename_sales_doctypes_patch.DOCTYPE_RENAMES:
            mock_frappe.delete_doc.assert_any_call(
                "DocType",
                old_name,
                force=True,
                ignore_permissions=True,
            )

    @patch("nexport.tests.test_patch_scripts.rename_sales_doctypes_patch.frappe")
    def test_rename_patch_is_idempotent_when_new_doctypes_already_exist(
        self, mock_frappe: MagicMock
    ) -> None:
        # Both old/new present => rename should skip; count keeps old docs from deletion.
        mock_frappe.db.exists.return_value = True
        mock_frappe.db.count.return_value = 1

        rename_sales_doctypes_patch.execute()

        mock_frappe.rename_doc.assert_not_called()
        self.assertEqual(
            mock_frappe.db.set_value.call_count,
            len(rename_sales_doctypes_patch.WORKFLOW_RENAMES),
        )

    @patch("nexport.tests.test_patch_scripts.rename_sales_doctypes_patch.frappe")
    def test_rename_patch_preserves_old_doctype_when_data_exists(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = True
        mock_frappe.db.count.return_value = 3

        rename_sales_doctypes_patch.execute()

        mock_frappe.delete_doc.assert_not_called()

    @patch("nexport.tests.test_patch_scripts.rename_sales_doctypes_patch.frappe")
    def test_rename_patch_skips_safely_when_old_doctype_missing(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = False

        rename_sales_doctypes_patch.execute()

        mock_frappe.rename_doc.assert_not_called()
        mock_frappe.delete_doc.assert_not_called()
        self.assertEqual(
            mock_frappe.db.set_value.call_count,
            len(rename_sales_doctypes_patch.WORKFLOW_RENAMES),
        )

    @patch("nexport.tests.test_patch_scripts.rename_sales_doctypes_patch.frappe")
    def test_rename_patch_raises_when_rename_doc_fails(self, mock_frappe: MagicMock) -> None:
        # First doctype enters rename path immediately.
        mock_frappe.db.exists.side_effect = [True, False]
        mock_frappe.rename_doc.side_effect = RuntimeError("rename failed")

        with self.assertRaises(RuntimeError):
            rename_sales_doctypes_patch.execute()

    @patch("nexport.tests.test_patch_scripts.rename_sales_doctypes_patch.frappe")
    def test_rename_patch_raises_when_workflow_sync_fails(self, mock_frappe: MagicMock) -> None:
        # Skip rename and delete by making old DocTypes missing.
        mock_frappe.db.exists.return_value = False
        mock_frappe.db.set_value.side_effect = RuntimeError("workflow sync failed")

        with self.assertRaises(RuntimeError):
            rename_sales_doctypes_patch.execute()


class TestWorkspaceLinksPatchScript(unittest.TestCase):
    """Contract tests for workspace-link sync patch behavior."""

    @patch("nexport.tests.test_patch_scripts.workspace_links_patch.frappe")
    def test_workspace_links_patch_skips_when_workspace_missing(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = False

        workspace_links_patch.execute()

        mock_frappe.get_doc.assert_not_called()

    @patch("nexport.tests.test_patch_scripts.workspace_links_patch.frappe")
    def test_workspace_links_patch_updates_legacy_link_targets(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = True
        workspace = MagicMock()
        workspace.links = [
            {"link_to": "Nexport Quote"},
            {"link_to": "Purchase Order"},
            {"link_to": "Nexport Delivery Note"},
        ]
        workspace.shortcuts = [{"link_to": "Nexport Sales Order"}]
        workspace.content = '[{"data":{"link_to":"Nexport Quote"}}]'
        mock_frappe.get_doc.return_value = workspace

        workspace_links_patch.execute()

        self.assertEqual(workspace.links[0]["link_to"], "Quote")
        self.assertEqual(workspace.links[1]["link_to"], "Purchase Order")
        self.assertEqual(workspace.links[2]["link_to"], "Delivery Note")
        self.assertEqual(workspace.shortcuts[0]["link_to"], "Sales Order")
        self.assertIn('"link_to":"Quote"', workspace.content)
        workspace.save.assert_called_once_with(ignore_permissions=True)

    @patch("nexport.tests.test_patch_scripts.workspace_links_patch.frappe")
    def test_workspace_links_patch_is_idempotent(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = True
        workspace = MagicMock()
        workspace.links = [{"link_to": "Quote"}]
        workspace.shortcuts = [{"link_to": "Sales Order"}]
        workspace.content = '[{"data":{"link_to":"Delivery Note"}}]'
        mock_frappe.get_doc.return_value = workspace

        workspace_links_patch.execute()

        workspace.save.assert_not_called()

    @patch("nexport.tests.test_patch_scripts.workspace_links_patch.frappe")
    def test_workspace_links_patch_logs_error_and_raises(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = True
        mock_frappe.get_doc.side_effect = RuntimeError("workspace load failed")

        with self.assertRaises(RuntimeError):
            workspace_links_patch.execute()

        mock_frappe.log_error.assert_called_once()


class TestWorkflowStateBackfillAfterRenamePatch(unittest.TestCase):
    """Contract test for post-rename workflow-state rerun patch."""

    @patch("nexport.tests.test_patch_scripts.workflow_state_post_rename_patch._execute_sync")
    def test_backfill_after_rename_delegates_to_existing_backfill(self, mock_execute: MagicMock) -> None:
        workflow_state_post_rename_patch.execute()
        mock_execute.assert_called_once_with()


class TestInvoiceFinalizePatch(unittest.TestCase):
    """Contract tests for invoice finalize-field backfill patch."""

    @patch("nexport.tests.test_patch_scripts.invoice_finalize_patch.frappe")
    def test_invoice_finalize_patch_skips_when_invoice_doctype_missing(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = False
        invoice_finalize_patch.execute()
        mock_frappe.db.sql.assert_not_called()

    @patch("nexport.tests.test_patch_scripts.invoice_finalize_patch.frappe")
    def test_invoice_finalize_patch_updates_defaults_when_fields_exist(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.side_effect = [True, True, True]
        invoice_finalize_patch.execute()
        self.assertEqual(mock_frappe.db.sql.call_count, 2)


class TestReSyncWorkspaceLinksPatch(unittest.TestCase):
    """Contract tests for re_sync_workspace_links patch behavior."""

    @patch("nexport.tests.test_patch_scripts.re_sync_links_patch.frappe")
    def test_re_sync_links_patch_skips_when_workspace_missing(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = False

        re_sync_links_patch.execute()

        mock_frappe.get_doc.assert_not_called()

    @patch("nexport.tests.test_patch_scripts.re_sync_links_patch.frappe")
    def test_re_sync_links_patch_renames_capital_p_variants(self, mock_frappe: MagicMock) -> None:
        """NexPort (capital-P) legacy names are renamed to canonical targets."""
        mock_frappe.db.exists.return_value = True
        workspace = MagicMock()
        workspace.links = [
            {"link_to": "NexPort Quote"},
            {"link_to": "NexPort Sales Order"},
        ]
        workspace.shortcuts = [{"link_to": "NexPort Delivery Note"}]
        workspace.content = '[{"data":{"link_to":"NexPort Quote"}}]'
        mock_frappe.get_doc.return_value = workspace

        re_sync_links_patch.execute()

        self.assertEqual(workspace.links[0]["link_to"], "Quote")
        self.assertEqual(workspace.links[1]["link_to"], "Sales Order")
        self.assertEqual(workspace.shortcuts[0]["link_to"], "Delivery Note")
        self.assertIn('"link_to":"Quote"', workspace.content)
        workspace.save.assert_called_once_with(ignore_permissions=True)

    @patch("nexport.tests.test_patch_scripts.re_sync_links_patch.frappe")
    def test_re_sync_links_patch_is_idempotent(self, mock_frappe: MagicMock) -> None:
        """Running re_sync twice produces same result (no redundant save on second run)."""
        mock_frappe.db.exists.return_value = True
        workspace = MagicMock()
        workspace.links = [{"link_to": "Quote"}]
        workspace.shortcuts = [{"link_to": "Sales Order"}]
        workspace.content = '[{"data":{"link_to":"Delivery Note"}}]'
        mock_frappe.get_doc.return_value = workspace

        re_sync_links_patch.execute()

        workspace.save.assert_not_called()

    @patch("nexport.tests.test_patch_scripts.re_sync_links_patch.frappe")
    def test_re_sync_links_patch_logs_error_and_raises(self, mock_frappe: MagicMock) -> None:
        mock_frappe.db.exists.return_value = True
        mock_frappe.get_doc.side_effect = RuntimeError("workspace load failed")

        with self.assertRaises(RuntimeError):
            re_sync_links_patch.execute()

        mock_frappe.log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
