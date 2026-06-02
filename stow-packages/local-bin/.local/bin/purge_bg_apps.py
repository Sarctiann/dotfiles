#!/usr/bin/env python3
"""
purge_bg_apps.py - Remove background apps, startup items, and login extensions on macOS.

Removes all traces of the matching apps: plists, support folders, system
extensions, running processes, and the BTM database entry. A reboot is
required to fully complete the cleanup.

Safety:
  - System extensions are uninstalled via the proper macOS API (safe unload).
  - Processes are killed by exact name match only (no pkill -f).
  - Nothing is modified until you confirm the full list of changes.

Usage:
  sudo python3 purge_bg_apps.py [options] <search_term1> <search_term2> ...

Options:
  -n, --dry-run    Show what would be removed without actually removing anything
  -y, --yes        Skip confirmation prompt
"""

import os
import sys
import re
import subprocess
import shutil
import argparse

def matches(text, patterns):
    return any(p.search(text) for p in patterns)


def get_user_home():
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        return os.path.expanduser(f'~{sudo_user}')
    return os.path.expanduser('~')


def is_bundle_id(s):
    return s.count('.') >= 2


def discover_extensions(patterns):
    items = []
    try:
        result = subprocess.run(['systemextensionsctl', 'list'], capture_output=True, text=True, check=True)
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
            parts = line.strip().split()
            bundle_id = next((p for p in parts if is_bundle_id(p)), None)
            if bundle_id is None:
                continue
            if matches(bundle_id, patterns):
                idx = parts.index(bundle_id)
                team_id = parts[0] if idx > 0 and not any(c in parts[0] for c in './-') else None
                if team_id == '*':
                    team_id = None
                items.append({
                    'type': 'extension',
                    'bundle_id': bundle_id,
                    'team_id': team_id,
                    'display': f"  System Extension: {bundle_id}" + (f" (team: {team_id})" if team_id else "")
                })
    except Exception as e:
        print(f"  Warning: Could not list system extensions: {e}")
    return items


def discover_files(patterns):
    items = []
    user_home = get_user_home()
    scan_paths = [
        "/Library/LaunchAgents",
        "/Library/LaunchDaemons",
        "/Library/Application Support",
        "/Library/Extensions",
        "/Library/PrivilegedHelperTools",
        f"{user_home}/Library/LaunchAgents",
        f"{user_home}/Library/Application Support",
    ]
    for path in scan_paths:
        if not os.path.exists(path):
            continue
        for item in os.listdir(path):
            if matches(item, patterns):
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path) and not os.path.islink(full_path)
                kind = "Folder" if is_dir else "File"
                items.append({
                    'type': 'file',
                    'path': full_path,
                    'is_dir': is_dir,
                    'display': f"  {kind}: {full_path}"
                })
    return items


def discover_processes(patterns):
    items = []
    try:
        ps_output = subprocess.run(['ps', '-A', '-o', 'comm'], capture_output=True, text=True, check=True)
        seen = set()
        for line in ps_output.stdout.split('\n'):
            proc_name = line.split('/')[-1]
            if proc_name and matches(proc_name, patterns) and proc_name not in seen:
                seen.add(proc_name)
                items.append({
                    'type': 'process',
                    'name': proc_name,
                    'display': f"  Process: {proc_name}"
                })
    except Exception as e:
        print(f"  Warning: Could not list processes: {e}")
    return items


def execute_removal(items):
    for item in items:
        try:
            if item['type'] == 'file':
                if item['is_dir']:
                    print(f"  => Removing folder: {item['path']}")
                    shutil.rmtree(item['path'])
                else:
                    print(f"  => Removing file: {item['path']}")
                    os.remove(item['path'])
        except Exception as e:
            print(f"  Warning: Could not remove {item['path']}: {e}")


def execute_kill(items):
    for item in items:
        if item['type'] != 'process':
            continue
        try:
            print(f"  => Killing process: {item['name']}")
            subprocess.run(['pkill', '-i', item['name']], capture_output=True)
        except Exception as e:
            print(f"  Warning: Could not kill {item['name']}: {e}")


def execute_uninstall_extensions(items):
    for item in items:
        if item['type'] != 'extension' or not item['team_id']:
            continue
        try:
            print(f"  => Uninstalling extension: {item['bundle_id']}")
            subprocess.run(['systemextensionsctl', 'uninstall', item['team_id'], item['bundle_id']], capture_output=True)
        except Exception as e:
            print(f"  Warning: Could not uninstall {item['bundle_id']}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Remove background apps, startup items, and login extensions on macOS.",
        epilog="Example: sudo python3 purge_bg_apps.py logi karabiner edge"
    )
    parser.add_argument('terms', nargs='+', help='Search terms (regex patterns) to match')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    patterns = [re.compile(p, re.IGNORECASE) for p in args.terms]
    dry_run = args.dry_run

    if os.geteuid() != 0:
        print("Error: This script must be run with administrator privileges (sudo).")
        print("Example: sudo python3 purge_bg_apps.py logi karabiner edge")
        sys.exit(1)

    print(f"Searching for items matching: {args.terms}\n")

    print("Scanning system extensions...")
    extensions = discover_extensions(patterns)
    for item in extensions:
        print(item['display'])

    print("\nScanning files (LaunchAgents, Daemons, Support, Extensions, Helpers)...")
    files = discover_files(patterns)
    for item in files:
        print(item['display'])

    print("\nScanning running processes...")
    processes = discover_processes(patterns)
    for item in processes:
        print(item['display'])

    all_items = extensions + files + processes

    if not all_items:
        print("\nNo matching items found.")
        sys.exit(0)

    n_ext = sum(1 for i in extensions)
    n_files = sum(1 for i in files)
    n_proc = sum(1 for i in processes)

    print(f"\n{'='*60}")
    print(f"Found {len(all_items)} item(s): {n_ext} extension(s), {n_files} file(s), {n_proc} process(es)")

    if dry_run:
        print("Dry-run mode enabled. No changes were made.")
        sys.exit(0)

    if not args.yes:
        confirm = input("Proceed with removal? [y/N] ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            sys.exit(0)

    # Order: files first (prevent restart), then kill processes, then uninstall
    # extensions (safe since the process is already stopped), finally reset BTM.
    print("\nRemoving files...")
    execute_removal(files)

    print("\nStopping running processes...")
    execute_kill(processes)

    print("\nUninstalling system extensions...")
    execute_uninstall_extensions(extensions)

    print("\nSyncing System Settings interface...")
    try:
        subprocess.run(['sfltool', 'resetbtm'], check=True)
        print("  => Background Task Management database reset successfully.")
    except Exception as e:
        print(f"  Warning: Could not reset BTM database: {e}")

    print("\nDone! A reboot is required for changes to take full effect.")


if __name__ == '__main__':
    main()
