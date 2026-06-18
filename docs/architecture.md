# Architecture

## Install Flow

```mermaid
flowchart TD
    install_sh["install.sh"] --> setup["1_setup.sh (bootstrap)"]
    setup -->|"macOS: Xcode + brew + python3"| mgmt_install
    setup -->|"Linux: apt/pacman/dnf python3"| mgmt_install

    mgmt_install["2_management.py install"] --> load_config["Load config.json"]
    load_config --> detect_changes{"Config changed<br>since last install?"}
    detect_changes -->|"no (re-install)"| skip_unchanged["Skip steps with unchanged config"]
    detect_changes -->|"yes / --just"| run_all["Run all required steps"]

    skip_unchanged --> system_pkgs
    run_all --> system_pkgs

    subgraph pipeline ["Pipeline Steps"]
        system_pkgs["① System packages<br>brew / apt / pacman / dnf"]
        cli_tools["② CLI tools<br>GitHub releases"]
        fonts["③ Fonts<br>Nerd Fonts download"]
        stow["④ Stow symlinks<br>stow -R"]
        runtimes["⑤ Runtimes<br>nvm / bun / rust / opencode"]
        npm["⑥ NPM packages<br>npm install -g"]
        post_install["⑦ Post-install<br>TPM / zsh plugins / Windows Terminal"]
        verify["⑧ Verification<br>essential + optional checks"]
    end

    system_pkgs --> cli_tools --> fonts --> stow --> runtimes --> npm --> post_install --> verify

    verify --> save_manifest["Save manifest + config snapshot"]
    save_manifest --> done["✅ Done"]
```

## Uninstall Flow

```mermaid
flowchart TD
    uninstall_sh["uninstall.sh"] --> uninst_setup["1_uninstall.sh (bootstrap)"]
    uninst_setup --> mgmt_uninstall["2_management.py uninstall"]
    mgmt_uninstall --> load_manifest["Load manifest.json"]
    load_manifest --> confirm{"--force?"}
    confirm -->|"no"| prompt["Confirmation prompt"]
    confirm -->|"yes"| reverse
    prompt --> reverse

    subgraph reverse_pipeline ["Pipeline Steps (reverse order)"]
        verify_u["⑧ Verification"]
        post_undo["⑦ Post-install undo<br>TPM / zsh plugins / Windows Terminal"]
        npm_undo["⑥ NPM packages uninstall"]
        runtime_undo["⑤ Runtimes uninstall"]
        stow_undo["④ Stow symlinks undo<br>+ backup restore"]
        fonts_undo["③ Fonts remove"]
        cli_undo["② CLI tools remove"]
    end

    reverse --> verify_u --> post_undo --> npm_undo --> runtime_undo --> stow_undo --> fonts_undo --> cli_undo

    cli_undo --> delete_manifest{"--just mode?"}
    delete_manifest -->|"no"| delete["Delete manifest"]
    delete_manifest -->|"yes"| keep["Keep manifest<br>(partial uninstall)"]
    delete --> done_u["✅ Done"]
    keep --> done_u
```

## --just Mode

```mermaid
flowchart LR
    just["--just PKG"] --> resolve["Resolve package deps<br>from config step_deps"]
    resolve --> plan["Build stow plan<br>PKG + transitive deps"]
    plan --> skip["should_skip_step()<br>skips steps not in plan"]
    skip --> run["Run only:<br>base steps + needed steps"]
```

## Config Snapshot (Change Detection)

```mermaid
flowchart LR
    install["Install runs"] --> hash["SHA-256 hash per step config"]
    hash --> store["Store in manifest<br>config_snapshot"]
    reinstall["Re-install runs"] --> compare["Compare current hashes vs stored"]
    compare --> match["Match → skip step"]
    compare --> mismatch["Mismatch → run step"]
```

## Module Dependencies

```mermaid
flowchart TD
    mgmt["2_management.py"]
    cfg["config.py"]
    core["core.py"]
    manifest["manifest.py"]
    cli["cli_tools.py"]
    gh["gh_releases.py"]
    syspkg["system_packages.py"]
    fonts["fonts.py"]
    stow["stow.py"]
    runtimes["runtimes.py"]
    npm["npm_packages.py"]
    post["post_install.py"]
    verify["verify.py"]

    mgmt --> cfg
    mgmt --> core
    mgmt --> manifest
    mgmt --> cli
    mgmt --> syspkg
    mgmt --> fonts
    mgmt --> stow
    mgmt --> runtimes
    mgmt --> npm
    mgmt --> post
    mgmt --> verify
    cli --> gh
    cli --> core
    cli --> manifest
    stow --> core
    stow --> manifest
    fonts --> core
    fonts --> manifest
    runtimes --> core
    runtimes --> manifest
    post --> core
    post --> manifest
    post --> stow
    manifest --> core
```

## File Layout

```
dotfiles/
├── install.sh                          # User entry point
├── uninstall.sh                        # Uninstall entry point
├── config.json                         # All pipeline config
├── dotfiles-manifest.json              # (generated) Last install snapshot
├── stow-packages/                      # Source for stow symlinks
│   ├── lazyvim/
│   ├── zsh/
│   ├── tmux/
│   ├── ghostty/
│   └── ...
├── tools_management/
│   ├── 1_setup.sh                      # Bootstrap (bash)
│   ├── 1_uninstall.sh                  # Uninstall bootstrap (bash)
│   ├── 2_management.py                 # Pipeline orchestrator
│   ├── config.py                       # Config loader
│   ├── core.py                         # Shared utilities
│   ├── manifest.py                     # Manifest CRUD + change detection
│   ├── cli_tools.py                    # CLI tool install orchestration
│   ├── gh_releases.py                  # GitHub release downloader
│   ├── system_packages.py              # OS package manager interface
│   ├── fonts.py                        # Nerd Font installer
│   ├── stow.py                         # Stow symlink management
│   ├── runtimes.py                     # Runtime/version manager installer
│   ├── npm_packages.py                 # Global npm package installer
│   ├── post_install.py                 # Post-install hooks
│   └── verify.py                       # Install verification
└── testing/
    ├── test_pipeline.py                # Test orchestrator (linux/wsl via Docker, mac via --check)
    ├── docker-compose.yml              # Docker compose services
    ├── test_containers/
    │   ├── test_pipeline.sh            # Shared pipeline test script
    │   ├── Dockerfile.linux            # Linux container
    │   └── Dockerfile.wsl              # WSL container (fake /mnt/c)
    └── logs/                           # (generated) Test output logs
```
