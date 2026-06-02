---
name: agent-model-audit
description: Use when auditing agent models, reviewing provider offerings, optimizing model assignments by cost and speed, or updating agent descriptions with cost/speed indicators. Trigger keywords: "audit agents", "audit models", "update agent models", "review models", "optimize agents".
---

# Agent Model Audit

Audit connected providers, analyze model offerings (cost, speed, usage limits), and optimize agent-to-model assignments. Produces a dated audit report and updates agent configurations.

> **Important:** The current model assignments in `opencode.jsonc` are the **output** of this process, not the input. Discard them at the start. All assignments will be determined fresh from the data gathered in steps 1–5.

## Priority Mode

The optimization priority is determined by an optional argument passed to the command:

| Argument (EN/ES)                              | Priority Order          |
| --------------------------------------------- | ----------------------- |
| `skill` / `ability` / `habilidad` _(default)_ | Role fit → Cost → Speed |
| `price` / `cost` / `precio` / `barato`        | Cost → Role fit → Speed |
| `speed` / `fast` / `velocidad` / `rapido`     | Speed → Role fit → Cost |

If no argument was provided, use **`skill`** mode (role fit first).

## Workflow

### 1. Discover Available Models

Run the following command to get the authoritative list of models available in opencode:

```bash
opencode models
```

This returns the full list of `provider/model` identifiers actually configured and accessible. **This is the only source of truth** — do not use general knowledge or assumptions about what models exist.

From the output:

- Note every `provider/model` identifier
- Group by provider
- Identify which providers are active (not in `disabled_providers` in `opencode.jsonc`)

> **Critical:** Only models that appear in `opencode models` output are candidates for agent assignment.
>
> **⚠️ Model identifiers must match EXACTLY — character for character.**
> Pay close attention to punctuation. Model names use hyphens, not dots:
>
> - ✅ `opencode/claude-sonnet-4-6` (correct — hyphens)
> - ❌ `opencode/claude-sonnet-4.6` (incorrect — dot)
> - ✅ `opencode/gpt-5.4` (correct — dot is part of the version)
> - ❌ `opencode/gpt-5-4` (incorrect — hyphen instead of dot)
>
> **Never guess or normalize model names.** Always copy-paste the exact identifier
> from the `opencode models` output. This applies to all steps that reference
> model names (steps 2, 3, 5, 6, 7, 8, and 9).

Also read `opencode.jsonc` to collect **agent names and their roles** (from descriptions and `agents/*.md` files). Ignore current model assignments — those will be replaced.

### 2. Research Model Characteristics and Validate URLs

For each model listed in step 1, gather from provider documentation:

- **Cost per request** — from provider pricing pages
- **Requests per time window** — from rate limit docs
- **Speed/latency** — fast / normal / slow
- **Context window** — maximum input tokens
- **Best use case** — reasoning, coding, analysis, quick tasks, etc.

**Key sources per provider:**

- **opencode-go**: `https://opencode.ai/docs/go/#usage-limits`
- **opencode-zen**: `https://opencode.ai/docs/zen/#pricing`
- **GitHub Copilot (pricing)**: `https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing`
- **GitHub Copilot (multipliers)**: `https://docs.github.com/en/copilot/reference/copilot-billing/model-multipliers-for-annual-plans`
- **OpenRouter / Zen**: `https://openrouter.ai/models`
- **Other providers**: consult their official documentation

**URL Validation — REQUIRED:**

For every URL listed above that you navigate to:

1. If the page loads successfully → use it as-is.
2. If the page returns 404 or redirects to an unrelated page → search for the correct URL, then **update this SKILL.md** with the correct URL before continuing. This ensures future executions use the correct URL.

### 3. Collect Concrete Model Data

For each confirmed-available model, extract the following **numeric** values from your step 2 research:

- **Intelligence Score** (0–100): A numeric capability score based on reasoning and coding benchmarks (MMLU-Pro, GPQA, HumanEval, SWE-bench, etc.) and/or community consensus. The goal is a single comparable number per model. If multiple benchmarks are available, use a weighted average.
- **Cost per Million Tokens** (USD): The provider's listed cost per 1M input tokens. Use the input token price as the standard comparator.
- **Speed** (tokens/second): Measured output tokens per second from provider docs or community benchmarks. If only latency is available, convert to a comparable throughput estimate.

> **Important:** These must be actual numeric values from research, not subjective categories. If exact numbers aren't available, estimate conservatively and note the source.

Record the data in a structured JSON file at `docs/agent-audits/model-data.json` for later use with the scale calculator script. Example:

```json
{
  "models": {
    "provider/model-name": {
      "intelligence": 82,
      "cost": 3.50,
      "speed": 120
    }
  }
}
```

### 4. Identify Agent Roles

Read each `agents/*.md` file and `opencode.jsonc` agent descriptions. For each agent, determine its role:

| Role archetype         | Needs                                     |
| ---------------------- | ----------------------------------------- |
| Reasoning/architecture | Deep thinking, extended context           |
| Implementation         | Precision, balanced speed                 |
| Quick tasks            | Fast, low latency                         |
| Large context analysis | High context window                       |
| Execution/terminal     | Reliable, fast, good at structured output |
| General purpose        | Balanced across all dimensions            |

### 5. Propose Optimized Assignments

Assign each agent a model from the step-1 list. Apply the **Priority Mode** from the top of this skill to determine the ordering of trade-offs.

**Default (`skill` mode) — Role fit → Cost → Speed:**

1. Find the model whose capabilities best match the agent's role archetype (step 4)
2. Among models equally suited to the role, prefer the cheaper one
3. Among equally cheap models, prefer the faster one

**`price` mode — Cost → Role fit → Speed:**

1. Start with the cheapest models and work up
2. Among equally cheap models, pick the one that best fits the role
3. Among equally good fits at the same price, prefer the faster one

**`speed` mode — Speed → Role fit → Cost:**

1. Start with the fastest models
2. Among equally fast models, pick the one that best fits the role
3. Among equally good fits at the same speed, prefer the cheaper one

**All modes — non-negotiable constraints:**

- **No duplicate models** — each agent must use a unique model
- **Only models from step 1** — never assign a model not confirmed available
- **No assignment left blank** — every agent must have a model
- **Exact identifier match** — model names must be copied verbatim from step 1 output, including all hyphens, dots, and version numbers. Never modify, normalize, or guess identifiers.

Save the resulting assignments to `docs/agent-audits/assignments.json` for use in step 6.

### 6. Calculate Scale-Based Indicators

After assigning models to all agents (step 5), compute the quality, cost, and speed indicators **relative to the selected set of models only**.

Run the scale calculator script with your collected data and assignments:

```bash
python skills/agent-model-audit/scripts/scale-calculator.py \
  --data docs/agent-audits/model-data.json \
  --assignments docs/agent-audits/assignments.json \
  --format json \
  --output docs/agent-audits/scale-results.json
```

The JSON output contains `value`, `tier`, `icon`, and `label` for each dimension of each selected model.

**Algorithm:**

For each dimension:

1. Collect the numeric values for all assigned models
2. Apply the dimension-specific rule for `---`
3. Find the relevant minimum and maximum values
4. Calculate the range: `range = max - min`
5. Divide the relevant range into equal segments
6. Assign icons based on which segment each model falls into:

### Dimension Rules

- **Intelligence:** `---` means `Basic`. Use all intelligence values and split the full range into 4 equal segments.
- **Cost:** `---` means `Free`. Use `---` only when cost is exactly `0`. Split the positive-cost range into 3 equal segments for the remaining tiers.
- **Speed:** `---` means `Unknown`. Use `---` only when the model has no speed value. Split the known-speed range into 3 equal segments for the remaining tiers.

| Dimension      | Segment 1               | Segment 2                | Segment 3               | Segment 4                 |
| -------------- | ----------------------- | ------------------------ | ----------------------- | ------------------------- |
| Intelligence   | `--- ` (0 — Basic)      | `󰫣   ` (1 — Good)       | `󰫣󰫣  ` (2 — Very Good) | `󰫣󰫣󰫣 ` (3 — Excellent) |
| Cost           | `--- ` (0 — Free)       | `   ` (1 — Economic)    | `  ` (2 — Normal)     | ` ` (3 — Expensive)  |
| Speed          | `--- ` (0 — Unknown)    | `󱐋  ` (1 — Slow)        | `󱐋󱐋 ` (2 — Normal)     | `󱐋󱐋󱐋` (3 — Fast)       |

> **Edge cases:**
> - If intelligence has no spread (`range = 0`), assign the second segment (1 icon) to all models.
> - If all selected costs are `0`, assign `---` to all cost values.
> - If the positive cost range has no spread, assign the second non-zero segment (2 icons) to all positive-cost models.
> - If no speed values are known, assign `---` to all speed values.
> - If the known speed range has no spread, assign the second non-zero segment (2 icons) to all known-speed models.

> **Note:** For intelligence and speed, more icons = better. For cost, fewer icons = cheaper (better).

### 7. Create Audit Report

Write to `docs/agent-audits/YYYY-MM-DD.md`:

```markdown
# Agent Model Audit — YYYY-MM-DD

## Priority Mode

`skill` (role fit first)

## Providers Connected

| Provider    | Models Available | Notes                  |
| ----------- | ---------------- | ---------------------- |
| opencode-go | 12               | Go subscription active |

## Model Analysis

Numeric data collected in step 3:

| Model             | Intelligence | Cost ($/1M tok) | Speed (t/s) |
| ----------------- | ------------ | ---------------- | ----------- |
| deepseek-v4-flash | 65           | 0.15             | 200         |
| minimax-m2.5      | 60           | 0.20             | 180         |
| qwen3.5-plus      | 72           | 0.35             | 150         |
| qwen3.6-plus      | 78           | 1.50             | 100         |
| deepseek-v4-pro   | 85           | 2.00             | 90          |
| minimax-m2.7      | 80           | 1.80             | 170         |
| mimo-v2.5-pro     | 88           | 8.00             | 45          |
| kimi-k2.6         | 82           | 6.00             | 50          |
| glm-5.1           | 90           | 10.00            | 40          |
| claude-sonnet-4-6 | 95           | 15.00            | 80          |

## Scale Calculation

Range divided per dimension (computed in step 6):

| Dimension    | Min / Scope      | Max / Scope      | Range | Q1 (< )     | Q2 (< )     | Q3 (< )     | Q4 (>=)     |
| ------------ | ---------------- | ---------------- | ----- | ----------- | ----------- | ----------- | ----------- |
| Intelligence | 60               | 95               | 35    | 60–69       | 69–78       | 78–87       | 87–95       |
| Cost         | 0.15 (positive)  | 15.0 (positive)  | 14.85 | 0.15–3.86   | 3.86–7.58   | 7.58–11.29  | 11.29–15.00 |
| Speed        | 40 (known)       | 200 (known)      | 160   | 40–80       | 80–120      | 120–160     | 160–200     |

## Proposed Assignments

| Agent   | Model             | Intelligence | Cost | Speed | Role Fit  | Rationale           |
| ------- | ----------------- | ------------ | ---- | ----- | --------- | ------------------- |
| build   | qwen3.6-plus      | 󰫣󰫣          |     | 󱐋󱐋    | Good      | Balanced for coding |
| z-spark | deepseek-v4-flash | 󰫣           |     | 󱐋󱐋󱐋   | Excellent | Fast & cheap        |
| ...     | ...               | ...          | ...  | ...   | ...       | ...                 |

## Changes from Previous Config

- Assigned `z-forge` → `mimo-v2.5-pro` (precision coding, best role fit)
- Assigned `explore` → `minimax-m2.5` (fast exploration, lowest cost)
- Updated all agent descriptions with `[quality | cost | speed]` indicators

## Uniqueness Check

All agents use unique models: ✅
```

### 8. Update Configurations

All model assignments must come **exclusively** from models confirmed in step 1.

> **⚠️ CRITICAL:** Before writing any model identifier to `opencode.jsonc`,
> verify it character-for-character against the `opencode models` output from step 1.
> Common mistakes: replacing hyphens with dots (`claude-sonnet-4-6` → `claude-sonnet-4.6`)
> or vice versa. Always copy-paste, never type from memory.

**`opencode.jsonc`:**

- Set `agent.<name>.model` for every agent from the proposed assignments in step 7
- Set `agent.<name>.description` with `[quality | cost | speed]` prefix

**`agents/*.md`:**

- Do NOT add or modify `description` in agent `.md` frontmatter.
- The `description` field with `[quality | cost | speed]` indicators must ONLY exist in `opencode.jsonc`.
- Agent `.md` files contain the agent's behavioral instructions (mode, tools, system prompt).
- Duplicating descriptions in both places creates drift and confusion.

**Format:** `[quality | cost | speed] Description text`

- Quality padded to 4 chars: `--- ` (Basic), `󰫣   ` (Good), `󰫣󰫣  ` (Very Good), `󰫣󰫣󰫣 ` (Excellent)
- Cost padded to 4 chars: `--- ` (Free only when cost is `0`), `   ` (Economic), `  ` (Normal), ` ` (Expensive)
- Speed padded to 4 chars: `--- ` (Unknown only when speed is missing), `󱐋  ` (Slow), `󱐋󱐋 ` (Normal), `󱐋󱐋󱐋` (Fast)
- Example: `[󰫣󰫣 |   | 󱐋󱐋 ] Reasoning architect for decomposition and design decisions`

### 9. Verify

- No duplicate models across agents ✅
- All agent descriptions have `[quality | cost | speed]` indicators ✅
- Scale calculation ran on selected models only ✅
- Icons assigned by range quarters (Q1 → `---`, Q2 → 1 icon, Q3 → 2 icons, Q4 → 3 icons) ✅
- All assigned models came from `opencode models` output ✅
- **All model identifiers match `opencode models` output character-for-character** ✅
- Audit report saved to `docs/agent-audits/YYYY-MM-DD.md` ✅
- `opencode.jsonc` is valid JSONC ✅

## Notes

- `docs/agent-audits/` should be gitignored (working documents, not committed)
- Config changes (`opencode.jsonc`) should be committed
- Agent `.md` files should only be committed if their behavioral content (mode, tools, system prompt) was modified — not for description changes
- Remind user to restart opencode after config changes
