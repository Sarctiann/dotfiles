# ─── Locale & basics ───────────────────────────────────────────
export CLICOLOR=1
export LC_ALL=en_US.UTF-8
export VIRTUAL_ENV_DISABLE_PROMPT=1

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
zstyle ':vcs_info:*' formats '%F{yellow}( <%f%F{green}%r%f%F{yellow}>%f %b %u%c%F{yellow})%f'

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
alias auggie-work="auggie --augment-cache-dir ~/Documents/HST/.augment_work_profile"
alias Claude="claude --dangerously-skip-permissions"
alias oc="opencode"
alias devlights-info="bat ~/Documents/MarkdownNotes/MISC/DEVLIGHTS_FISCAL.md"
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
source ~/.zsh/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
source ~/.zsh/zsh-autosuggestions/zsh-autosuggestions.zsh

# ─── Editor ────────────────────────────────────────────────────
export EDITOR=nvim
export VISUAL=nvim
export DOCS_DIR="$HOME/Documents"

# ─── Language runtimes ─────────────────────────────────────────
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" --no-use
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

if [ -f ".nvmrc" ]; then
  nvm use > /dev/null
else
  nvm use default > /dev/null
fi

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
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
export PATH="$HOME/.cargo/bin:$PATH"
export PATH="$HOME/.opencode/bin:$PATH"

# ─── API keys & credentials ────────────────────────────────────
export GITHUB_PERSONAL_ACCESS_TOKEN=$(gh auth token)

set -a
source "$HOME/.config/opencode/.credentials"
source "$HOME/.config/.jira/.credentials"
source "$HOME/.zsh/.credentials"
set +a
