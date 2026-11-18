-- Agent notifications (see ~/.local/bin/agent-notify) for agents running in a :terminal.
--
-- Claude Code announces permission prompts and questions with an OSC 9 desktop notification
-- (preferredNotifChannel "iterm2"). Neovim receives it as a TermRequest and forwards it to agent-notify, which skips
-- it when you are watching that terminal. The transcript watcher (claude_notify_watcher.py) can't see permission
-- prompts in Claude's "auto" permission mode: the tool_use is only written once the prompt is answered.
-- "Waiting for your input" (Claude idle for 60s) is dropped: the watcher already notified when the turn ended.
-- OSC 9;N;... sequences (9;4 is the progress bar) aren't notifications.
--
-- Source, event and pid match what the watcher sends for the same prompt ("claude", "permission" / "ask", the claude
-- pid), so agent-notify drops the second one as a duplicate.

local agent_notify = vim.fn.expand("~/.local/bin/agent-notify")
local shells = { sh = true, bash = true, zsh = true, fish = true, dash = true }

--- The agent behind a :terminal job: the job itself, or its first child when the job is a shell running it.
local function agent_proc(job_pid)
  local proc = vim.api.nvim_get_proc(job_pid)
  if proc and shells[proc.name] then
    local child = vim.api.nvim_get_proc_children(job_pid)[1]
    local child_proc = child and vim.api.nvim_get_proc(child)
    if child_proc then
      return child, child_proc.name
    end
  end
  return job_pid, proc and proc.name or "agent"
end

vim.api.nvim_create_autocmd("TermRequest", {
  group = vim.api.nvim_create_augroup("AgentNotify", { clear = true }),
  callback = function(ev)
    local seq = type(ev.data) == "table" and ev.data.sequence or ev.data
    if type(seq) ~= "string" then
      return
    end
    local text = seq:match("^\027%]9;(.*)$")
    if not text or text:match("^%d+;") then
      return
    end
    text = text:gsub("[\007\027\\]+$", "")
    local lower = text:lower()
    if lower:find("waiting for your input", 1, true) then
      return
    end
    local event = lower:find("permission", 1, true) and "permission" or "ask"
    local job_pid = vim.b[ev.buf].terminal_job_pid
    if not job_pid or vim.fn.executable(agent_notify) == 0 then
      return
    end
    local pid, name = agent_proc(job_pid)
    vim.system({
      agent_notify, "emit",
      "--source", name,
      "--event", event,
      "--message", text,
      "--pid", tostring(pid),
    }, { detach = true })
  end,
})
