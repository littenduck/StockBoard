from stockboard_backend.strategy_evaluation import (
    GateDefinition, IndicatorValue, RuleDefinition, RuleEvaluationResult, StrategyDefinition,
    StrategyThresholds, strategy_evaluation_calculate_strategy_score_percent_from_rule_results,
    strategy_evaluation_calculate_unknown_weight_ratio_from_rule_results,
    strategy_evaluation_determine_pass_from_rule_results,
    strategy_evaluation_evaluate_gate_from_indicator_values,
    strategy_evaluation_evaluate_rule_against_indicator_values,
    strategy_evaluation_evaluate_strategy_for_symbol,
)


def build_rule_result(rule_id, status, weight, veto=False, method=None):
    return RuleEvaluationResult(rule_id, rule_id, status, None, weight, veto, method)


def build_rule(rule_id, indicator, operator, weight, value=None, veto=False, method=None):
    return RuleDefinition(rule_id, rule_id, rule_id, indicator, operator, weight, value, veto, method)


def build_indicator_value_by_id(**value_by_id):
    return {key: IndicatorValue(key, value, "test") for key, value in value_by_id.items()}


def test_rule_operators_and_missing_value():
    rule = build_rule("R1", "x", "between", 3, [1, 2])
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        rule, build_indicator_value_by_id(x=2)).status == "pass"
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        rule, build_indicator_value_by_id(x=2.1)).status == "fail"
    assert strategy_evaluation_evaluate_rule_against_indicator_values(rule, {}).status == "unknown"
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        rule, build_indicator_value_by_id(x=None)).status == "unknown"


def test_rule_without_indicator_or_without_a_line_stays_unknown():
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        build_rule("M1", None, None, 3, method="manual"), build_indicator_value_by_id(x=1)).status == "unknown"
    assert strategy_evaluation_evaluate_rule_against_indicator_values(
        build_rule("M2", "x", None, 3), build_indicator_value_by_id(x=1)).status == "unknown"


def test_score_ignores_unknown_and_not_applicable():
    result_list = [build_rule_result("a", "pass", 4), build_rule_result("b", "fail", 4),
                   build_rule_result("c", "unknown", 5), build_rule_result("d", "not_applicable", 3)]
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(result_list) == 50.0
    assert strategy_evaluation_calculate_unknown_weight_ratio_from_rule_results(result_list) == round(5 / 13, 3)


def test_manual_rules_do_not_count_toward_the_unknown_share():
    result_list = [build_rule_result("a", "pass", 4), build_rule_result("m", "unknown", 5, method="manual")]
    assert strategy_evaluation_calculate_unknown_weight_ratio_from_rule_results(result_list) == 0.0
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(result_list) == 100.0


def test_score_is_none_when_nothing_is_judged():
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(
        [build_rule_result("a", "unknown", 3)]) is None


def test_pass_veto():
    assert strategy_evaluation_determine_pass_from_rule_results(
        [build_rule_result("a", "pass", 5, True), build_rule_result("b", "fail", 5, True)]) is False
    assert strategy_evaluation_determine_pass_from_rule_results(
        [build_rule_result("a", "pass", 5, True), build_rule_result("b", "unknown", 5, True)]) is None
    assert strategy_evaluation_determine_pass_from_rule_results(
        [build_rule_result("a", "pass", 5, True), build_rule_result("b", "fail", 4)]) is True


def test_weight_five_without_the_veto_flag_does_not_veto():
    assert strategy_evaluation_determine_pass_from_rule_results([build_rule_result("a", "fail", 5)]) is True


def test_high_score_can_fail_and_low_score_can_pass():
    high_score_list = [build_rule_result("a", "pass", 4), build_rule_result("b", "pass", 4),
                       build_rule_result("c", "fail", 5, True)]
    low_score_list = [build_rule_result("a", "fail", 4), build_rule_result("b", "fail", 4),
                      build_rule_result("c", "pass", 5, True)]
    assert strategy_evaluation_determine_pass_from_rule_results(high_score_list) is False
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(high_score_list) > 50
    assert strategy_evaluation_determine_pass_from_rule_results(low_score_list) is True
    assert strategy_evaluation_calculate_strategy_score_percent_from_rule_results(low_score_list) < 50


def test_nested_tier_lines_give_partial_credit():
    gate = GateDefinition("g", "G", [build_rule("loose", "y", "less_than", 2, 5.0), build_rule("strict", "y", "less_than", 2, 4.5)])

    def score_at(yield_value):
        result = strategy_evaluation_evaluate_gate_from_indicator_values(gate, build_indicator_value_by_id(y=yield_value))
        return strategy_evaluation_calculate_strategy_score_percent_from_rule_results(result.rule_result_list)

    assert (score_at(4.3), score_at(4.7), score_at(5.2)) == (100.0, 50.0, 0.0)


def test_strategy_evaluation_picks_best_expiration_window():
    contract_gate = GateDefinition("gate_2", "Gate 2", [
        build_rule("CTR-02", "days", "between", 4, [30, 45])], per_expiration_window=True)
    macro_gate = GateDefinition("gate_0", "Gate 0", [
        build_rule("EVT-01", "clear", "is_true", 5, veto=True)])
    strategy = StrategyDefinition("s", "S", "t", StrategyThresholds(), [macro_gate, contract_gate])
    result = strategy_evaluation_evaluate_strategy_for_symbol(
        strategy, "AAA", build_indicator_value_by_id(clear=True),
        {"14-30": build_indicator_value_by_id(days=20), "30-45": build_indicator_value_by_id(days=35)})
    contract_result = result.gate_result_list[1]
    assert contract_result.expiration_window_label == "30-45"
    assert len(contract_result.alternative_window_result_list) == 1
    assert result.is_pass is True and result.score_percent == 100.0
