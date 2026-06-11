"""
Tests for wp-vitals report.py

Run with:
    pytest tests/test_report.py -v
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path so we can import report
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report import generate_executive_summary, generate_debug_prompts


# ---------------------------------------------------------------------------
# generate_executive_summary
# ---------------------------------------------------------------------------

class TestGenerateExecutiveSummary:
    """Tests for the unified executive summary generation."""

    def test_returns_string_with_all_data(self):
        """Should return a non-empty string when all audit results are provided."""
        log_result = {"report": "HEALTHY - No issues found."}
        plugin_result = {"report": "WARNING - query-monitor needs update."}
        theme_result = {"report": "CRITICAL - 1 critical vulnerability in form-data."}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Overall Health: WARNING\nTop 3 Actions: ...")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_executive_summary("test-site", log_result, plugin_result, theme_result)

        assert result is not None
        assert len(result) > 0

    def test_handles_missing_log_result(self):
        """Should not crash when log result is None."""
        plugin_result = {"report": "WARNING - query-monitor needs update."}
        theme_result = {"report": "WARNING - vulnerabilities found."}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Overall Health: WARNING")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_executive_summary("test-site", None, plugin_result, theme_result)

        assert result is not None

    def test_handles_missing_plugin_result(self):
        """Should not crash when plugin result is None."""
        log_result = {"report": "HEALTHY - No issues."}
        theme_result = {"report": "WARNING - vulnerabilities found."}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Overall Health: WARNING")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_executive_summary("test-site", log_result, None, theme_result)

        assert result is not None

    def test_handles_missing_theme_result(self):
        """Should not crash when theme result is None."""
        log_result = {"report": "HEALTHY - No issues."}
        plugin_result = {"report": "WARNING - updates available."}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Overall Health: WARNING")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_executive_summary("test-site", log_result, plugin_result, None)

        assert result is not None

    def test_handles_all_none_results(self):
        """Should not crash when all audit results are None."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="No data available.")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_executive_summary("test-site", None, None, None)

        assert result is not None

    def test_includes_site_name_in_prompt(self):
        """Site name should appear in the prompt sent to Claude."""
        log_result = {"report": "HEALTHY"}
        plugin_result = {"report": "HEALTHY"}
        theme_result = {"report": "HEALTHY"}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="HEALTHY")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            generate_executive_summary("my-test-site", log_result, plugin_result, theme_result)

            call_args = mock_client.messages.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "my-test-site" in prompt

    def test_returns_api_response_text(self):
        """Should return the text content from the Claude API response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Overall Health: CRITICAL")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_executive_summary("test-site", None, None, None)

        assert result == "Overall Health: CRITICAL"


# ---------------------------------------------------------------------------
# generate_debug_prompts
# ---------------------------------------------------------------------------

class TestGenerateDebugPrompts:
    """Tests for ready-to-paste debug prompt generation."""

    def test_returns_prompts_with_audit_data(self):
        """Should return formatted prompts when audit data is available."""
        log_result = {"report": "CRITICAL - PHP Fatal error in price.php:57"}
        plugin_result = {"report": "WARNING - query-monitor needs major update"}
        theme_result = {"report": "WARNING - form-data critical vulnerability"}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Prompt 1: How do I fix price.php:57?\nPrompt 2: ...")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_debug_prompts(log_result, plugin_result, theme_result)

        assert result is not None
        assert len(result) > 0

    def test_returns_none_when_all_results_empty(self):
        """Should return None when no audit data is available to generate prompts from."""
        result = generate_debug_prompts(None, None, None)
        assert result is None

    def test_returns_none_when_reports_are_empty_strings(self):
        """Should return None when all report fields are empty strings."""
        log_result = {"report": ""}
        plugin_result = {"report": ""}
        theme_result = {"report": ""}

        result = generate_debug_prompts(log_result, plugin_result, theme_result)
        assert result is None

    def test_handles_partial_results(self):
        """Should generate prompts even when only some audits have data."""
        log_result = {"report": "CRITICAL - Fatal error in plugin"}
        plugin_result = None
        theme_result = None

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Prompt 1: How do I debug this fatal error?")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_debug_prompts(log_result, plugin_result, theme_result)

        assert result is not None

    def test_combines_all_reports_in_prompt(self):
        """All three audit reports should appear in the prompt sent to Claude."""
        log_result = {"report": "log-specific-error-text"}
        plugin_result = {"report": "plugin-specific-warning-text"}
        theme_result = {"report": "theme-specific-vulnerability-text"}

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Prompt 1: ...")]

        with patch("report.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            generate_debug_prompts(log_result, plugin_result, theme_result)

            call_args = mock_client.messages.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "log-specific-error-text" in prompt
            assert "plugin-specific-warning-text" in prompt
            assert "theme-specific-vulnerability-text" in prompt
