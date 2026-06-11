"""
wp-vitals: Audits installed WordPress plugins for a given site.
Checks for outdated versions, major version jumps, inactive plugins,
and auto-update status using WP-CLI and Claude AI.

Automatically resolves Local by Flywheel's MySQL socket environment
so WP-CLI can connect without needing to open Local's shell first.

Can be run standalone or imported by report.py for unified site reporting.

Usage:
    python audit_plugins.py --site evanghenry
    python audit_plugins.py --path /full/path/to/wordpress
"""

import os
import re
import json
import argparse
import subprocess
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
LOCAL_SITES_PATH = os.getenv("LOCAL_SITES_PATH")

LOCAL_SITES_JSON = os.path.expanduser(
    "~/Library/Application Support/Local/sites.json"
)
LOCAL_SSH_ENTRY = os.path.expanduser(
    "~/Library/Application Support/Local/ssh-entry"
)


def parse_args() -> argparse.Namespace:
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(description="wp-vitals - Audit WordPress plugins")
    parser.add_argument("--site", type=str, default=None,
                        help="Site folder name under LOCAL_SITES_PATH (e.g. --site evanghenry)")
    parser.add_argument("--path", type=str, default=None,
                        help="Full path to WordPress root. Overrides --site.")
    return parser.parse_args()


def get_local_env(site: str) -> dict:
    """
    Look up Local by Flywheel's environment variables for a given site.

    Reads sites.json to find the site ID, then parses the site's ssh-entry
    shell script to extract MYSQL_HOME and PHPRC. These are required for
    WP-CLI to connect to Local's socket-based MySQL without opening Local's shell.

    :param site: Site folder name under LOCAL_SITES_PATH.
    :return: Dict of environment variables to inject into subprocess, or empty dict on failure.
    """
    try:
        with open(LOCAL_SITES_JSON, 'r') as f:
            sites = json.load(f)
    except Exception:
        return {}

    # Find the site ID by matching the folder name in the path
    site_id = None
    for sid, data in sites.items():
        site_path = data.get("path", "")
        if os.path.basename(site_path).lower() == site.lower():
            site_id = sid
            break

    if not site_id:
        return {}

    # Parse the ssh-entry shell script for environment variables
    ssh_script = os.path.join(LOCAL_SSH_ENTRY, f"{site_id}.sh")
    if not os.path.exists(ssh_script):
        return {}

    env_vars = {}
    try:
        with open(ssh_script, 'r') as f:
            content = f.read()

        # Extract export KEY="VALUE" lines
        for match in re.finditer(r'export\s+(\w+)="([^"]+)"', content):
            env_vars[match.group(1)] = match.group(2)

        # Also extract PATH additions and prepend them
        path_additions = re.findall(r'export PATH="([^"]+):\$PATH"', content)
        if path_additions:
            current_path = os.environ.get("PATH", "")
            new_path = ":".join(path_additions) + ":" + current_path
            env_vars["PATH"] = new_path

    except Exception:
        return {}

    return env_vars


def get_wp_path(site: str | None, path: str | None) -> str | None:
    """
    Resolve the WordPress root path from either a site name or explicit path.

    :param site: Site folder name under LOCAL_SITES_PATH.
    :param path: Explicit full path to WordPress root.
    :return: Resolved WordPress root path or None if not found.
    """
    if path:
        return path
    if site:
        wp_path = os.path.join(LOCAL_SITES_PATH, site, "app", "public")
        if os.path.exists(wp_path):
            return wp_path
        print(f"WordPress root not found at: {wp_path}")
        return None
    return None


def get_plugin_list(wp_path: str, site: str | None = None) -> list[dict] | None:
    """
    Run WP-CLI to retrieve the full plugin list for a WordPress install.

    Automatically injects Local by Flywheel's MySQL environment variables
    so WP-CLI can connect to the site's socket without opening Local's shell.
    Skips drop-in pseudo-plugins (e.g. db.php) which have no version data.
    Strips any PHP deprecation warnings that appear before the JSON output.

    :param wp_path: Absolute path to the WordPress root directory.
    :param site: Site folder name used to look up Local environment variables.
    :return: List of plugin dicts or None on failure.
    """
    # Build environment with Local's MySQL socket variables injected
    env = {**os.environ}
    if site:
        local_env = get_local_env(site)
        env.update(local_env)

    try:
        result = subprocess.run(
            ["wp", "plugin", "list", f"--path={wp_path}", "--format=json", "--allow-root"],
            capture_output=True,
            text=True,
            env=env
        )

        # Strip anything before the JSON array starts (e.g. PHP deprecation warnings)
        output = result.stdout
        json_start = output.find("[")
        if json_start == -1:
            print(f"No JSON output from WP-CLI. stderr: {result.stderr}")
            return None

        output = output[json_start:]
        plugins = json.loads(output)

        # Filter out drop-ins and must-use plugins which have no meaningful version data
        return [p for p in plugins if p.get("status") not in ("dropin", "must-use")]

    except Exception as e:
        print(f"Failed to run WP-CLI: {e}")
        return None


def classify_plugins(plugins: list[dict]) -> dict:
    """
    Classify plugins by update status and risk level.

    Flags major version jumps (e.g. 3.x to 4.x) as higher risk than
    minor updates. Also surfaces inactive plugins and auto-update status.

    :param plugins: Raw plugin list from WP-CLI.
    :return: Dict with classified plugin groups and summary counts.
    """
    needs_update = []
    major_version_jumps = []
    inactive = []
    auto_update_off = []
    up_to_date = []

    for plugin in plugins:
        status = plugin.get("status", "")
        update = plugin.get("update", "none")
        version = plugin.get("version", "")
        update_version = plugin.get("update_version", "")
        auto_update = plugin.get("auto_update", "off")

        if status == "inactive":
            inactive.append(plugin)

        if auto_update == "off" and status == "active":
            auto_update_off.append(plugin)

        if update == "available" and update_version:
            needs_update.append(plugin)

            try:
                current_major = int(version.split(".")[0])
                update_major = int(update_version.split(".")[0])
                if update_major > current_major:
                    major_version_jumps.append(plugin)
            except (ValueError, IndexError):
                pass
        else:
            if status != "inactive":
                up_to_date.append(plugin)

    return {
        "needs_update": needs_update,
        "major_version_jumps": major_version_jumps,
        "inactive": inactive,
        "auto_update_off": auto_update_off,
        "up_to_date": up_to_date,
        "total": len(plugins)
    }


def analyze_plugins(site_name: str, plugins: list[dict], classification: dict) -> str | None:
    """
    Send plugin audit data to Claude for prioritized update recommendations.

    :param site_name: Display name of the site being audited.
    :param plugins: Full plugin list from WP-CLI.
    :param classification: Classified plugin groups from classify_plugins().
    :return: Formatted analysis string from Claude, or None if no plugins found.
    """
    if not plugins:
        return None

    plugins_text = json.dumps(plugins, indent=2)
    major_jumps = [p["name"] for p in classification["major_version_jumps"]]
    inactive_names = [p["name"] for p in classification["inactive"]]
    auto_off = [p["name"] for p in classification["auto_update_off"]]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""You are a WordPress developer auditing plugins for site: {site_name}

PLUGIN DATA:
{plugins_text}

FLAGGED ITEMS:
- Major version jumps (higher risk): {major_jumps if major_jumps else 'None'}
- Inactive plugins: {inactive_names if inactive_names else 'None'}
- Auto-update OFF (active plugins): {auto_off if auto_off else 'None'}

Use these exact health criteria:
- CRITICAL: Known vulnerable plugin version, or a major version jump on a business-critical plugin (ACF, WooCommerce, Gravity Forms)
- WARNING: Updates available, inactive plugins present, or auto-update disabled on key plugins
- HEALTHY: All plugins current, no inactive plugins, auto-updates configured

Provide:
1. Overall health: CRITICAL / WARNING / HEALTHY
2. Top 3 most urgent plugins to address and why
3. Any major version jumps that need careful testing before updating
4. Inactive plugins that should be removed
5. One recommended action to take right now

Keep it concise. Max 15 lines."""
            }
        ]
    )

    return message.content[0].text


def run_plugin_audit(site: str | None = None, path: str | None = None) -> dict | None:
    """
    Run plugin audit for a single site and return structured results.

    Designed to be called by report.py for unified site reporting.
    Returns None if WP-CLI fails or no plugins are found.

    :param site: Site folder name under LOCAL_SITES_PATH.
    :param path: Explicit full path to WordPress root. Overrides site.
    :return: Dict with site_name, classification, and report, or None on failure.
    """
    wp_path = get_wp_path(site, path)
    if not wp_path:
        return None

    site_name = site or os.path.basename(wp_path)
    plugins = get_plugin_list(wp_path, site=site)

    if not plugins:
        return None

    classification = classify_plugins(plugins)
    report = analyze_plugins(site_name, plugins, classification)

    return {
        "site_name": site_name,
        "classification": classification,
        "report": report
    }


def main() -> None:
    """Main entry point. Orchestrates plugin discovery, classification, and analysis."""
    args = parse_args()
    wp_path = get_wp_path(args.site, args.path)

    if not wp_path:
        print("Provide --site or --path to a WordPress root directory.")
        return

    site_name = args.site or os.path.basename(wp_path)

    print(f"Auditing plugins for: {site_name}...")
    plugins = get_plugin_list(wp_path, site=args.site)

    if plugins is None:
        print("Could not retrieve plugin list. Is the site running and WP-CLI available?")
        return

    if not plugins:
        print("No plugins found.")
        return

    classification = classify_plugins(plugins)

    print(f"Found {classification['total']} plugin(s) -- "
          f"{len(classification['needs_update'])} need updates, "
          f"{len(classification['inactive'])} inactive\n")

    print("=" * 60)
    print("WP VITALS - PLUGIN AUDIT REPORT")
    print("=" * 60)

    report = analyze_plugins(site_name, plugins, classification)

    if report:
        print(f"\n--- {site_name} ---")
        print(report)

    print("\n" + "=" * 60)
    print("Audit complete.")


if __name__ == "__main__":
    main()
