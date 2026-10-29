import { Plugin } from "@opencode/plugin/tui"

export default Plugin.define({
  id: "dotfiles.tabs",
  setup(context) {
    context.keymap.layer(() => ({
      mode: "global",
      priority: 10,
      commands: [
        {
          id: "dotfiles.tabs.close_all",
          title: "Close all session tabs",
          group: "Tabs",
          bind: "tabq",
          palette: true,
          run: () => {
            const sessionIDs = context.ui.tabs.list().map((tab) => tab.sessionID)
            for (const sessionID of sessionIDs) context.ui.tabs.close(sessionID)
          },
        },
      ],
    }))
  },
})
