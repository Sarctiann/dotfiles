local DOCS_DIR = os.getenv("DOCS_DIR")
local plugin_dir = DOCS_DIR and (DOCS_DIR .. "/SARCTIANN/LuaCode/custom_plugins/cli-integration.nvim/") or nil

local gemini_utils = require("utils.gemini_utils")
local augment_utils = require("utils.augment_utils")
local opencode_utils = require("utils.opencode_utils")

-- Static check: are we inside COMPANY_DIR at load time?
-- Uses augment_utils.get_augment_cache_dir() as canonical cache_dir source.
local company_dir_str = os.getenv("COMPANY_DIR") or ""
local is_company_project = false
if company_dir_str ~= "" then
  local company_dir = vim.fn.expand(company_dir_str):gsub("/+$", "")
  local current_dir = vim.fn.getcwd()
  is_company_project = (current_dir .. "/"):sub(1, #company_dir + 1) == company_dir .. "/"
end

local integration_op
local keys_op

if is_company_project then
  local cache_dir = augment_utils.get_augment_cache_dir()

  integration_op = {
    name = "Augment",
    cli_cmd = "auggie --augment-cache-dir=" .. vim.fn.shellescape(cache_dir),
    cli_ready_flags = { search_for = "Version" },
    start_doing = function(visual_text, actions)
      require("cli-integration.hooks").insert_current_path_or_explain_selection()(visual_text, actions, "Augment")
    end,
    on_open = function(_, _)
      local nvim_soc = os.getenv("NVIM") or vim.v.servername
      augment_utils.on_open_auggie(cache_dir, {
        neovim = { NVIM_SOCKET_PATH = nvim_soc },
        jira = { JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN") },
      })
    end,
    format_paths = function(paths, actions)
      if #paths == 1 then
        actions.send_keys("@" .. paths[1] .. " ")
      else
        actions.for_each_path(function(path)
          actions.send_keys("@" .. path)
          actions.send_line()
        end)
      end
    end,
    window_width = 45,
    terminal_keys = {
      terminal_mode = {
        normal_mode = { "<M-q>" },
        insert_file_path = { "<C-o>" },
        insert_all_buffers = { "<C-o><C-o>" },
      },
    },
  }

  keys_op = {
    {
      "<leader>aa",
      function()
        augment_utils.new_session(cache_dir)
      end,
      desc = "Augment New Session",
      silent = true,
      mode = { "n", "v" },
    },
    {
      "<leader>aq",
      function()
        augment_utils.ask_inline(cache_dir)
      end,
      desc = "Augment Ask (inline)",
      mode = { "n", "v" },
    },
    {
      "<leader>as",
      nil,
      desc = " Augment Code Sessions",
      silent = true,
    },
    {
      "<leader>asc",
      function()
        augment_utils.resume_last_session(cache_dir)
      end,
      desc = "Augment Code Resume last session",
      silent = true,
    },
    {
      "<leader>asd",
      function()
        augment_utils.delete_all_augment_sessions(cache_dir)
      end,
      desc = "Augment Code Delete All sessions",
      silent = true,
    },
    {
      "<leader>ass",
      function()
        augment_utils.manage_augment_sessions(false, cache_dir)
      end,
      desc = "Augment Code Custom Session Manager",
      silent = true,
    },
  }
else
  integration_op = {
    name = "OpenCode",
    cli_cmd = opencode_utils.get_cli_cmd(),
    cli_ready_flags = { search_for = "Ask", from_line = 22, lines_amt = 12 },
    on_open = function()
      opencode_utils.on_open()
    end,
    start_doing = function(visual_text, actions)
      require("cli-integration.hooks").insert_current_path_or_explain_selection()(visual_text, actions, "OpenCode")
    end,
    format_paths = function(paths, actions)
      if #paths == 1 then
        actions.send_keys("@" .. paths[1])
        actions.wait(250)
        actions.send_keys("<CR>")
      else
        actions.for_each_path(function(path)
          actions.send_keys("@" .. path)
          actions.wait(250)
          actions.send_keys("<CR>")
          actions.send_line()
        end)
      end
    end,
    on_ask_submit = function(data, actions)
      if data.selection then
        actions.send_line("```")
        actions.send_keys("@" .. data.relative_file)
        actions.wait(250)
        actions.send_keys("<CR>")
        actions.send_line(" L" .. data.start_line .. "-L" .. data.end_line)
        actions.send_line(data.selection)
        actions.send_line("```")
      else
        actions.send_keys("@" .. data.relative_file)
        actions.wait(250)
        actions.send_keys("<CR>")
        actions.send_line(" L" .. data.start_line)
      end
      actions.send_line()
      actions.send_line(data.question)
      actions.submit()
    end,
    keep_open = false,
    window_width = 45,
    terminal_keys = {
      terminal_mode = {
        normal_mode = { "<M-q>" },
        insert_file_path = { "<C-o>" },
        insert_all_buffers = { "<C-o><C-o>" },
      },
    },
  }

  keys_op = {
    {
      "<leader>aa",
      ":CLIIntegration open_root OpenCode<CR>",
      desc = "OpenCode New Session",
      silent = true,
      mode = { "n", "v" },
    },
    {
      "<leader>aq",
      function()
        require("cli-integration").hooks.ask("OpenCode")
      end,
      desc = "OpenCode Ask (inline)",
      mode = { "n", "v" },
    },
    {
      "<leader>as",
      nil,
      desc = " OpenCode Sessions & Server",
      silent = true,
    },
    {
      "<leader>asc",
      ":CLIIntegration open_root OpenCode --continue<CR>",
      desc = "OpenCode Resume Latest",
      silent = true,
    },
    {
      "<leader>ass",
      function()
        opencode_utils.manage_opencode_sessions(false)
      end,
      desc = "OpenCode Session Manager",
      silent = true,
    },
    {
      "<leader>asd",
      opencode_utils.delete_all_opencode_sessions,
      desc = "OpenCode Delete Project Sessions",
      silent = true,
    },
    {
      "<leader>asi",
      function()
        opencode_utils.show_info()
      end,
      desc = "OpenCode Status",
      silent = true,
    },
    {
      "<leader>ast",
      opencode_utils.toggle_tunnel,
      desc = "OpenCode Toggle Tunnel",
      silent = true,
    },
    {
      "<leader>ask",
      function()
        opencode_utils.inspect_opencode_processes()
      end,
      desc = "OpenCode Inspect Processes",
      silent = true,
    },
  }
end

local plugin_spec = {
  --- @module 'cli-integration'
  {
    "Sarctiann/cli-integration.nvim",
    cmd = "CLIIntegration",
    --- @type Cli-Integration.Config
    opts = {
      debug = false,
      window_features = {
        auto_insert = true,
        buffer_lock = true,
        dynamic_resize = true,
        fullscreen = true,
        nav_keymaps = true,
        start_insert_on_click = true,
      },
      show_help_on_open = true,
      new_lines_amount = 1,
      start_insert_on_click = true,
      adapters = {
        bufferline = true,
      },
      list_buffer = false,
      window_width = 40,
      window_padding = 1,
      terminal_keys = {
        terminal_mode = {
          normal_mode = { "<M-q>" },
          insert_file_path = { "<C-p>" },
          insert_all_buffers = { "<C-p><C-p>" },
          new_lines = { "<S-CR>" },
          submit = { "<C-s>", "<C-CR>" },
          enter = { "<CR>" },
          help = { "<M-?>", "??", "\\\\" },
          toggle_fullscreen = { "<C-w>" },
        },
        normal_mode = {
          hide = { "<Esc>" },
          toggle_fullscreen = { "<C-f>" },
        },
      },
      integrations = {
        integration_op,
        {
          name = "Gemini",
          cli_cmd = "gemini",
          cli_ready_flags = { search_for = "Type your", from_line = 15, lines_amt = 15 },
          start_doing = function(visual_text, actions)
            require("cli-integration.hooks").insert_current_path_or_explain_selection()(visual_text, actions, "Gemini")
          end,
          format_paths = function(paths, actions)
            actions.send_keys("@" .. paths[1] .. " ")
          end,
          window_width = 45,
        },
      },
    },
    keys = vim.list_extend(
      {
        {
          "<leader>a",
          nil,
          desc = "AI",
          silent = true,
          mode = { "n", "v" },
        },
      },
      vim.list_extend({
        {
          "<leader>ag",
          ":CLIIntegration open_root Gemini<CR>",
          desc = "Gemini New Session",
          silent = true,
          mode = { "n", "v" },
        },
        {
          "<leader>aQ",
          function()
            require("cli-integration").hooks.ask("Gemini")
          end,
          desc = "Gemini Ask (inline)",
          silent = true,
          mode = { "n", "v" },
        },
        {
          "<leader>aS",
          nil,
          desc = " Gemini Sessions",
          silent = true,
        },
        {
          "<leader>aSc",
          ":CLIIntegration open_root Gemini --resume latest<CR>",
          desc = "Gemini Resume Latest",
          silent = true,
        },
        {
          "<leader>aSs",
          function()
            gemini_utils.manage_gemini_sessions(false)
          end,
          desc = "Gemini Session Manager",
          silent = true,
        },
        {
          "<leader>aSd",
          gemini_utils.delete_all_gemini_sessions,
          desc = "Gemini Delete Project Sessions",
          silent = true,
        },
      }, keys_op)
    ),
  },
}

if plugin_dir and vim.fn.isdirectory(plugin_dir) == 1 then
  plugin_spec[1].dev = true
  plugin_spec[1].dir = plugin_dir
end

return plugin_spec
