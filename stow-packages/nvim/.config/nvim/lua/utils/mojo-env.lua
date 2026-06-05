local M = {}

-- NOTE: Set to true for debugging, false in normal use.
-- Logs go to /tmp/mojo-env.log
local DEBUG = false

local cache = {}
local active_env = nil

local function log(...)
  if not DEBUG then
    return
  end
  local msg = table.concat({ ... }, " ")
  local fp = io.open("/tmp/mojo-env.log", "a")
  if fp then
    fp:write(os.date("%H:%M:%S") .. " " .. msg .. "\n")
    fp:close()
  end
end

--- Prepend a directory to a PATH-like environment variable,
--- but only if it's not already present.
local function env_prepend(var, dir)
  local current = vim.env[var] or ""
  for entry in current:gmatch("[^:]+") do
    if entry == dir then
      return
    end
  end
  vim.env[var] = dir .. ":" .. current
end

--- Walk up from filepath to find the project root,
--- then scan for a mojo environment inside it.
--- Caches the result by directory to avoid repeated scans.
--- NOTE: Cache is never invalidated automatically.
--- If you add mojo to a project that previously had none,
--- call :lua require("utils.mojo-env").reset_cache() or restart Neovim.
function M.find_and_activate(filepath)
  filepath = filepath or vim.fn.expand("%:p")
  log("find_and_activate filepath=", filepath)
  if filepath == "" then
    log("find_and_activate empty filepath, returning false")
    return false
  end

  local dir = vim.fn.fnamemodify(filepath, ":h")
  log("find_and_activate dir=", dir)

  if cache[dir] ~= nil then
    log("find_and_activate cache hit for dir=", dir, "value=", tostring(cache[dir]))
    if cache[dir] == false then
      return false
    end
    M._activate(cache[dir])
    return true
  end

  -- NOTE: vim.fs.root walks upward from filepath looking for these markers.
  -- Order matters: the first match wins. Keep pixi markers before generic ones.
  local markers = { "pixi.toml", "pyproject.toml", ".pixi", ".venv" }
  local root = vim.fs.root(filepath, markers)
  log("find_and_activate vim.fs.root result=", tostring(root))
  if not root then
    log("find_and_activate no root found, caching false for dir=", dir)
    cache[dir] = false
    return false
  end

  local env = M._scan(root)
  log("find_and_activate scan result for root=", root, "env=", vim.inspect(env))
  cache[dir] = env or false

  if env then
    M._activate(env)
    return true
  end

  log("find_and_activate no env found in root, returning false")
  return false
end

--- Scan a project root for mojo-lsp-server.
--- Checks pixi environments first, then .venv.
function M._scan(root)
  log("_scan root=", root)

  local matches = vim.fn.glob(root .. "/.pixi/envs/*/bin/mojo-lsp-server", false, true)
  log("_scan pixi matches count=", #matches)
  if #matches > 0 then
    log("_scan first pixi match=", matches[1])
    local bin_dir = vim.fn.fnamemodify(matches[1], ":h")
    log("_scan pixi bin_dir=", bin_dir)
    return { type = "pixi", bin_dir = bin_dir, env_dir = root }
  end

  local venv_bin = root .. "/.venv/bin/mojo-lsp-server"
  local venv_exists = vim.fn.filereadable(venv_bin) == 1
  log("_scan venv path=", venv_bin, "exists=", tostring(venv_exists))
  if venv_exists then
    return { type = "venv", bin_dir = root .. "/.venv/bin", env_dir = root }
  end

  log("_scan no mojo-lsp-server found in root")
  return nil
end

--- Activate a mojo environment by setting PATH and the environment
--- variables that the mojo toolchain needs to find its std library
--- and runtime libraries.
-- NOTE: The conda activation script at
--   <prefix>/etc/conda/activate.d/10-activate-max.sh
-- sets MODULAR_HOME=${CONDA_PREFIX}/share/max
-- Without this, mojo-lsp-server cannot find std.mojopkg.
function M._activate(env)
  log("_activate type=", env.type, "bin_dir=", env.bin_dir)
  active_env = env

  -- NOTE: env_prepend checks for duplicates to avoid PATH bloat
  -- on repeated activations (e.g. cache miss, or switching projects).
  env_prepend("PATH", env.bin_dir)
  log("_activate PATH=", vim.env.PATH)

  if env.type == "pixi" then
    -- NOTE: fnamemodify(".../bin", ":h") → "..."
    local prefix = vim.fn.fnamemodify(env.bin_dir, ":h")
    vim.env.CONDA_PREFIX = prefix
    vim.env.MODULAR_HOME = prefix .. "/share/max"
    env_prepend("DYLD_FALLBACK_LIBRARY_PATH", prefix .. "/lib")
    log("_activate CONDA_PREFIX=", prefix)
    log("_activate MODULAR_HOME=", vim.env.MODULAR_HOME)
    log("_activate DYLD_FALLBACK_LIBRARY_PATH=", vim.env.DYLD_FALLBACK_LIBRARY_PATH)
  end
end

--- Return the full path to mojo-lsp-server inside the active environment,
--- as a list suitable for lspconfig's cmd option.
--- NOTE: Using a full path (not relying on PATH) ensures argv[0]
--- points to the real binary location, so mojo can resolve std relative to itself.
function M.get_lsp_cmd()
  if not active_env then
    log("get_lsp_cmd no active env, returning nil")
    return nil
  end
  local cmd = { active_env.bin_dir .. "/mojo-lsp-server" }
  log("get_lsp_cmd returning ", vim.inspect(cmd))
  return cmd
end

--- Return the full path to the mojo binary inside the active environment.
function M.get_mojo_cmd()
  if not active_env then
    return nil
  end
  return active_env.bin_dir .. "/mojo"
end

function M.get_active()
  return active_env
end

function M.set_debug(enabled)
  DEBUG = enabled
  log("set_debug enabled=", tostring(enabled))
end

function M.reset_cache()
  cache = {}
  active_env = nil
  log("reset_cache called")
end

return M
