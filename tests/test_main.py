"""
Tests for wp-vitals main.py

Run with:
    pytest tests/test_main.py -v
"""

import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Add project root to path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import filter_recent_lines, find_log_files, analyze_logs


# ---------------------------------------------------------------------------
# filter_recent_lines
# ---------------------------------------------------------------------------

class TestFilterRecentLines:
    """Tests for the log line date filtering function."""

    def test_includes_recent_entry(self):
        """Lines timestamped within the cutoff window should be included."""
        today = datetime.now(timezone.utc)
        timestamp = today.strftime("%d-%b-%Y %H:%M:%S UTC")
        content = f"[{timestamp}] PHP Warning: Something went wrong"

        result = filter_recent_lines(content, days=30)

        assert "PHP Warning" in result

    def test_excludes_old_entry(self):
        """Lines timestamped outside the cutoff window should be excluded."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        timestamp = old_date.strftime("%d-%b-%Y %H:%M:%S UTC")
        content = f"[{timestamp}] PHP Warning: Old error"

        result = filter_recent_lines(content, days=30)

        assert "Old error" not in result

    def test_includes_lines_without_timestamp(self):
        """Stack trace lines and continuation lines without timestamps should always be included."""
        content = "Stack trace:\n#0 /some/file.php(42): someFunction()"

        result = filter_recent_lines(content, days=30)

        assert "Stack trace" in result
        assert "#0 /some/file.php" in result

    def test_includes_unparseable_timestamp(self):
        """Lines with malformed timestamps should be included rather than silently dropped."""
        content = "[not-a-real-date] PHP Notice: Something"

        result = filter_recent_lines(content, days=30)

        assert "PHP Notice" in result

    def test_empty_content_returns_empty(self):
        """Empty input should return an empty string."""
        result = filter_recent_lines("", days=30)

        assert result == ""

    def test_mixed_old_and_recent(self):
        """Only recent lines should survive when log contains both old and new entries."""
        today = datetime.now(timezone.utc)
        old_date = today - timedelta(days=60)

        recent_ts = today.strftime("%d-%b-%Y %H:%M:%S UTC")
        old_ts = old_date.strftime("%d-%b-%Y %H:%M:%S UTC")

        content = (
            f"[{old_ts}] PHP Warning: Old error\n"
            f"[{recent_ts}] PHP Fatal error: New error"
        )

        result = filter_recent_lines(content, days=30)

        assert "New error" in result
        assert "Old error" not in result


# ---------------------------------------------------------------------------
# find_log_files
# ---------------------------------------------------------------------------

class TestFindLogFiles:
    """Tests for the log file discovery function."""

    def test_returns_list(self):
        """Should always return a list, even if no files are found."""
        with patch("main.LOCAL_SITES_PATH", "/nonexistent/path"):
            result = find_log_files()
        assert isinstance(result, list)

    def test_site_filter_is_case_insensitive(self, tmp_path):
        """Site filter should match regardless of case."""
        site_dir = tmp_path / "MyTestSite" / "app" / "public" / "wp-content"
        site_dir.mkdir(parents=True)
        log_file = site_dir / "debug.log"
        log_file.write_text("PHP Warning: test")

        with patch("main.LOCAL_SITES_PATH", str(tmp_path)):
            result = find_log_files(site_filter="mytestsite")

        assert len(result) == 1
        assert "MyTestSite" in result[0]

    def test_no_filter_returns_all_sites(self, tmp_path):
        """Without a site filter, all discovered log files should be returned."""
        for site_name in ["site-one", "site-two"]:
            log_dir = tmp_path / site_name / "app" / "public" / "wp-content"
            log_dir.mkdir(parents=True)
            (log_dir / "debug.log").write_text("PHP Warning: test")

        with patch("main.LOCAL_SITES_PATH", str(tmp_path)):
            result = find_log_files()

        assert len(result) == 2

    def test_results_sorted_by_modified_time(self, tmp_path):
        """Most recently modified log file should appear first."""
        import time

        for site_name in ["older-site", "newer-site"]:
            log_dir = tmp_path / site_name / "app" / "public" / "wp-content"
            log_dir.mkdir(parents=True)
            (log_dir / "debug.log").write_text("PHP Warning: test")
            time.sleep(0.05)

        with patch("main.LOCAL_SITES_PATH", str(tmp_path)):
            result = find_log_files()

        assert "newer-site" in result[0]


# ---------------------------------------------------------------------------
# analyze_logs
# ---------------------------------------------------------------------------

class TestAnalyzeLogs:
    """Tests for the Claude API analysis function."""

    def test_returns_none_for_empty_content(self):
        """Should return None without making an API call if content is blank."""
        result = analyze_logs("test-site", "   ")
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        """Should return None for content that is only newlines and spaces."""
        result = analyze_logs("test-site", "\n\n\n")
        assert result is None

    def test_calls_api_with_site_name(self):
        """Site name should appear in the prompt sent to Claude."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="## Overall Health\nHEALTHY")]

        with patch("main.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            analyze_logs("my-test-site", "PHP Warning: something")

            call_args = mock_client.messages.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "my-test-site" in prompt

    def test_returns_api_response_text(self):
        """Should return the text content from the Claude API response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="CRITICAL - Site is down")]

        with patch("main.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = analyze_logs("test-site", "PHP Fatal error: something")

        assert result == "CRITICAL - Site is down"

    def test_truncates_long_content(self):
        """Log content exceeding 5,000 characters should be truncated before sending."""
        long_content = "PHP Warning: test\n" * 500
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="WARNING")]

        with patch("main.client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            analyze_logs("test-site", long_content)

            call_args = mock_client.messages.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            log_section = prompt.split("Logs:\n")[1]
            assert len(log_section) <= 5000
