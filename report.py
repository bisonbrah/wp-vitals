"""
wp-vitals: Unified site health report.
Runs all available audits against a single WordPress install and surfaces
a consolidated brief -- logs, plugins, and theme dependencies in one pass.

Usage:
    python report.py --site evanghenry
    python report.py --site evanghenry --theme egh-custom
    python report.py --site evanghenry --days 7
"""

import os
import argparse
from anthropic import Anthropic
from dotenv import load_dotenv

from main import run_log_analysis
from audit_plugins import run_plugin_audit
from audit_theme import run_theme_audit

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def parse_args() -> argparse.Namespace:
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(description="wp-vitals - Unified WordPress site health report")
    parser.add_argument("--site", type=str, required=True,
                        help="Site folder name under LOCAL_SITES_PATH (e.g. --site evanghenry)")
    parser.add_argument("--theme", type=str, default=None,
                        help="Theme folder name to target (e.g. --theme egh-custom)")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days back to include in log analysis (default: 30)")
    return parser.parse_args()


def generate_executive_summary(site: str, log_result: dict | None, plugin_result: dict | None,
                               theme_result: dict | None) -> str | None:
    """
    Send all audit results to Claude for a unified executive summary.

    Synthesizes findings across logs, plugins, and theme dependencies into
    a single prioritized brief the developer can act on immediately.

    :param site: Site folder name being reported on.
    :param log_result: Structured result from run_log_analysis().
    :param plugin_result: Structured result from run_plugin_audit().
    :param theme_result: Structured result from run_theme_audit().
    :return: Formatted executive summary string from Claude.
    """
    log_report = log_result.get("report", "No log data available.") if log_result else "No log data available."
    plugin_report = plugin_result.get("report",
                                      "No plugin data available.") if plugin_result else "No plugin data available."
    theme_report = theme_result.get("report",
                                    "No theme data available.") if theme_result else "No theme data available."

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": f"""You are a WordPress developer reviewing a full site health brief for: {site}

You have three audit reports below. Synthesize them into a single executive summary
a developer can read in 60 seconds before diving into a new project.

LOG ANALYSIS:
{log_report}

PLUGIN AUDIT:
{plugin_report}

THEME DEPENDENCY AUDIT:
{theme_report}

Provide:
1. **Overall Site Health** - single status: CRITICAL / WARNING / HEALTHY
2. **Top 3 Priority Actions** - the three most important things to do right now, in order
3. **Biggest Risk** - the single most dangerous issue across all three audits
4. **Quick Wins** - anything that can be fixed in under 5 minutes

Keep it tight. Max 20 lines. A developer is about to start working on this site."""
            }
        ]
    )

    return message.content[0].text


def generate_debug_prompts(log_result: dict | None, plugin_result: dict | None,
                           theme_result: dict | None) -> str | None:
    """
    Generate ready-to-paste Claude prompts for the top issues found across all audits.

    Tailored to the specific errors, files, plugin versions, and framework detected
    so the developer can go straight to a focused debugging session.

    :param log_result: Structured result from run_log_analysis().
    :param plugin_result: Structured result from run_plugin_audit().
    :param theme_result: Structured result from run_theme_audit().
    :return: Formatted string containing ready-to-paste debug prompts.
    """
    log_report = log_result.get("report", "") if log_result else ""
    plugin_report = plugin_result.get("report", "") if plugin_result else ""
    theme_report = theme_result.get("report", "") if theme_result else ""

    combined = f"{log_report}\n{plugin_report}\n{theme_report}".strip()
    if not combined:
        return None

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""Based on these WordPress site audit findings, generate 2-3 ready-to-paste prompts
a developer can drop directly into Claude or another LLM to dig deeper into the top issues.

Each prompt should:
- Reference the specific error, file, plugin name, or version number from the findings
- Ask for a concrete fix, not a general explanation
- Be self-contained so it works without additional context

AUDIT FINDINGS:
{combined}

Format each prompt clearly labeled as "Prompt 1:", "Prompt 2:", etc.
Keep each prompt under 100 words."""
            }
        ]
    )

    return message.content[0].text


def main() -> None:
    """Main entry point. Orchestrates all audits and generates unified site health report."""
    args = parse_args()

    print(f"\nRunning full health report for: {args.site}")
    print("=" * 60)

    # Run all three audits
    print("\n[ 1/3 ] Analyzing error logs...")
    log_result = run_log_analysis(site=args.site, days=args.days)

    print("[ 2/3 ] Auditing plugins...")
    plugin_result = run_plugin_audit(site=args.site)

    print("[ 3/3 ] Auditing theme dependencies...")
    theme_result = run_theme_audit(site=args.site, theme=args.theme)

    print("\n" + "=" * 60)
    print("WP VITALS - SITE HEALTH REPORT")
    print(f"Site: {args.site}")
    print("=" * 60)

    # Individual audit sections
    if log_result and log_result.get("report"):
        print("\n--- ERROR LOGS ---")
        print(log_result["report"])
    else:
        print("\n--- ERROR LOGS ---")
        print("No recent log entries found.")

    if plugin_result and plugin_result.get("report"):
        print("\n--- PLUGINS ---")
        print(plugin_result["report"])
    else:
        print("\n--- PLUGINS ---")
        print("Could not retrieve plugin data. Is the site running?")

    if theme_result and theme_result.get("report"):
        print("\n--- THEME DEPENDENCIES ---")
        framework = theme_result.get("framework", {})
        print(
            f"Framework: {framework.get('framework', 'Unknown')} | Node: {framework.get('recommended_node', 'Unknown')}")
        print(theme_result["report"])
    else:
        print("\n--- THEME DEPENDENCIES ---")
        print("No theme with package.json found.")

    # Executive summary
    print("\n" + "=" * 60)
    print("EXECUTIVE SUMMARY")
    print("=" * 60)
    summary = generate_executive_summary(args.site, log_result, plugin_result, theme_result)
    if summary:
        print(summary)

    # Ready-to-paste debug prompts
    print("\n" + "=" * 60)
    print("DEBUG PROMPTS")
    print("=" * 60)
    prompts = generate_debug_prompts(log_result, plugin_result, theme_result)
    if prompts:
        print(prompts)

    print("\n" + "=" * 60)
    print("Report complete.")


if __name__ == "__main__":
    main()
