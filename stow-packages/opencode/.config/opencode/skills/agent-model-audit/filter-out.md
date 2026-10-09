## Filter these models out

- **Nemotron**: from any provider
- **GPT models**: from any provider
- **Gemini models**: from any provider
- **Models that train on request data**: any model whose provider uses prompts/completions for training
  (e.g. Go/Meta "Contributor" tier: `muse-spark-1.3-contributor`, `muse-spark-1.2-contributor`).
  Requests to these fail with "This Go model trains on request data" unless the workspace allows
  training in Privacy settings — assume the user has it disabled. Check the provider's Privacy table.
- **Paid opencode/ (Zen) models**: any `opencode/*` model that is not free (not `*-free` or `big-pickle`)
  → Prefer `opencode-go/*` alternatives for paid model needs

## Try to use (if not in the previous list)

- `opencode-go/*` — primary provider for all paid agent models
- `opencode/big-pickle` — free model with near-best intelligence
- `opencode/*-free` — free Zen models for exploration and low-cost roles
