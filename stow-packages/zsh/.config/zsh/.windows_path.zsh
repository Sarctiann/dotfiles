# WSL: add Windows System32 to PATH so markdown-preview.nvim (and other tools)
# can use cmd.exe / start to open URLs in the Windows default browser.
if [[ -d /mnt/c/Windows/System32 ]]; then
  export PATH="/mnt/c/Windows/System32:$PATH"
fi
