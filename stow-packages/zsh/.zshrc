# ─── Locale & basics ───────────────────────────────────────────
export CLICOLOR=1
export LC_ALL=en_US.UTF-8
export VIRTUAL_ENV_DISABLE_PROMPT=1

# Source .zprofile if not a login shell (tmux on Linux/WSL)
# macOS Terminal.app starts zsh as login shell; Linux generally doesn't.
if [[ ! -o login ]] && [[ -f "$HOME/.zprofile" ]]; then
  source "$HOME/.zprofile"
fi

# ─── Prompt setup ──────────────────────────────────────────────
autoload -Uz promptinit
promptinit
setopt histignorealldups sharehistory PROMPT_SUBST

autoload -Uz vcs_info
precmd_vcs_info() { vcs_info }
precmd_functions+=( precmd_vcs_info )

zstyle ':vcs_info:*' check-for-changes true
zstyle ':vcs_info:*' unstagedstr '%F{red} %f'
zstyle ':vcs_info:*' stagedstr '%F{green} %f'
zstyle ':vcs_info:*' formats '%F{yellow}( <%f%F{green}%r%f%F{yellow}>%f %b%m %u%c%F{yellow})%f'

zstyle ':vcs_info:git+set-message:*:*' hooks git-remote

+vi-git-remote() {
    local git_root cache_file
    git_root=$(git rev-parse --show-toplevel 2>/dev/null) || return
    cache_file="$_GIT_PROMPT_CACHE/${git_root//\//_}"

    local ahead=0 behind=0 timestamp=0
    if [[ -f "$cache_file" ]]; then
        IFS=' ' read -r ahead behind timestamp < "$cache_file"
    fi

    zmodload zsh/datetime 2>/dev/null
    local delta_str=""
    if (( timestamp > 0 )); then
        local delta=$(( EPOCHSECONDS - timestamp ))
        if (( delta < 60 )); then
            delta_str="${delta}s"
        elif (( delta < 3600 )); then
            delta_str="$(( delta / 60 ))m"
        else
            delta_str="$(( delta / 3600 ))h"
        fi
        hook_com[misc]="%F{244}  ${delta_str}%f"
    fi

    if (( ahead > 0 || behind > 0 )); then
        local remote_info="%F{215}"
        (( ahead > 0 )) && remote_info+="↑${ahead}"
        (( behind > 0 )) && remote_info+="↓${behind}"
        remote_info+="%f"
        hook_com[branch]+=" ${remote_info}"
    fi
}

# ── Remote ahead/behind via async fetch + cache ───────────────
typeset -g _GIT_PROMPT_CACHE="${XDG_RUNTIME_DIR:-/tmp}/git-prompt-cache"

_async_git_fetch() {
    local git_root
    git_root=$(git rev-parse --show-toplevel 2>/dev/null) || return
    local cache_file="$_GIT_PROMPT_CACHE/${git_root//\//_}"
    local lock_file="$_GIT_PROMPT_CACHE/${git_root//\//_}.lock"

    mkdir -p "$_GIT_PROMPT_CACHE" 2>/dev/null

    (
        mkdir "$lock_file" 2>/dev/null || exit
        git -C "$git_root" fetch --quiet 2>/dev/null

        zmodload zsh/datetime 2>/dev/null
        local upstream ahead behind
        upstream=$(git -C "$git_root" rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null)
        if [[ -n "$upstream" ]]; then
            ahead=$(git -C "$git_root" rev-list --count @{upstream}..HEAD 2>/dev/null || echo 0)
            behind=$(git -C "$git_root" rev-list --count HEAD..@{upstream} 2>/dev/null || echo 0)
        else
            ahead=0; behind=0
        fi

        echo "$ahead $behind $EPOCHSECONDS" > "$cache_file"
        rmdir "$lock_file" 2>/dev/null
    ) &!
}

precmd_functions+=( _async_git_fetch )

function virtualenv_info () {
    [ $VIRTUAL_ENV ] && echo '('`basename $VIRTUAL_ENV`') '
    [ $PIXI_PROMPT ] && echo $PIXI_PROMPT
}

PROMPT=$'\n'
PROMPT+='%{%F{yellow}%}< %{%F{blue}%}%~%{%F{white}%} :'
PROMPT+=' ${vcs_info_msg_0_}'
PROMPT+=$'\n'
PROMPT+='%{%F{green}%}$(virtualenv_info)'
PROMPT+='%{%F{cyan}%}%n%{%F{135}%}@%{%F{cyan}%}%m%{%F{yellow}%} > %{%F{white}%}'

# ─── API keys & credentials ────────────────────────────────────
# All env vars are defined in ~/.config/zsh/.credentials (see README.md there)
set -a
[ -f "$HOME/.config/zsh/.credentials" ] && source "$HOME/.config/zsh/.credentials"
set +a

# ─── Aliases ───────────────────────────────────────────────────
alias 'cd..'='cd ..'
alias 'cd-'='cd -'
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias ll='ls -al'
alias la='ls -A'
alias l='ls -CF'
alias mg='mongo --quiet'
alias ptpy='ptpython'
alias lzv="NVIM_APPNAME=nvim nvim"
alias lzg="lazygit"
alias lzd="lazydocker"
alias lzs="lazysql"
alias π-thon="python3.14"
alias py="python3"
alias auggie-work="auggie --augment-cache-dir $COMPANY_DIR/.augment_work_profile"
alias Claude="claude --dangerously-skip-permissions"
alias oc="opencode"
alias devlights-info="bat $DOCS_DIR/MarkdownNotes/MISC/DEVLIGHTS_FISCAL.md"
alias tmux-help='bat -l markdown ~/.config/tmux/help.txt'

# ─── Key bindings ──────────────────────────────────────────────
bindkey '^[[1;5C' emacs-forward-word
bindkey '^[[1;5D' emacs-backward-word
bindkey -e

# ─── History ───────────────────────────────────────────────────
HISTSIZE=1000
SAVEHIST=1000
HISTFILE=~/.zsh_history

# ─── Completion ────────────────────────────────────────────────
fpath+=~/.zfunc
autoload -Uz compinit
compinit

zstyle ':completion:*' auto-description 'specify: %d'
zstyle ':completion:*' completer _expand _complete _correct _approximate
zstyle ':completion:*' format 'Completing %d'
zstyle ':completion:*' group-name ''
zstyle ':completion:*' menu select=2
zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}
zstyle ':completion:*' list-colors ''
zstyle ':completion:*' list-prompt %SAt %p: Hit TAB for more, or the character to insert%s
zstyle ':completion:*' matcher-list '' 'm:{a-z}={A-Z}' 'm:{a-zA-Z}={A-Za-z}' 'r:|[._-]=* r:|=* l:|=*'
zstyle ':completion:*' menu select=long
zstyle ':completion:*' select-prompt %SScrolling active: current selection at %p%s
zstyle ':completion:*' use-compctl false
zstyle ':completion:*' verbose true
zstyle ':completion:*:*:kill:*:processes' list-colors '=(#b) #([0-9]#)*=0=01;31'
zstyle ':completion:*:kill:*' command 'ps -u $USER -o pid,%cpu,tty,cputime,cmd'

# ─── Plugins ───────────────────────────────────────────────────
ZSH_PLUGIN_DIR="$HOME/.local/share/zsh-plugins"
source "$ZSH_PLUGIN_DIR/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
source "$ZSH_PLUGIN_DIR/zsh-autosuggestions/zsh-autosuggestions.zsh"

# ─── Editor ────────────────────────────────────────────────────
export EDITOR=nvim
export VISUAL=nvim

# ─── PATH ──────────────────────────────────────────────────────
export PATH=/usr/local/opt/openssl@1.1/bin:$PATH
export PATH=/opt/homebrew/bin:$PATH
export PATH=/usr/local/bin:$PATH

export MODULAR_HOME="$HOME/.modular"
export PATH="$MODULAR_HOME/pkg/packages.modular.com_mojo/bin:$PATH"
export PATH="$PATH:$MODULAR_HOME/bin"

export PATH="$HOME/.zigup:$HOME/.zig:$PATH"
export PATH="/Library/TeX/texbin:$PATH"
export PATH="$HOME/.pixi/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.cargo/bin:$PATH"
export PATH="$HOME/.opencode/bin:$PATH"

# ─── Language runtimes ─────────────────────────────────────────
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" --no-use
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

autoload -Uz add-zsh-hook

load-nvmrc() {
  local nvmrc_path
  nvmrc_path="$(nvm_find_nvmrc)"

  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version
    nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")

    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
      nvm use
    elif [ "$nvmrc_node_version" != "$(nvm version)" ]; then
      nvm use
      clear
    fi
  elif [ -n "$(PWD=$OLDPWD nvm_find_nvmrc)" ] && [ "$(nvm version)" != "$(nvm version default)" ]; then
    nvm use default
  fi
}

add-zsh-hook chpwd load-nvmrc
load-nvmrc

export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home

eval "$(luarocks path --bin)"

# ─── SDKs ──────────────────────────────────────────────────────
export ANDROID_HOME=$HOME/Library/Android/sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/tools
export PATH=$PATH:$ANDROID_HOME/tools/bin
export PATH=$PATH:$ANDROID_HOME/emulator

export VULKAN_SDK=/path/to/vulkan-sdk
export PATH=$VULKAN_SDK/bin:$PATH
export DYLD_LIBRARY_PATH=$VULKAN_SDK/lib:$DYLD_LIBRARY_PATH
export VK_ICD_FILENAMES=$VULKAN_SDK/etc/vulkan/icd.d/MoltenVK_icd.json
export VK_LAYER_PATH=$VULKAN_SDK/etc/vulkan/explicit_layer.d

# Load WSL Windows path (generated by dotfiles post_install)
[[ -f "$HOME/.config/zsh/.windows_path.zsh" ]] && source "$HOME/.config/zsh/.windows_path.zsh"

# ─── SSH agent (keychain) ──────────────────────────────────────
# Manages ssh-agent across terminals; prompts for passphrase once per boot.
# Uses mkdir as atomic lock so tmux session-resurrect doesn't prompt in all windows.
if command -v keychain &>/dev/null; then
  eval $(keychain --eval --quiet -Q --timeout 480)
  if ! ssh-add -l &>/dev/null; then
    if mkdir /tmp/ssh-add-lock 2>/dev/null; then
      ssh-add ~/.ssh/id_ed25519 2>/dev/null
      rmdir /tmp/ssh-add-lock 2>/dev/null
    fi
  fi
fi


# bun completions
[ -s "/home/sarctiann/.bun/_bun" ] && source "/home/sarctiann/.bun/_bun"
