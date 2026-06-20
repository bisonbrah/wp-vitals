# wp-vitals

A growing suite of CLI tools for WordPress developers who are swamped, context-switching between projects, and need a
fast TL;DR on how broken a site is before diving in.

---

## Requirements

- Python 3.10+
- Node.js + npm (for theme audits)
- WP-CLI (for plugin audits)
- [Local by Flywheel](https://localwp.com/) (or any local WordPress environment)
- Anthropic API key ([get one here](https://console.anthropic.com))

---

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/bisonbrah/wp-vitals.git
   cd wp-vitals
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root:
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   LOCAL_SITES_PATH=/path/to/your/local/sites
   ```

---

## Scripts

### `report.py` - Unified Site Health Report

Runs all audits against a single WordPress install in one pass. Outputs a full
site brief covering logs, plugins, and theme dependencies -- plus an executive
summary and ready-to-paste debug prompts for the top issues found.

```bash
# Full report for a site
python report.py --site my-client-site

# Target a specific theme
python report.py --site my-client-site --theme my-theme

# Scope log analysis to last 7 days
python report.py --site my-client-site --days 7
```

| Flag      | Default      | Description                                    |
|-----------|--------------|------------------------------------------------|
| `--site`  | **required** | Site folder name under LOCAL_SITES_PATH        |
| `--theme` | None         | Theme folder name to target                    |
| `--days`  | 30           | Number of days back to include in log analysis |

---

### `main.py` - Log Analyzer

Analyzes WordPress debug logs for a target install. Surfaces critical issues, common error types, and recommended
fixes. Filters by date range.

```bash
# Analyze a specific site, last 30 days (default)
python main.py --site my-client-site

# Scope to last 7 days
python main.py --site my-client-site --days 7
```

| Flag     | Default      | Description                                   |
|----------|--------------|-----------------------------------------------|
| `--site` | **required** | Target a specific site by folder name         |
| `--days` | 30           | Only analyze log entries from the last N days |

---

### `audit_theme.py` - Theme Dependency Auditor

Analyzes a WordPress theme's full dependency health. Detects the theme framework and build tool, recommends the correct
Node version via nvm, separates safe npm updates from locked dependencies, and surfaces vulnerabilities with
framework-aware upgrade guidance.

```bash
# Audit a specific theme
python audit_theme.py --site my-client-site --theme my-theme

# Audit by full path
python audit_theme.py --path /full/path/to/theme

# Audit all themes under a site
python audit_theme.py --site my-client-site
```

| Flag      | Default | Description                                     |
|-----------|---------|-------------------------------------------------|
| `--site`  | None    | Site folder name under LOCAL_SITES_PATH         |
| `--theme` | None    | Theme folder name. If omitted, scans all themes |
| `--path`  | None    | Full path to a theme directory                  |

---

### `audit_plugins.py` - Plugin Auditor

Audits installed WordPress plugins using WP-CLI. Flags outdated plugins, major version jumps, inactive plugins, and
auto-update status. Automatically resolves Local by Flywheel's MySQL socket environment so no manual shell setup is
required.

```bash
# Audit plugins for a specific site
python audit_plugins.py --site my-client-site

# Audit by full WordPress root path
python audit_plugins.py --path /full/path/to/wordpress
```

| Flag     | Default | Description                                   |
|----------|---------|-----------------------------------------------|
| `--site` | None    | Site folder name under LOCAL_SITES_PATH       |
| `--path` | None    | Full path to WordPress root. Overrides --site |

---

## Health Criteria

| Status   | Conditions                                                                                                    |
|----------|---------------------------------------------------------------------------------------------------------------|
| CRITICAL | PHP Fatal error, white screen, database connection failure, site-down condition, critical npm vulnerabilities |
| WARNING  | Deprecation notices, plugin conflicts, non-fatal PHP warnings, high npm vulnerabilities, outdated plugins     |
| HEALTHY  | Only debug/info logs, no errors, clean dependency audit, all plugins current                                  |

---

## Notes

- `.env` is gitignored -- never commit your API key
- Logs are truncated to 5,000 characters per site to keep API costs minimal
- Typical cost per full report run is a few cents using Claude Haiku
- WP-CLI must be installed and the target site must be running for plugin audits