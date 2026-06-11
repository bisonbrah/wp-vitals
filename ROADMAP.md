# wp-vitals Roadmap

A growing suite of CLI tools for WordPress developers who are swamped, context-switching between projects, and need a
fast TL;DR on how broken a site is before diving in.

---

## Current Scripts

### `report.py` - Complete

Unified site health orchestrator. Runs all audits against a single WordPress install in one pass and outputs a
consolidated brief covering logs, plugins, and theme dependencies. Includes an executive summary and ready-to-paste
debug prompts tailored to the specific issues found.

**Flags:** `--site` (required), `--theme`, `--days`

---

### `main.py` - Complete

Analyzes WordPress debug logs across all local installs. Surfaces critical issues, common error types, and recommended
fixes using Claude AI. Prioritizes most recently active sites first and filters by date range.

**Planned enhancement:** For each identified issue, generate a ready-to-paste prompt the developer can drop into Claude
or their LLM of choice to dig deeper. Tailored to the specific error, file, and plugin version -- so you skip the
generic search and go straight to a focused debugging session.

**Flags:** `--days`, `--limit`, `--site`

---

### `audit_theme.py` - Complete

Analyzes a WordPress theme's full dependency health. Detects the theme framework and build tool, recommends the correct
Node version via nvm, separates safe npm updates from locked dependencies, and surfaces vulnerabilities with
framework-aware upgrade guidance.

**Flags:** `--site`, `--theme`, `--path`

---

### `audit_plugins.py` - Complete

Audits installed WordPress plugins using WP-CLI. Flags outdated plugins, major version jumps, inactive plugins, and
auto-update status. Provides prioritized update recommendations with framework-aware context.

**Flags:** `--site`, `--path`

---

## Planned: Web Dashboard

A Django-based web interface for visualizing health reports across multiple sites.

- Run audits from the browser
- Color-coded health status per site (Critical / Warning / Healthy)
- Historical report storage and comparison via Postgres
- Aggregate view across all local installs
- Client-shareable report URLs