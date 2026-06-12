#!/usr/bin/env python3
"""
sync_git_config.py — Generate ~/.gitconfig from environment variables.

Reads: GIT_NAME, GIT_EMAIL, COMPANY_GIT_NAME, COMPANY_GIT_EMAIL, COMPANY_DIR
Generates ~/.gitconfig with hardcoded values (env vars resolved at generation time).

Usage:
  export GIT_NAME="..." GIT_EMAIL="..." COMPANY_DIR="..."
  sync_git_config.py            # generate from env vars
  sync_git_config.py --check    # show what vars are set without writing
"""

import argparse
import os
import sys
from pathlib import Path


ALIASES = """
[alias]
  cm = commit -m
  ca = commit --amend
  c = checkout
  po = push origin
  pu = pull origin --no-rebase
  m = merge
  aa = add --all
  puo = push --set-upstream origin
"""

SETTINGS = """
[core]
  editor = nano

[init]
  defaultBranch = main

[pull]
  ff = only
"""


def require(var: str) -> str | None:
    val = os.environ.get(var, "").strip()
    if not val:
        print(f"⚠  {var} is not set — skipping")
        return None
    return val


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ~/.gitconfig from env vars")
    parser.add_argument(
        "--check", action="store_true", help="show vars and exit without writing"
    )
    args = parser.parse_args()

    git_name = require("GIT_NAME")
    git_email = require("GIT_EMAIL")
    company_name = require("COMPANY_GIT_NAME")
    company_email = require("COMPANY_GIT_EMAIL")
    company_dir = require("COMPANY_DIR")

    if company_dir:
        company_dir = os.path.expanduser(company_dir).rstrip("/")

    if args.check:
        print(f"  GIT_NAME          = {git_name or '(not set)'}")
        print(f"  GIT_EMAIL         = {git_email or '(not set)'}")
        print(f"  COMPANY_GIT_NAME  = {company_name or '(not set)'}")
        print(f"  COMPANY_GIT_EMAIL = {company_email or '(not set)'}")
        print(f"  COMPANY_DIR       = {company_dir or '(not set)'}")
        return

    if not git_name or not git_email:
        print("❌ GIT_NAME and GIT_EMAIL are required")
        sys.exit(1)

    parts: list[str] = []

    parts.append("[user]")
    parts.append(f"  name = {git_name}")
    parts.append(f"  email = {git_email}")
    parts.append("")

    if company_name and company_email and company_dir:
        work_path = Path.home() / ".gitconfig-work"
        work_content = f"[user]\n  name = {company_name}\n  email = {company_email}\n"
        work_path.write_text(work_content)
        print(f"✓ Generated {work_path}")

        parts.append(f'[includeIf "gitdir:{company_dir}/"]')
        parts.append("  path = ~/.gitconfig-work")
        parts.append("")

    parts.append(ALIASES.strip())
    parts.append(SETTINGS.strip())
    parts.append("")

    gitconfig = Path.home() / ".gitconfig"
    gitconfig.write_text("\n".join(parts))
    print(f"✓ Generated {gitconfig}")


if __name__ == "__main__":
    main()
