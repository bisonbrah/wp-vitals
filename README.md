# wp-vitals

A CLI agent that analyzes WordPress debug logs across all local installs and surfaces actionable health reports using Claude AI.

For each site it finds, it identifies:
- Top 3 critical issues with specific file and line references
- Most common error type
- Overall health status (Critical / Warning / Healthy)
- A recommended action to resolve the primary issue

Built for developers managing multiple local WordPress installs who don't want to manually grep through debug logs.

---

## Requirements

- Python 3.10+
- [Local by Flywheel](https://localwp.com/) (or any local WordPress environment)
- Anthropic API key ([get one here](https://console.anthropic.com))

---

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/bisonbrah/wp-health.git
   cd wp-health
   ```

2. Install dependencies:
   ```bash
   pip install anthropic python-dotenv
   ```

3. Create a `.env` file in the project root:
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   LOCAL_SITES_PATH=/path/to/your/local/sites
   ```

4. Run it:
   ```bash
   python main.py
   ```

---

## Usage

```bash
# Analyze 10 most recently active sites, last 30 days (default)
python main.py

# Scope to last 7 days, top 5 sites
python main.py --days 7 --limit 5

# Target a specific site
python main.py --site my-client-site

# Combine flags
python main.py --site my-client-site --days 7
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--days` | 30 | Only analyze log entries from the last N days |
| `--limit` | 10 | Max number of sites to analyze, most recent first |
| `--site` | None | Target a specific site by folder name |

---

## Example Output

```
============================================================
WP HEALTH REPORT
============================================================

Analyzing: my-client-site...

--- my-client-site ---
## Top 3 Critical Issues
1. Fatal Error in mobility-city-products.php (line 57) - Plugin throwing
   exception during wp-settings.php inclusion, preventing WordPress from loading
2. Maintenance Mode Active - Site displaying maintenance page as fallback
3. WP-CLI Bootstrap Failure - Command-line operations blocked

## Most Common Error Type
PHP Fatal Error - Plugin inclusion failure blocking entire site initialization

## Overall Health
CRITICAL - Site is down.

## Recommended Action
Disable the plugin immediately by renaming its folder, then debug line 57
for syntax errors before reactivating.
```

---

## Health Criteria

| Status | Conditions |
|--------|------------|
| 🔴 CRITICAL | PHP Fatal error, white screen, database connection failure, site-down condition |
| ⚠️ WARNING | Deprecation notices, plugin conflicts, non-fatal PHP warnings, missing assets |
| ✅ HEALTHY | Only debug/info logs, no actual errors |

---

## Notes

- `.env` is gitignored -- never commit your API key
- Sites are prioritized by most recently modified log file
- Sites with no log entries in the specified time window are skipped automatically
- Logs are truncated to 5,000 characters per site to keep API costs minimal
- Typical cost per full run across 10 sites is under a penny using Claude Haiku