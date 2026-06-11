"""
wp-vitals: Analyzes a WordPress theme's dependency health.
Detects the theme framework and version, determines the correct Node version,
and provides a safe upgrade path for NPM packages without breaking the build.

Can be run standalone or imported by report.py for unified site reporting.

Usage:
    python audit_theme.py --site evanghenry
    python audit_theme.py --site evanghenry --theme egh-custom
    python audit_theme.py --path /full/path/to/theme
"""

import os
import json
import argparse
import subprocess
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
LOCAL_SITES_PATH = os.getenv("LOCAL_SITES_PATH")


def parse_args() -> argparse.Namespace:
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(description="wp-vitals - Analyze WordPress theme dependency health")
    parser.add_argument("--site", type=str, default=None,
                        help="Site folder name under LOCAL_SITES_PATH (e.g. --site evanghenry)")
    parser.add_argument("--theme", type=str, default=None,
                        help="Theme folder name (e.g. --theme egh-custom)")
    parser.add_argument("--path", type=str, default=None,
                        help="Full path to a theme directory. Overrides --site and --theme.")
    return parser.parse_args()


def find_theme_dirs(site: str, theme: str | None) -> list[str]:
    """
    Locate theme directories containing a package.json under a given site.

    Searches common log locations for Local by Flywheel installs.
    Results are sorted by last modified time, newest first.

    :param site: Site folder name under LOCAL_SITES_PATH.
    :param theme: Optional specific theme folder name to target.
    :return: List of absolute paths to theme directories with package.json.
    """
    themes_path = os.path.join(LOCAL_SITES_PATH, site, "app", "public", "wp-content", "themes")

    if not os.path.exists(themes_path):
        print(f"Themes directory not found: {themes_path}")
        return []

    if theme:
        target = os.path.join(themes_path, theme)
        if os.path.exists(os.path.join(target, "package.json")):
            return [target]
        else:
            print(f"No package.json found in: {target}")
            return []

    results = []
    for entry in os.scandir(themes_path):
        if entry.is_dir() and os.path.exists(os.path.join(entry.path, "package.json")):
            results.append(entry.path)

    return results


def read_json_file(path: str) -> dict | None:
    """
    Read and parse a JSON file.

    :param path: Absolute path to the JSON file.
    :return: Parsed dict or None if file doesn't exist or is invalid.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def detect_framework(package_json: dict) -> dict:
    """
    Detect the theme framework, version, and recommended Node version
    from package.json dependencies.

    :param package_json: Parsed package.json contents.
    :return: Dict with framework name, version, build tool, recommended Node version, and notes.
    """
    all_deps = {}
    all_deps.update(package_json.get("dependencies", {}))
    all_deps.update(package_json.get("devDependencies", {}))

    # Sage 11 -- Vite based
    if "@roots/sage" in all_deps and "@roots/bud" not in all_deps:
        return {
            "framework": "Sage 11",
            "version": all_deps.get("@roots/sage", "unknown"),
            "build_tool": "Vite",
            "recommended_node": "20.x LTS",
            "notes": "Vite-based. Node 18+ required, Node 20 LTS recommended."
        }

    # Sage 10 -- Bud based
    if "@roots/sage" in all_deps and "@roots/bud" in all_deps:
        bud_version = all_deps.get("@roots/bud", "unknown")
        return {
            "framework": "Sage 10",
            "version": all_deps.get("@roots/sage", "unknown"),
            "build_tool": f"@roots/bud {bud_version}",
            "recommended_node": "18.x LTS",
            "notes": "Bud-based build tool. Node 16-18 recommended. Avoid Node 20+ with older bud versions."
        }

    # Sage 9 -- Webpack / Laravel Mix based
    if "laravel-mix" in all_deps or (
            "@roots/sage" not in all_deps and "webpack" in all_deps
            and any(k.startswith("browser-sync") for k in all_deps)
    ):
        return {
            "framework": "Sage 9",
            "version": all_deps.get("@roots/sage", "unknown"),
            "build_tool": "Webpack via Laravel Mix",
            "recommended_node": "14.16.0",
            "notes": "Webpack 4 / Laravel Mix stack. Requires Node 14.16.0 exactly via nvm. Node 16+ will break the build."
        }

    # Fallback -- generic webpack
    if "webpack" in all_deps:
        webpack_version = all_deps.get("webpack", "unknown")
        return {
            "framework": "Unknown (Webpack-based)",
            "version": "unknown",
            "build_tool": f"Webpack {webpack_version}",
            "recommended_node": "16.x",
            "notes": "Could not detect theme framework. Webpack detected -- try Node 16 LTS as a safe default."
        }

    return {
        "framework": "Unknown",
        "version": "unknown",
        "build_tool": "unknown",
        "recommended_node": "18.x LTS",
        "notes": "Could not detect framework or build tool. Node 18 LTS is a safe default to try."
    }


def run_npm_audit(theme_dir: str) -> dict | None:
    """
    Run npm audit --json in the given theme directory and return parsed results.

    :param theme_dir: Absolute path to the theme directory.
    :return: Parsed npm audit JSON as a dict, or None on failure.
    """
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            cwd=theme_dir,
            capture_output=True,
            text=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Failed to run npm audit in {theme_dir}: {e}")
        return None


def summarize_audit(audit_data: dict) -> dict:
    """
    Extract a concise vulnerability summary from raw npm audit JSON.

    :param audit_data: Raw parsed npm audit output.
    :return: Summary dict with counts and top vulnerabilities.
    """
    meta = audit_data.get("metadata", {}).get("vulnerabilities", {})
    vulns = audit_data.get("vulnerabilities", {})

    severity_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}

    top_vulns = []
    for name, data in vulns.items():
        severity = data.get("severity", "low")
        via = data.get("via", [])
        advisories = [v for v in via if isinstance(v, dict)]
        if advisories:
            top_vulns.append({
                "package": name,
                "severity": severity,
                "title": advisories[0].get("title", "Unknown"),
                "fixAvailable": bool(data.get("fixAvailable"))
            })

    top_vulns.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return {
        "counts": meta,
        "top_vulnerabilities": top_vulns[:10]
    }


def analyze_theme(theme_name: str, framework: dict, audit_summary: dict, composer_json: dict | None) -> str | None:
    """
    Send full theme dependency context to Claude for intelligent upgrade guidance.

    :param theme_name: Display name of the theme being analyzed.
    :param framework: Detected framework info from detect_framework().
    :param audit_summary: Condensed vulnerability summary from summarize_audit().
    :param composer_json: Parsed composer.json contents or None if not present.
    :return: Formatted analysis string from Claude.
    """
    counts = audit_summary.get("counts", {})
    vulns_text = json.dumps(audit_summary.get("top_vulnerabilities", []), indent=2)

    composer_info = "Not present"
    if composer_json:
        composer_deps = composer_json.get("require", {})
        composer_info = json.dumps(composer_deps, indent=2)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": f"""You are an expert WordPress developer analyzing theme dependency health for: {theme_name}

DETECTED FRAMEWORK:
- Framework: {framework['framework']}
- Version: {framework['version']}
- Build tool: {framework['build_tool']}
- Recommended Node version: {framework['recommended_node']}
- Notes: {framework['notes']}

NPM VULNERABILITY COUNTS:
- Critical: {counts.get('critical', 0)}
- High: {counts.get('high', 0)}
- Moderate: {counts.get('moderate', 0)}
- Low: {counts.get('low', 0)}
- Total: {counts.get('total', 0)}

TOP VULNERABILITIES:
{vulns_text}

COMPOSER DEPENDENCIES:
{composer_info}

Based on the detected framework, provide:

1. **Node Version Recommendation** - exact version to use with nvm, and why
2. **Safe to Update** - list packages that can be updated without breaking the build
3. **Do NOT Update** - packages locked to this framework version that would break things
4. **Critical Fixes** - immediate actions for critical/high vulnerabilities that are safe to apply
5. **Overall Health** - CRITICAL / WARNING / HEALTHY
6. **One Key Insight** - something specific to this framework version the developer should know

Be specific and practical. A developer is going to act on this output directly.
Max 20 lines."""
            }
        ]
    )

    return message.content[0].text


def run_theme_audit(site: str | None = None, theme: str | None = None, path: str | None = None) -> dict | None:
    """
    Run theme dependency audit for a single theme and return structured results.

    Designed to be called by report.py for unified site reporting.
    Returns None if no theme directory with package.json is found.

    :param site: Site folder name under LOCAL_SITES_PATH.
    :param theme: Optional specific theme folder name to target.
    :param path: Explicit full path to a theme directory. Overrides site and theme.
    :return: Dict with theme_name, framework, audit_summary, and report, or None on failure.
    """
    if path:
        theme_dirs = [path]
    elif site:
        theme_dirs = find_theme_dirs(site, theme)
    else:
        return None

    if not theme_dirs:
        return None

    # For report.py, target the first (most relevant) theme only
    theme_dir = theme_dirs[0]
    theme_name = os.path.basename(theme_dir)

    package_json = read_json_file(os.path.join(theme_dir, "package.json"))
    if not package_json:
        return None

    composer_json = read_json_file(os.path.join(theme_dir, "composer.json"))
    framework = detect_framework(package_json)
    audit_data = run_npm_audit(theme_dir)

    if not audit_data:
        return None

    audit_summary = summarize_audit(audit_data)
    report = analyze_theme(theme_name, framework, audit_summary, composer_json)

    return {
        "theme_name": theme_name,
        "framework": framework,
        "audit_summary": audit_summary,
        "report": report
    }


def main() -> None:
    """Main entry point. Orchestrates theme discovery, framework detection, and analysis."""
    args = parse_args()

    if args.path:
        theme_dirs = [args.path]
    elif args.site:
        theme_dirs = find_theme_dirs(args.site, args.theme)
    else:
        print("Provide --site or --path to a theme directory.")
        return

    if not theme_dirs:
        print("No theme directories found with package.json.")
        return

    print(f"Found {len(theme_dirs)} theme(s) to audit\n")
    print("=" * 60)
    print("WP VITALS - THEME DEPENDENCY REPORT")
    print("=" * 60)

    for theme_dir in theme_dirs:
        theme_name = os.path.basename(theme_dir)
        print(f"\nAnalyzing: {theme_name}...")

        package_json = read_json_file(os.path.join(theme_dir, "package.json"))
        if not package_json:
            print(f"  Could not read package.json in {theme_dir}")
            continue

        composer_json = read_json_file(os.path.join(theme_dir, "composer.json"))
        framework = detect_framework(package_json)

        print(f"  Framework: {framework['framework']} | Build tool: {framework['build_tool']}")
        print(f"  Recommended Node: {framework['recommended_node']}")

        audit_data = run_npm_audit(theme_dir)
        if not audit_data:
            continue

        audit_summary = summarize_audit(audit_data)
        counts = audit_summary["counts"]
        print(f"  Vulnerabilities: {counts.get('critical', 0)} critical / "
              f"{counts.get('high', 0)} high / "
              f"{counts.get('moderate', 0)} moderate / "
              f"{counts.get('low', 0)} low")

        report = analyze_theme(theme_name, framework, audit_summary, composer_json)
        if report:
            print(f"\n--- {theme_name} ---")
            print(report)

    print("\n" + "=" * 60)
    print("Analysis complete.")


if __name__ == "__main__":
    main()
