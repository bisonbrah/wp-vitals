# wp-vitals Roadmap

A growing suite of CLI tools for WordPress developers who are swamped, context-switching between projects, and need a fast TL;DR on how broken a site is before diving in.

---

## Current Scripts

### `analyze_logs.py` - Partially Complete
Analyzes WordPress debug logs across all local installs. Surfaces critical issues, common error types, and recommended fixes using Claude AI.

**Planned enhancement:** For each identified issue, generate a ready-to-paste 
prompt the developer can drop into Claude or their LLM of choice to dig deeper. 
Tailored to the specific error, file, and plugin version -- so you skip the 
generic search and go straight to a focused debugging session.

**Flags:** `--days`, `--limit`, `--site`

---

## Planned Scripts

### `audit_plugins.py`
Audits installed plugins across a WordPress site. Checks for outdated versions against the WordPress.org API and flags known vulnerabilities.

- Pull installed plugin list via WP-CLI
- Compare against WordPress.org version data
- Flag plugins with available updates or known security issues
- Severity classification: Critical / Warning / Healthy

### `audit_packages.py`
Audits NPM dependencies in a WordPress theme. Targets Sage 9/10/11 and other modern theme setups using `package.json`.

- Run `npm audit` in the theme directory
- Parse JSON output for vulnerability severity
- Surface high and critical vulnerabilities with remediation steps
- Useful for aging Sage 9 sites with stale dependencies

### `analyze_lighthouse.py`
Runs a Lighthouse audit against a local or live URL and summarizes findings using Claude AI.

- Fire Lighthouse CLI headlessly against a target URL
- Export results as JSON
- Extract scores: Performance, Accessibility, SEO, Best Practices
- Surface specific audit failures with prioritized recommendations

### `audit_accessibility.py`
Analyzes a WordPress theme's PHP and Blade templates for common accessibility issues.

- Scan theme files for missing alt attributes, improper heading hierarchy, missing ARIA labels, and form input issues
- Flag violations by file and line number
- Severity classification aligned with WCAG 2.1 AA standards

---

## Planned: Unified Health Report

An orchestrator script (`report.py`) that runs all of the above against a target site and generates a single unified health report.

**Use case:** Point it at an aging Sage 9 client site and get back a full picture -- broken error logs, outdated plugins, vulnerable NPM packages, Lighthouse scores, and accessibility flags -- in one pass.

Output formats planned:
- Terminal (current)
- Markdown file
- HTML report

---

## Planned: Web Dashboard

A Django-based web interface for visualizing health reports across multiple sites.

- Run audits from the browser
- Color-coded health status per site (Critical / Warning / Healthy)
- Historical report storage and comparison
- Client-shareable report URLs