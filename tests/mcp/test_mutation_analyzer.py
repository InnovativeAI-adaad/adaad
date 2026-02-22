from runtime.mcp.mutation_analyzer import analyze_mutation


def test_analyzer_determinism_and_fields():
    payload = {"ops": [{"op": "replace", "value": "safe"}]}
    a = analyze_mutation(payload)
    b = analyze_mutation(payload)
    assert a == b
    assert 0.0 <= a["predicted_fitness_score"] <= 1.0
    assert set(a["component_scores"].keys()) == {
        "constitutional_compliance",
        "stability_heuristics",
        "performance_delta",
        "resource_efficiency",
        "lineage_distance",
    }
    assert "recommendation" in a


def test_risk_tiers_ranges():
    low = analyze_mutation({"ops": [], "constitutional_compliance": 1.0, "stability_heuristics": 1.0, "performance_delta": 1.0, "resource_efficiency": 1.0, "lineage_distance": 1.0})
    assert low["risk_tier"] in {"low", "medium", "high"}
