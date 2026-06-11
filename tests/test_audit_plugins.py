"""
Tests for wp-vitals audit_plugins.py

Run with:
    pytest tests/test_audit_plugins.py -v
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path so we can import audit_plugins
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit_plugins import classify_plugins, get_wp_path, get_plugin_list


# ---------------------------------------------------------------------------
# get_wp_path
# ---------------------------------------------------------------------------

class TestGetWpPath:
    """Tests for WordPress root path resolution."""

    def test_returns_explicit_path_when_provided(self):
        """--path should take precedence over --site."""
        result = get_wp_path(site=None, path="/some/explicit/path")
        assert result == "/some/explicit/path"

    def test_resolves_path_from_site_name(self, tmp_path):
        """Should construct the correct WP root path from a site name."""
        wp_root = tmp_path / "mysite" / "app" / "public"
        wp_root.mkdir(parents=True)

        with patch("audit_plugins.LOCAL_SITES_PATH", str(tmp_path)):
            result = get_wp_path(site="mysite", path=None)

        assert result == str(wp_root)

    def test_returns_none_for_missing_site(self, tmp_path):
        """Should return None if the resolved path does not exist."""
        with patch("audit_plugins.LOCAL_SITES_PATH", str(tmp_path)):
            result = get_wp_path(site="nonexistent-site", path=None)

        assert result is None

    def test_returns_none_when_both_args_missing(self):
        """Should return None if neither site nor path is provided."""
        result = get_wp_path(site=None, path=None)
        assert result is None

    def test_explicit_path_overrides_site(self, tmp_path):
        """When both are provided, --path should win."""
        result = get_wp_path(site="some-site", path="/explicit/path")
        assert result == "/explicit/path"


# ---------------------------------------------------------------------------
# classify_plugins
# ---------------------------------------------------------------------------

class TestClassifyPlugins:
    """Tests for plugin classification logic."""

    def test_flags_plugin_with_available_update(self):
        """Plugins with update=available should appear in needs_update."""
        plugins = [
            {
                "name": "my-plugin",
                "status": "active",
                "update": "available",
                "version": "1.0.0",
                "update_version": "1.1.0",
                "auto_update": "on"
            }
        ]

        result = classify_plugins(plugins)

        assert len(result["needs_update"]) == 1
        assert result["needs_update"][0]["name"] == "my-plugin"

    def test_flags_major_version_jump(self):
        """Plugins jumping a major version should be flagged separately."""
        plugins = [
            {
                "name": "query-monitor",
                "status": "active",
                "update": "available",
                "version": "3.19.0",
                "update_version": "4.0.6",
                "auto_update": "off"
            }
        ]

        result = classify_plugins(plugins)

        assert len(result["major_version_jumps"]) == 1
        assert result["major_version_jumps"][0]["name"] == "query-monitor"

    def test_does_not_flag_minor_update_as_major_jump(self):
        """Minor version updates should not appear in major_version_jumps."""
        plugins = [
            {
                "name": "imagify",
                "status": "active",
                "update": "available",
                "version": "2.2.6",
                "update_version": "2.2.8",
                "auto_update": "off"
            }
        ]

        result = classify_plugins(plugins)

        assert len(result["major_version_jumps"]) == 0
        assert len(result["needs_update"]) == 1

    def test_flags_inactive_plugins(self):
        """Inactive plugins should be surfaced separately."""
        plugins = [
            {
                "name": "wp-lightweight-debug",
                "status": "inactive",
                "update": "none",
                "version": "1.0.0",
                "update_version": "",
                "auto_update": "off"
            }
        ]

        result = classify_plugins(plugins)

        assert len(result["inactive"]) == 1
        assert result["inactive"][0]["name"] == "wp-lightweight-debug"

    def test_flags_active_plugins_with_auto_update_off(self):
        """Active plugins with auto-update disabled should be flagged."""
        plugins = [
            {
                "name": "imagify",
                "status": "active",
                "update": "none",
                "version": "2.2.8",
                "update_version": "",
                "auto_update": "off"
            }
        ]

        result = classify_plugins(plugins)

        assert len(result["auto_update_off"]) == 1

    def test_does_not_flag_inactive_plugins_for_auto_update(self):
        """Inactive plugins should not appear in auto_update_off list."""
        plugins = [
            {
                "name": "wp-lightweight-debug",
                "status": "inactive",
                "update": "none",
                "version": "1.0.0",
                "update_version": "",
                "auto_update": "off"
            }
        ]

        result = classify_plugins(plugins)

        assert len(result["auto_update_off"]) == 0

    def test_up_to_date_plugin_not_flagged(self):
        """Plugins with no updates available should appear in up_to_date."""
        plugins = [
            {
                "name": "acf-pro",
                "status": "active",
                "update": "none",
                "version": "6.8.4",
                "update_version": "",
                "auto_update": "on"
            }
        ]

        result = classify_plugins(plugins)

        assert len(result["up_to_date"]) == 1
        assert len(result["needs_update"]) == 0

    def test_total_count_excludes_nothing(self):
        """Total count should reflect all plugins passed in."""
        plugins = [
            {"name": "plugin-a", "status": "active", "update": "none",
             "version": "1.0.0", "update_version": "", "auto_update": "on"},
            {"name": "plugin-b", "status": "inactive", "update": "none",
             "version": "1.0.0", "update_version": "", "auto_update": "off"},
            {"name": "plugin-c", "status": "active", "update": "available",
             "version": "1.0.0", "update_version": "2.0.0", "auto_update": "off"},
        ]

        result = classify_plugins(plugins)

        assert result["total"] == 3

    def test_empty_plugin_list(self):
        """Empty plugin list should return zeroed classification."""
        result = classify_plugins([])

        assert result["total"] == 0
        assert result["needs_update"] == []
        assert result["major_version_jumps"] == []
        assert result["inactive"] == []


# ---------------------------------------------------------------------------
# get_plugin_list
# ---------------------------------------------------------------------------

class TestGetPluginList:
    """Tests for WP-CLI plugin list retrieval."""

    def test_filters_out_dropins(self):
        """Drop-in pseudo-plugins should be excluded from results."""
        mock_output = json.dumps([
            {"name": "real-plugin", "status": "active", "update": "none",
             "version": "1.0.0", "update_version": "", "auto_update": "on"},
            {"name": "db.php", "status": "dropin", "update": "none",
             "version": "", "update_version": "", "auto_update": "off"}
        ])

        with patch("audit_plugins.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, stderr="")
            result = get_plugin_list("/some/wp/path")

        assert len(result) == 1
        assert result[0]["name"] == "real-plugin"

    def test_strips_deprecation_warnings_before_json(self):
        """PHP deprecation warnings printed before JSON should be stripped."""
        deprecation = "Deprecated: some PHP warning\n"
        json_data = json.dumps([
            {"name": "my-plugin", "status": "active", "update": "none",
             "version": "1.0.0", "update_version": "", "auto_update": "on"}
        ])
        mock_output = deprecation + json_data

        with patch("audit_plugins.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, stderr="")
            result = get_plugin_list("/some/wp/path")

        assert result is not None
        assert len(result) == 1

    def test_returns_none_when_no_json_in_output(self):
        """Should return None if WP-CLI output contains no JSON array."""
        with patch("audit_plugins.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Error: no WordPress found", stderr="")
            result = get_plugin_list("/bad/path")

        assert result is None

    def test_returns_none_on_exception(self):
        """Should return None if subprocess raises an exception."""
        with patch("audit_plugins.subprocess.run", side_effect=Exception("WP-CLI not found")):
            result = get_plugin_list("/some/path")

        assert result is None
