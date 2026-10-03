def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(int(len(sorted_values) * pct), len(sorted_values) - 1)
    return sorted_values[index]
