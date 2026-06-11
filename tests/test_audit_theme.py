"""
Tests for wp-vitals audit_theme.py

Run with:
    pytest tests/test_audit_theme.py -v
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path so we can import audit_theme
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit_theme import detect_framework, summarize_audit, read_json_file, find_theme_dirs


# ---------------------------------------------------------------------------
# detect_framework
# ---------------------------------------------------------------------------

class TestDetectFramework:
    """Tests for theme framework and Node version detection."""

    def test_detects_sage_9(self):
        """Sage 9 sites using Laravel Mix should recommend Node 14.16.0."""
        package_json = {
            "devDependencies": {
                "laravel-mix": "^6.0.0",
                "browser-sync": "^2.0.0"
            }
        }

        result = detect_framework(package_json)

        assert result["framework"] == "Sage 9"
        assert "14.16.0" in result["recommended_node"]

    def test_detects_sage_10(self):
        """Sage 10 sites using @roots/bud should recommend Node 18.x."""
        package_json = {
            "devDependencies": {
                "@roots/sage": "^10.0.0",
                "@roots/bud": "^6.20.0"
            }
        }

        result = detect_framework(package_json)

        assert result["framework"] == "Sage 10"
        assert "18" in result["recommended_node"]

    def test_detects_sage_11(self):
        """Sage 11 sites using @roots/sage without @roots/bud should recommend Node 20.x."""
        package_json = {
            "devDependencies": {
                "@roots/sage": "^11.0.0"
            }
        }

        result = detect_framework(package_json)

        assert result["framework"] == "Sage 11"
        assert "20" in result["recommended_node"]

    def test_detects_generic_webpack(self):
        """Themes with webpack but no recognized framework should fall back gracefully."""
        package_json = {
            "devDependencies": {
                "webpack": "^5.0.0"
            }
        }

        result = detect_framework(package_json)

        assert "Webpack" in result["framework"]
        assert result["recommended_node"] is not None

    def test_unknown_framework_returns_safe_default(self):
        """Themes with no recognized build tool should return a safe Node default."""
        package_json = {
            "devDependencies": {
                "some-random-tool": "^1.0.0"
            }
        }

        result = detect_framework(package_json)

        assert result["framework"] == "Unknown"
        assert result["recommended_node"] is not None

    def test_returns_build_tool(self):
        """Framework detection should always return a build_tool value."""
        package_json = {
            "devDependencies": {
                "@roots/sage": "^10.0.0",
                "@roots/bud": "^6.20.0"
            }
        }

        result = detect_framework(package_json)

        assert "build_tool" in result
        assert result["build_tool"] is not None

    def test_checks_both_dependencies_and_dev_dependencies(self):
        """Framework detection should scan both dependencies and devDependencies."""
        package_json = {
            "dependencies": {
                "@roots/sage": "^10.0.0"
            },
            "devDependencies": {
                "@roots/bud": "^6.20.0"
            }
        }

        result = detect_framework(package_json)

        assert result["framework"] == "Sage 10"


# ---------------------------------------------------------------------------
# summarize_audit
# ---------------------------------------------------------------------------

class TestSummarizeAudit:
    """Tests for npm audit JSON summarization."""

    def test_extracts_vulnerability_counts(self):
        """Should correctly extract vulnerability counts from audit metadata."""
        audit_data = {
            "metadata": {
                "vulnerabilities": {
                    "critical": 1,
                    "high": 5,
                    "moderate": 3,
                    "low": 2,
                    "total": 11
                }
            },
            "vulnerabilities": {}
        }

        result = summarize_audit(audit_data)

        assert result["counts"]["critical"] == 1
        assert result["counts"]["high"] == 5
        assert result["counts"]["total"] == 11

    def test_sorts_by_severity(self):
        """Top vulnerabilities should be sorted critical first, then high, moderate, low."""
        audit_data = {
            "metadata": {"vulnerabilities": {}},
            "vulnerabilities": {
                "low-pkg": {
                    "severity": "low",
                    "via": [{"title": "Low issue", "source": 1}],
                    "fixAvailable": True
                },
                "critical-pkg": {
                    "severity": "critical",
                    "via": [{"title": "Critical issue", "source": 2}],
                    "fixAvailable": True
                },
                "high-pkg": {
                    "severity": "high",
                    "via": [{"title": "High issue", "source": 3}],
                    "fixAvailable": True
                }
            }
        }

        result = summarize_audit(audit_data)
        severities = [v["severity"] for v in result["top_vulnerabilities"]]

        assert severities[0] == "critical"
        assert severities[1] == "high"
        assert severities[2] == "low"

    def test_skips_transitive_wrappers(self):
        """Vulnerabilities with no direct advisory (transitive wrappers) should be excluded."""
        audit_data = {
            "metadata": {"vulnerabilities": {}},
            "vulnerabilities": {
                "wrapper-pkg": {
                    "severity": "high",
                    "via": ["some-other-package"],  # string, not dict -- transitive
                    "fixAvailable": True
                }
            }
        }

        result = summarize_audit(audit_data)

        assert len(result["top_vulnerabilities"]) == 0

    def test_limits_to_ten_vulnerabilities(self):
        """Should return no more than 10 top vulnerabilities regardless of total count."""
        vulns = {}
        for i in range(20):
            vulns[f"pkg-{i}"] = {
                "severity": "high",
                "via": [{"title": f"Issue {i}", "source": i}],
                "fixAvailable": True
            }

        audit_data = {
            "metadata": {"vulnerabilities": {}},
            "vulnerabilities": vulns
        }

        result = summarize_audit(audit_data)

        assert len(result["top_vulnerabilities"]) <= 10

    def test_empty_vulnerabilities_returns_empty_list(self):
        """Audit with no vulnerabilities should return an empty top_vulnerabilities list."""
        audit_data = {
            "metadata": {"vulnerabilities": {"total": 0}},
            "vulnerabilities": {}
        }

        result = summarize_audit(audit_data)

        assert result["top_vulnerabilities"] == []


# ---------------------------------------------------------------------------
# read_json_file
# ---------------------------------------------------------------------------

class TestReadJsonFile:
    """Tests for JSON file reading utility."""

    def test_reads_valid_json_file(self, tmp_path):
        """Should return parsed dict for a valid JSON file."""
        data = {"name": "my-theme", "version": "1.0.0"}
        json_file = tmp_path / "package.json"
        json_file.write_text(json.dumps(data))

        result = read_json_file(str(json_file))

        assert result == data

    def test_returns_none_for_missing_file(self):
        """Should return None if the file does not exist."""
        result = read_json_file("/nonexistent/path/package.json")

        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        """Should return None if the file contains invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("this is not json {{{")

        result = read_json_file(str(bad_file))

        assert result is None


# ---------------------------------------------------------------------------
# find_theme_dirs
# ---------------------------------------------------------------------------

class TestFindThemeDirs:
    """Tests for theme directory discovery."""

    def test_finds_theme_with_package_json(self, tmp_path):
        """Should return theme directories that contain a package.json."""
        theme_dir = tmp_path / "mysite" / "app" / "public" / "wp-content" / "themes" / "my-theme"
        theme_dir.mkdir(parents=True)
        (theme_dir / "package.json").write_text('{"name": "my-theme"}')

        with patch("audit_theme.LOCAL_SITES_PATH", str(tmp_path)):
            result = find_theme_dirs("mysite", None)

        assert len(result) == 1
        assert "my-theme" in result[0]

    def test_skips_themes_without_package_json(self, tmp_path):
        """Should ignore theme directories that don't have a package.json."""
        theme_dir = tmp_path / "mysite" / "app" / "public" / "wp-content" / "themes" / "no-node-theme"
        theme_dir.mkdir(parents=True)

        with patch("audit_theme.LOCAL_SITES_PATH", str(tmp_path)):
            result = find_theme_dirs("mysite", None)

        assert len(result) == 0

    def test_targets_specific_theme(self, tmp_path):
        """When theme is specified, should only return that theme directory."""
        themes_base = tmp_path / "mysite" / "app" / "public" / "wp-content" / "themes"
        for name in ["theme-a", "theme-b"]:
            d = themes_base / name
            d.mkdir(parents=True)
            (d / "package.json").write_text('{"name": "' + name + '"}')

        with patch("audit_theme.LOCAL_SITES_PATH", str(tmp_path)):
            result = find_theme_dirs("mysite", "theme-a")

        assert len(result) == 1
        assert "theme-a" in result[0]

    def test_returns_empty_list_for_missing_site(self):
        """Should return an empty list if the site directory doesn't exist."""
        with patch("audit_theme.LOCAL_SITES_PATH", "/nonexistent"):
            result = find_theme_dirs("ghost-site", None)

        assert result == []
