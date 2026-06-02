from core import which


def verify(config: dict, mode: str = "install") -> None:
    _ = mode  # kept for API compatibility with step dispatcher
    v = config.get("verify", {})
    essentials = v.get("essential", [])
    optional = v.get("optional", [])

    print("🔍 Verifying installation...")

    missing = [cmd for cmd in essentials if not which(cmd)]
    if missing:
        print(f"⚠️  Missing essential commands: {' '.join(missing)}")
    else:
        print("✅ All essential commands are installed")

    for cmd in optional:
        if not which(cmd):
            print(f"   ℹ️  Optional: {cmd} not found")

    print()
