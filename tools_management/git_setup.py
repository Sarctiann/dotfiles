"""Git config setup step — prompts for git identity and generates ~/.gitconfig."""

import os
import subprocess
import sys
from pathlib import Path

import core

CREDENTIALS_PATH = Path.home() / ".config" / "zsh" / ".credentials"
GIT_VARS = ["GIT_NAME", "GIT_EMAIL", "COMPANY_GIT_NAME", "COMPANY_GIT_EMAIL", "COMPANY_DIR"]
SYNC_SCRIPT = str(core.BIN_DIR / "sync_git_config.py")


def _load_from_credentials(var: str) -> str | None:
    """Read a single var from ~/.config/zsh/.credentials if present."""
    if not CREDENTIALS_PATH.is_file():
        return None
    for line in CREDENTIALS_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("export ") and f"{var}=" in line:
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            if val:
                return val
    return None


def _get_env_or_creds(var: str) -> str | None:
    val = os.environ.get(var, "").strip()
    if val:
        return val
    return _load_from_credentials(var)


def _source_credentials() -> None:
    """Load credentials into the current process environment."""
    if not CREDENTIALS_PATH.is_file():
        return
    for line in CREDENTIALS_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            rest = line[7:]
            if "=" in rest:
                k, v = rest.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v and k not in os.environ:
                    os.environ[k] = v


def _prompt_var(var: str, label: str) -> str:
    current = _get_env_or_creds(var) or ""
    prompt_text = f"  {label}"
    if current:
        val = input(f"{prompt_text} [{current}]: ").strip()
        return val if val else current
    return input(f"{prompt_text}: ").strip()


def _save_to_credentials(vars: dict[str, str]) -> None:
    """Append or update git vars in ~/.config/zsh/.credentials."""
    if not vars:
        return
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = CREDENTIALS_PATH.read_text().splitlines(keepends=True) if CREDENTIALS_PATH.is_file() else []
    written = set()
    result_lines: list[str] = []
    section_header = "# ─── Git ────────────────────────────────────────────────────────\n"
    has_section = False
    for line in existing:
        for var in vars:
            if line.strip().startswith(f"export {var}="):
                line = f'export {var}="{vars[var]}"\n'
                written.add(var)
                break
        # remove old section header if we're replacing it
        if line == section_header:
            has_section = True
            continue
        # skip old git vars that were already written
        stripped = line.strip()
        if stripped.startswith("export ") and "=" in stripped:
            maybe_var = stripped[7:].split("=", 1)[0]
            if maybe_var in vars:
                continue
        result_lines.append(line)
    # append remaining vars that weren't in the file
    new_vars = {k: v for k, v in vars.items() if k not in written}
    if new_vars:
        result_lines.append("\n")
        result_lines.append(section_header)
        for k, v in new_vars.items():
            result_lines.append(f'export {k}="{v}"\n')
    CREDENTIALS_PATH.write_text("".join(result_lines))
    # Update process environment so sync script picks up latest values
    for k, v in vars.items():
        if v:
            os.environ[k] = v
    print(f"  ✓ Saved to {CREDENTIALS_PATH}")


def _run_sync() -> None:
    if not os.path.isfile(SYNC_SCRIPT):
        print(f"  ⚠  sync_git_config.py not found at {SYNC_SCRIPT}")
        return
    _source_credentials()
    subprocess.run([sys.executable, SYNC_SCRIPT], check=True)


def git_setup(config: dict, mode: str = "install") -> None:
    _ = config
    if mode == "check":
        print("🔧 Git setup:")
        for var in GIT_VARS:
            val = _get_env_or_creds(var) or "(not set)"
            print(f"     {var} = {val}")
        return

    if mode == "install":
        print("🔧 Git setup...")
        interactive = core.INTERACTIVE or os.environ.get("GIT_SETUP_INTERACTIVE") == "1" or sys.stdin.isatty()

        # Try loading from credentials first
        _source_credentials()

        if interactive:
            vals = {}
            print("  Enter your git identity (leave blank to keep current):")
            vals["GIT_NAME"] = _prompt_var("GIT_NAME", "  Git name (GIT_NAME)")
            vals["GIT_EMAIL"] = _prompt_var("GIT_EMAIL", "  Git email (GIT_EMAIL)")
            print("  Company git identity (for conditional includes):")
            vals["COMPANY_GIT_NAME"] = _prompt_var("COMPANY_GIT_NAME", "  Company name (COMPANY_GIT_NAME)")
            vals["COMPANY_GIT_EMAIL"] = _prompt_var("COMPANY_GIT_EMAIL", "  Company email (COMPANY_GIT_EMAIL)")
            vals["COMPANY_DIR"] = _prompt_var("COMPANY_DIR", "  Company dir (COMPANY_DIR)")
            _save_to_credentials(vals)

        all_set = all(_get_env_or_creds(v) for v in GIT_VARS[:2])
        if not all_set:
            print("  ⚠  GIT_NAME/GIT_EMAIL not set — skipping git config generation")
            return

        _run_sync()

    elif mode == "uninstall":
        gitconfig = Path.home() / ".gitconfig"
        if gitconfig.is_file() and not gitconfig.is_symlink():
            gitconfig.unlink()
            print("  ✓ Removed ~/.gitconfig")
