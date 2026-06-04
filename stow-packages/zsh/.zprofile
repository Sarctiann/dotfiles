export PATH=/usr/local/opt/openssl@1.1/bin:$PATH
export PATH=/opt/homebrew/bin:$PATH
export PATH=/usr/local/bin:$PATH

autoload -Uz compinit
compinit

# ~/.local/bin added for user-level tools (uv, pipx, etc.)
export PATH="$PATH:/Users/sebastianrodriguezcapurro/.local/bin"

# Added by `rbenv init` on Mon Dec  1 18:42:01 -03 2025
eval "$(rbenv init - --no-rehash zsh)"

##
# Your previous /Users/sebastianrodriguezcapurro/.zprofile file was backed up as /Users/sebastianrodriguezcapurro/.zprofile.macports-saved_2026-03-12_at_13:17:08
##

# MacPorts Installer addition on 2026-03-12_at_13:17:08: adding an appropriate PATH variable for use with MacPorts.
export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
# Finished adapting your PATH environment variable for use with MacPorts.


#compdef opencode
###-begin-opencode-completions-###
#
# yargs command completion script
#
# Installation: opencode completion >> ~/.zshrc
#    or opencode completion >> ~/.zprofile on OSX.
#
_opencode_yargs_completions()
{
  local reply
  local si=$IFS
  IFS=$'
' reply=($(COMP_CWORD="$((CURRENT-1))" COMP_LINE="$BUFFER" COMP_POINT="$CURSOR" opencode --get-yargs-completions "${words[@]}"))
  IFS=$si
  if [[ ${#reply} -gt 0 ]]; then
    _describe 'values' reply
  else
    _default
  fi
}
if [[ "'${zsh_eval_context[-1]}" == "loadautofunc" ]]; then
  _opencode_yargs_completions "$@"
else
  compdef _opencode_yargs_completions opencode
fi
###-end-opencode-completions-###

