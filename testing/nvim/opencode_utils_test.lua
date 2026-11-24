local utils = require("utils.opencode_utils")

local function eq(actual, expected, label)
  if vim.deep_equal(actual, expected) then
    return
  end
  error(string.format("%s\nexpected: %s\nactual:   %s", label, vim.inspect(expected), vim.inspect(actual)))
end

local LOCAL_SAMPLE = table.concat({
  "",
  "  Open a link to connect. Links work once and expire in 5 minutes.",
  "",
  "  http://127.0.0.1:49374/auth/connect/abc123",
  "  http://192.168.0.200:49374/auth/connect/abc123",
  "  https://tunnel.example.opentunnel.xyz/auth/connect/abc123",
  "",
  "  █████",
  "  █ ▄▄█",
  "  ██▄██",
  "",
}, "\n")

local parsed = utils._parse_pair_output(LOCAL_SAMPLE)
eq(#parsed.links, 3, "links count")
eq(parsed.links[3], "https://tunnel.example.opentunnel.xyz/auth/connect/abc123", "remote link")
eq(parsed.code, "abc123", "pairing code")
eq(parsed.qr, { "█████", "█ ▄▄█", "██▄██" }, "qr block without indent")

local deduped = utils._parse_pair_output("  http://127.0.0.1:1/auth/connect/x\n  http://127.0.0.1:1/auth/connect/x\n")
eq(#deduped.links, 1, "duplicate links collapsed")
eq(deduped.qr, nil, "no qr block yields nil")

local urls = utils._classify_urls({
  "http://127.0.0.1:49374/auth/connect/t",
  "http://192.168.0.200:49374/auth/connect/t",
  "https://x1.opentunnel.xyz/auth/connect/t",
})
eq(urls.remote, "https://x1.opentunnel.xyz/auth/connect/t", "remote link")
eq(urls.lan, "http://192.168.0.200:49374/auth/connect/t", "lan link")
eq(urls.loopback, "http://127.0.0.1:49374/auth/connect/t", "loopback link")

local off = utils._classify_urls({ "http://127.0.0.1:49374/x" })
eq(off.remote, nil, "no remote link when tunnel is off")

local service = '{"url":"http://0.0.0.0:49374","password":"pw"}'
local info = '{"urls":["http://127.0.0.1:49374","https://x1.opentunnel.xyz"]}'
local state = utils._service_state(service, info)
eq(state.tunnel, true, "tunnel detected")
eq(state.remote_url, "https://x1.opentunnel.xyz", "remote url from info")
eq(state.service_url, "http://127.0.0.1:49374", "0.0.0.0 rewritten to loopback")

local down = utils._service_state(nil, nil)
eq(down.tunnel, false, "tunnel off without service file")
if not down.error then
  error("expected an error message when service state is unavailable")
end

local done, live = false, nil
utils.get_service_state(function(state)
  done, live = true, state
end)
vim.wait(5000, function()
  return done
end, 50)
if not done then
  error("get_service_state never called back")
end
if live.error then
  error("get_service_state error: " .. live.error)
end
eq(type(live.tunnel), "boolean", "tunnel flag is boolean")

local ready = {
  kind = "ready",
  links = { "https://x1.opentunnel.xyz/auth/connect/abc" },
  code = "abc",
  qr = { "█████", "█ ▄▄█", "██▄██" },
  remote = true,
  remote_url = "https://x1.opentunnel.xyz/auth/connect/abc",
  lan_url = "http://192.168.0.200:49374/auth/connect/abc",
  created_at = os.time(),
  expires_at = os.time() + 300,
}

local wide = utils._layout(ready, 120)
eq(wide.qr_shown, true, "qr shown when it fits")
eq(wide.lines[1], " █████", "qr starts the body")

local narrow = utils._layout(ready, 4)
eq(narrow.qr_shown, false, "qr hidden when terminal is narrower than the qr")
if not table.concat(narrow.lines, "\n"):find("ancho", 1, true) then
  error("narrow layout must explain that the QR needs a wider terminal")
end

local expired = vim.deepcopy(ready)
expired.kind = "expired"
expired.expires_at = os.time() - 1
local expired_lines = table.concat(utils._layout(expired, 120).lines, "\n")
if not expired_lines:find("Expirado", 1, true) then
  error("expired layout must say the link expired")
end

local off = { kind = "off", remote = false, links = {} }
local off_lines = table.concat(utils._layout(off, 120).lines, "\n")
if not off_lines:find("Remote off", 1, true) then
  error("off layout must report that remote access is off")
end

local short = utils._layout(ready, 120, 10)
eq(short.qr_shown, false, "qr hidden when the terminal is too short")
if not table.concat(short.lines, "\n"):find("QR", 1, true) then
  error("short layout must explain that the QR needs more room")
end

local unicode_qr = { kind = "ready", links = {}, qr = { "█████" }, remote = true }
eq(utils._layout(unicode_qr, 10).qr_shown, true, "qr width must be measured in display cells, not bytes")

utils.open_pair_float(ready)
if not (utils._float and vim.api.nvim_win_is_valid(utils._float.win)) then
  error("open_pair_float did not open a window")
end
local body = table.concat(vim.api.nvim_buf_get_lines(utils._float.buf, 0, -1, false), "\n")
if not body:find("█████", 1, true) then
  error("float buffer does not contain the QR block")
end
utils.close_pair_float()
eq(utils._float, nil, "close_pair_float clears the float")
eq(utils._state, ready, "close_pair_float keeps the state")

local finished = false
utils._state = nil
utils.pair(false)
vim.wait(20000, function()
  return utils._state and utils._state.kind == "ready"
end, 100)
finished = utils._state ~= nil and utils._state.kind == "ready"
utils.close_pair_float()
if not finished then
  error("pair(false) did not reach the ready state")
end
if #utils._state.links == 0 then
  error("pair(false) captured no links")
end
if not utils._state.qr or #utils._state.qr == 0 then
  error("pair(false) captured no QR block")
end

utils.close_pair_float()
utils._job = 424242
local before = utils._state
utils.pair(false)
eq(utils._job, 424242, "a second pair call must not replace the running job")
eq(utils._state, before, "a second pair call must not reset state")
utils._job = nil

utils._state = nil
utils.show_info()
vim.wait(20000, function()
  return utils._state and (utils._state.kind == "ready" or utils._state.kind == "error")
end, 100)
local shown = utils._state
utils.close_pair_float()
if not shown then
  error("show_info did not produce state")
end
if shown.kind == "ready" and shown.remote_url == nil then
  error("ready state from show_info must have a remote link when the tunnel is on")
end

local original_pair = utils.pair
local original_state = utils.get_service_state
local pair_calls = 0
utils.pair = function()
  pair_calls = pair_calls + 1
end
utils.get_service_state = function(cb)
  cb({ tunnel = false })
end
utils.show_info()
eq(pair_calls, 0, "show_info must not start a pair job when the tunnel is off")
eq(utils._state and utils._state.kind, "off", "show_info reports the off state")
utils.pair = original_pair
utils.get_service_state = original_state
utils.close_pair_float()

local notified = nil
local original_notify = vim.notify
vim.notify = function(msg)
  notified = msg
end
local closed_ready = vim.deepcopy(ready)
utils.update_pair_float(closed_ready)
eq(utils._float, nil, "update_pair_float must not reopen a float the user closed")
if not (notified and notified:find("listo", 1, true)) then
  error("update_pair_float should notify when the float is closed")
end
vim.notify = original_notify

print("opencode_utils: all tests passed")
