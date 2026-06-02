#!/usr/bin/env python3
"""Calculate relative model indicators for the agent model audit."""

import argparse
import json
import sys


DIMENSIONS = ("intelligence", "cost", "speed")

ICONS = {
    "intelligence": {0: "--- ", 1: "󰫣   ", 2: "󰫣󰫣  ", 3: "󰫣󰫣󰫣 "},
    "cost":         {0: "--- ", 1: "   ", 2: "  ", 3: " "},
    "speed":        {0: "--- ", 1: "󱐋  ", 2: "󱐋󱐋 ", 3: "󱐋󱐋󱐋"},
}

LABELS = {
    "intelligence": {0: "Basic", 1: "Good", 2: "Very Good", 3: "Excellent"},
    "cost":         {0: "Free", 1: "Economic", 2: "Normal", 3: "Expensive"},
    "speed":        {0: "Unknown", 1: "Slow", 2: "Normal", 3: "Fast"},
}


def load_json(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def unique_preserving_order(values):
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def selected_models(all_models, assignments_path, model_args):
    if assignments_path:
        assignments = load_json(assignments_path)
        if isinstance(assignments, dict):
            selected = list(assignments.values())
        elif isinstance(assignments, list):
            selected = assignments
        else:
            raise ValueError("Assignments must be an object or an array of model names")
    elif model_args:
        selected = model_args
    else:
        selected = list(all_models)

    missing = [model for model in selected if model not in all_models]
    if missing:
        raise ValueError(f"Selected models missing from data: {', '.join(missing)}")

    return unique_preserving_order(selected)


def validate_model_data(model_data):
    for model, values in model_data.items():
        for dimension in DIMENSIONS:
            value = values.get(dimension)
            if dimension == "speed" and value is None:
                continue
            if not isinstance(value, (int, float)):
                raise ValueError(f"{model}.{dimension} must be numeric")


def build_scale_info(values, segments):
    if not values:
        return {
            "min": None,
            "max": None,
            "range": 0,
            **{f"q{index}_boundary": None for index in range(1, segments)},
        }

    minimum = min(values)
    maximum = max(values)
    span = maximum - minimum
    step = span / float(segments) if span else 0

    info = {
        "min": minimum,
        "max": maximum,
        "range": span,
    }
    for index in range(1, segments):
        info[f"q{index}_boundary"] = minimum + (step * index if span else 0)

    return info


def tier_from_boundaries(value, boundaries):
    for index, boundary in enumerate(boundaries):
        if value < boundary:
            return index
    return len(boundaries)


def tier_for_scaled_value(value, info, segments, fallback_tier):
    if info["min"] is None or info["range"] == 0:
        return fallback_tier

    boundaries = [info[f"q{index}_boundary"] for index in range(1, segments)]
    return tier_from_boundaries(value, boundaries)


def tier_for_nonzero_scale(value, info, segments, fallback_tier):
    if info["min"] is None:
        return fallback_tier
    if info["range"] == 0:
        return fallback_tier

    boundaries = [info[f"q{index}_boundary"] for index in range(1, segments)]
    return tier_from_boundaries(value, boundaries) + 1


def scale_info(values):
    return build_scale_info(values, 4)


def calculate(model_data):
    intelligence_values = [values["intelligence"] for values in model_data.values()]
    cost_values = [values["cost"] for values in model_data.values()]
    speed_values = [values.get("speed") for values in model_data.values()]

    scale = {
        "intelligence": scale_info(intelligence_values),
        "cost": scale_info([value for value in cost_values if value > 0]),
        "speed": scale_info([value for value in speed_values if value is not None]),
        "cost_free_count": sum(1 for value in cost_values if value == 0),
        "speed_unknown_count": sum(1 for value in speed_values if value is None),
    }

    results = {}
    for model, values in model_data.items():
        results[model] = {}
        intelligence_info = scale["intelligence"]
        intelligence_tier = tier_for_scaled_value(values["intelligence"], intelligence_info, 4, 1)
        results[model]["intelligence"] = {
            "value": values["intelligence"],
            "tier": intelligence_tier,
            "icon": ICONS["intelligence"][intelligence_tier],
            "label": LABELS["intelligence"][intelligence_tier],
        }

        cost_info = scale["cost"]
        cost_tier = 0 if values["cost"] == 0 else tier_for_nonzero_scale(values["cost"], cost_info, 3, 2)
        results[model]["cost"] = {
            "value": values["cost"],
            "tier": cost_tier,
            "icon": ICONS["cost"][cost_tier],
            "label": LABELS["cost"][cost_tier],
        }

        speed_value = values.get("speed")
        speed_info = scale["speed"]
        speed_tier = 0 if speed_value is None else tier_for_nonzero_scale(speed_value, speed_info, 3, 2)
        results[model]["speed"] = {
            "value": speed_value,
            "tier": speed_tier,
            "icon": ICONS["speed"][speed_tier],
            "label": LABELS["speed"][speed_tier],
        }

    return {"scale": scale, "models": results}


def render_json(output):
    return json.dumps(output, indent=2, ensure_ascii=False)


def render_text(output):
    lines = [
        f"{'Model':<22} {'Intelligence':<18} {'Cost ($/1M tok)':<18} {'Speed (t/s)':<18}",
        "-" * 76,
    ]

    for model, result in output["models"].items():
        speed_value = result["speed"]["value"]
        speed_display = f"{speed_value:<4}" if speed_value is not None else "--- "
        lines.append(
            f"{model:<22} "
            f"{result['intelligence']['value']:<4} {result['intelligence']['icon']:<12} "
            f"${result['cost']['value']:<8.2f} {result['cost']['icon']:<10} "
            f"{speed_display:<4} {result['speed']['icon']:<10}"
        )

    lines.append("")
    lines.append(f"Scale calculation for {len(output['models'])} selected models:")
    for dimension, info in output["scale"].items():
        if dimension == "cost_free_count" or dimension == "speed_unknown_count":
            continue
        if info["min"] is None:
            if dimension == "cost":
                lines.append("  Cost            no positive-cost models  free=all")
            elif dimension == "speed":
                lines.append("  Speed           no known-speed models    unknown=all")
            continue

        extra = ""
        if dimension == "cost":
            extra = f"  free={output['scale']['cost_free_count']}"
        elif dimension == "speed":
            extra = f"  unknown={output['scale']['speed_unknown_count']}"
        lines.append(
            f"  {dimension.title():<15} min={info['min']:.2f}  "
            f"max={info['max']:.2f}  range={info['range']:.2f}  "
            f"Q1 < {info['q1_boundary']:.2f}  "
            f"Q2 < {info['q2_boundary']:.2f}  "
            f"Q3 < {info['q3_boundary']:.2f}  "
            f"Q4 >= {info['q3_boundary']:.2f}{extra}"
        )

    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Calculate relative scale indicators for agent models"
    )
    parser.add_argument("--data", required=True, help="JSON file with model data")
    parser.add_argument("--assignments", help="JSON file with agent-to-model mapping")
    parser.add_argument("--models", nargs="*", help="Explicit list of selected model names")
    parser.add_argument("--output", help="Output file (default: stdout)")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text table)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        data = load_json(args.data)
        all_models = data.get("models", data)
        selected = selected_models(all_models, args.assignments, args.models)
        model_data = {model: all_models[model] for model in selected}
        validate_model_data(model_data)
        output = calculate(model_data)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        sys.exit(str(error))

    rendered = render_json(output) if args.format == "json" else render_text(output)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(rendered)
            file.write("\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
