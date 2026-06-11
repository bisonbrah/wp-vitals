"""
wp-vitals: Analyzes WordPress debug logs across local installs.
Surfaces critical issues, common error types, and recommended fixes using Claude AI.

Can be run standalone or imported by report.py for unified site reporting.

Usage:
    python main.py                        # Analyze 10 most recent sites, last 30 days
    python main.py --days 7 --limit 5    # Last 7 days, top 5 sites
    python main.py --site my-site        # Target a specific site by folder name
"""

import os
import glob
import argparse
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
LOCAL_SITES_PATH = os.getenv("LOCAL_SITES_PATH")


def parse_args() -> argparse.Namespace:
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(description="wp-vitals - Analyze WordPress debug logs")
    parser.add_argument("--days", type=int, default=30,
                        help="Only analyze log entries from the last N days (default: 30)")
    parser.add_argument("--limit", type=int, default=10,
                        help="Max number of sites to analyze, most recent first (default: 10)")
    parser.add_argument("--site", type=str, default=None,
                        help="Target a specific site by folder name (e.g. --site my-site)")
    return parser.parse_args()


def find_log_files(site_filter: str | None = None) -> list[str]:
    """
    Discover WordPress debug log files under LOCAL_SITES_PATH.

    Searches common log locations for Local by Flywheel installs.
    Results are sorted by last modified time, newest first.

    :param site_filter: Optional site folder name to scope the search to a single install.
    :return: List of absolute paths to discovered log files.
    """
    patterns = [
        f"{LOCAL_SITES_PATH}/*/app/public/wp-content/debug.log",
        f"{LOCAL_SITES_PATH}/*/logs/*.log",
        f"{LOCAL_SITES_PATH}/*/app/public/*.log",
    ]

    log_files = []
    for pattern in patterns:
        log_files.extend(glob.glob(pattern, recursive=True))

    if site_filter:
        log_files = [f for f in log_files if LOCAL_SITES_PATH and f.replace(LOCAL_SITES_PATH + "/", "").split("/")[
            0].lower() == site_filter.lower()]

    log_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

    return log_files


def filter_recent_lines(content: str, days: int) -> str:
    """
    Filter log content to only include entries from the last N days.

    Parses WordPress timestamp format: [09-Jun-2026 14:23:11 UTC]
    Lines without a parseable timestamp (stack traces, continuation lines)
    are always included to preserve context.

    :param content: Raw log file content.
    :param days: Number of days back to include.
    :return: Filtered log content as a single string.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = []

    for line in content.splitlines():
        if line.startswith("["):
            try:
                timestamp_str = line[1:line.index("]")]
                log_time = datetime.strptime(timestamp_str, "%d-%b-%Y %H:%M:%S %Z")
                log_time = log_time.replace(tzinfo=timezone.utc)
                if log_time >= cutoff:
                    filtered.append(line)
            except (ValueError, IndexError):
                filtered.append(line)
        else:
            filtered.append(line)

    return "\n".join(filtered)


def analyze_logs(site_name: str, log_content: str) -> str | None:
    """
    Send log content to Claude for analysis and return a health report.

    Uses explicit health criteria to ensure consistent severity classification
    across runs. Truncates log content to 5,000 characters to control API costs.

    :param site_name: Human-readable site identifier for context in the prompt.
    :param log_content: Filtered log content to analyze.
    :return: Formatted health report string, or None if log content is empty.
    """
    if not log_content.strip():
        return None

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""You are a WordPress developer analyzing error logs for site: {site_name}

Use these exact health criteria:
- CRITICAL: Any PHP Fatal error, white screen, database connection failure, or site-down condition
- WARNING: Deprecation notices, plugin conflicts, non-fatal PHP warnings, missing assets
- HEALTHY: Only debug/info logs, no actual errors

Analyze these logs and provide:
1. Top 3 most critical issues (be specific, include file/line if available)
2. Most common error type
3. Overall health: CRITICAL / WARNING / HEALTHY
4. One recommended action to resolve the primary issue

Keep it concise. Max 15 lines.

Logs:
{log_content[:5000]}"""
            }
        ]
    )

    return message.content[0].text


def run_log_analysis(site: str, days: int = 30) -> dict | None:
    """
    Run log analysis for a single site and return structured results.

    Designed to be called by report.py for unified site reporting.
    Returns None if no log file is found or no recent entries exist.

    :param site: Site folder name under LOCAL_SITES_PATH.
    :param days: Number of days back to include in analysis.
    :return: Dict with site_name, report, and skipped status, or None if no logs found.
    """
    log_files = find_log_files(site_filter=site)

    if not log_files:
        return None

    file_path = log_files[0]

    try:
        with open(file_path, 'r', errors='ignore') as f:
            raw_content = f.read()

        if not raw_content.strip():
            return None

        filtered_content = filter_recent_lines(raw_content, days)

        if not filtered_content.strip():
            return {"site_name": site, "report": None, "skipped": True, "reason": f"No entries in last {days} days"}

        report = analyze_logs(site, filtered_content)
        return {"site_name": site, "report": report, "skipped": False}

    except Exception as e:
        return {"site_name": site, "report": None, "skipped": True, "reason": str(e)}


def main() -> None:
    """Main entry point. Orchestrates log discovery, filtering, and analysis."""
    args = parse_args()

    print("Scanning for WordPress log files...")
    log_files = find_log_files(site_filter=args.site)

    if not log_files:
        msg = f"No log files found for site '{args.site}'." if args.site else "No log files found. Check your LOCAL_SITES_PATH."
        print(msg)
        return

    if not args.site:
        log_files = log_files[:args.limit]

    print(
        f"Analyzing {len(log_files)} site(s) | Last {args.days} days | {'Site: ' + args.site if args.site else 'Most recent first'}\n")
    print("=" * 60)
    print("WP VITALS - LOG REPORT")
    print("=" * 60)

    for file_path in log_files:
        site_name = file_path.replace(LOCAL_SITES_PATH + "/", "").split("/")[0]
        try:
            with open(file_path, 'r', errors='ignore') as f:
                raw_content = f.read()

            if not raw_content.strip():
                continue

            filtered_content = filter_recent_lines(raw_content, args.days)

            if not filtered_content.strip():
                print(f"\n--- {site_name} --- (no entries in last {args.days} days, skipping)")
                continue

            print(f"\nAnalyzing: {site_name}...")
            report = analyze_logs(site_name, filtered_content)

            if report:
                print(f"\n--- {site_name} ---")
                print(report)

        except Exception as e:
            print(f"Could not process {site_name}: {e}")

    print("\n" + "=" * 60)
    print("Analysis complete.")


if __name__ == "__main__":
    main()
