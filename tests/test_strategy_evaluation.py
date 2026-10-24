from stockboard_backend.strategy_evaluation import (
    GateDefinition, IndicatorValue, RuleDefinition, RuleEvaluationResult, StrategyDefinition,
    StrategyThresholds, strategy_evaluation_apply_variant_group_strictest_pass,
    strategy_evaluation_calculate_strategy_score_percent_from_rule_results,
    strategy_evaluation_calculate_unknown_weight_ratio_from_rule_results,
    strategy_evaluation_determine_pass_from_rule_results,
    strategy_evaluation_evaluate_rule_against_indicator_values,
    strategy_evaluation_evaluate_strategy_for_symbol,
)


def build_rule_result(rule_id, status, weight, variant_group=None):
    return RuleEvaluationResult(rule_id, rule_id, status, None, weight, variant_group)


def build_indicator_value_by_id(**value_by_id):
    return {key: IndicatorValue(key, value, "test") for key, value in value_by_id.items()}


def test_rule_operators_and_missing_value():
    rule = RuleDefinition("R1", "d", "x", "between", 3, [1, 2])
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        rule, build_indicator_value_by_id(x=2)).status == "pass"
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        rule, build_indicator_value_by_id(x=2.1)).status == "fail"
    assert strategy_evaluation_evaluate_rule_against_indicator_values(rule, {}).status == "unknown"
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        rule, build_indicator_value_by_id(x=None)).status == "unknown"


def test_score_ignores_unknown_and_not_applicable():
    result_list = [build_rule_result("a", "pass", 4), build_rule_result("b", "fail", 4),
                   build_rule_result("c", "unknown", 5), build_rule_result("d", "not_applicable", 3)]
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(result_list) == 50.0
    assert strategy_evaluation_calculate_unknown_weight_ratio_from_rule_results(result_list) == round(5 / 13, 3)


def test_score_is_none_when_nothing_is_judged():
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(
        [build_rule_result("a", "unknown", 3)]) is None


def test_pass_veto():
    assert strategy_evaluation_determine_pass_from_rule_results(
        [build_rule_result("a", "pass", 5), build_rule_result("b", "fail", 5)]) is False
    assert strategy_evaluation_determine_pass_from_rule_results(
        [build_rule_result("a", "pass", 5), build_rule_result("b", "unknown", 5)]) is None
    assert strategy_evaluation_determine_pass_from_rule_results(
        [build_rule_result("a", "pass", 5), build_rule_result("b", "fail", 4)]) is True


def test_high_score_can_fail_and_low_score_can_pass():
    high_score_list = [build_rule_result("a", "pass", 4), build_rule_result("b", "pass", 4),
                       build_rule_result("c", "fail", 5)]
    low_score_list = [build_rule_result("a", "fail", 4), build_rule_result("b", "fail", 4),
                      build_rule_result("c", "pass", 5)]
    assert strategy_evaluation_determine_pass_from_rule_results(high_score_list) is False
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(high_score_list) > 50
    assert strategy_evaluation_determine_pass_from_rule_results(low_score_list) is True
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(low_score_list) < 50


def test_variant_group_keeps_strictest_pass():
    result_list = strategy_evaluation_apply_variant_group_strictest_pass([
        build_rule_result("loose", "pass", 2, "g"), build_rule_result("strict", "pass", 4, "g"),
        build_rule_result("other", "fail", 3)])
    assert [r.status for r in result_list] == ["not_applicable", "pass", "fail"]


def test_variant_group_keeps_loosest_when_none_pass():
    result_list = strategy_evaluation_apply_variant_group_strictest_pass([
        build_rule_result("loose", "fail", 2, "g"), build_rule_result("strict", "fail", 4, "g")])
    assert [r.status for r in result_list] == ["fail", "not_applicable"]


def test_strategy_evaluation_picks_best_expiration_window():
    contract_gate = GateDefinition("gate_2", "Gate 2", [
        RuleDefinition("B07", "dte", "days", "between", 4, [30, 45])], per_expiration_window=True)
    macro_gate = GateDefinition("gate_0", "Gate 0", [
        RuleDefinition("A22", "no earnings", "clear", "is_true", 5)])
    strategy = StrategyDefinition("s", "S", "t", StrategyThresholds(), [macro_gate, contract_gate])
    result = strategy_evaluation_evaluate_strategy_for_symbol(
        strategy, "AAA", build_indicator_value_by_id(clear=True),
        {"14-30": build_indicator_value_by_id(days=20), "30-45": build_indicator_value_by_id(days=35)})
    contract_result = result.gate_result_list[1]
    assert contract_result.expiration_window_label == "30-45"
    assert len(contract_result.alternative_window_result_list) == 1
    assert result.is_pass is True and result.score_percent == 100.0
