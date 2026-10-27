"""Pure functions that score a strategy against indicator values. No network, no files."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from stock_benchmark_backend.localized_text import LocalizedText

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_APPLICABLE = "not_applicable"


@dataclass
class IndicatorValue:
    indicator_name: str
    value: Any
    source: str
    change_value: Optional[float] = None
    change_unit: Optional[str] = None  # "percent" or "basis_points"
    observed_at: Optional[float] = None  # epoch seconds of the observation; a value older than the indicator's max_age is dropped


@dataclass
class RuleDefinition:
    rule_id: str
    rule_name: str
    description: LocalizedText
    indicator: Optional[str]
    operator: Optional[str]
    weight: int
    value: Any = None
    veto: bool = False
    method: Optional[str] = None
    status: Optional[str] = None
    unit: str = ""  # the unit of the indicator it tests (%, USD ...), shown next to the measured value


@dataclass
class GateDefinition:
    gate_id: str
    display_name: LocalizedText
    rule_list: List[RuleDefinition]
    per_expiration_window: bool = False


@dataclass
class StrategyThresholds:
    max_unknown_weight_ratio: float = 0.20


@dataclass
class StrategyDefinition:
    strategy_id: str
    display_name: LocalizedText
    source: LocalizedText
    thresholds: StrategyThresholds
    gate_list: List[GateDefinition]
    summary: Optional[LocalizedText] = None
    help_text: Optional[LocalizedText] = None
    # Asset types the strategy applies to (stock, etf, other). None means every type. For the others the page shows a dash.
    asset_type_list: Optional[List[str]] = None


@dataclass
class RuleEvaluationResult:
    rule_id: str
    rule_name: str
    status: str
    measured_value: Any
    weight: int
    veto: bool = False
    method: Optional[str] = None
    unit: str = ""


@dataclass
class GateEvaluationResult:
    gate_id: str
    display_name: LocalizedText
    is_pass: Optional[bool]
    rule_result_list: List[RuleEvaluationResult]
    expiration_window_label: Optional[str] = None
    alternative_window_result_list: List["GateEvaluationResult"] = field(default_factory=list)


@dataclass
class StrategyEvaluationResult:
    strategy_id: str
    symbol: str
    is_pass: Optional[bool]
    score_percent: Optional[float]
    unknown_weight_ratio: float
    gate_result_list: List[GateEvaluationResult]


def strategy_evaluation_evaluate_rule_against_indicator_values(
    rule_definition: RuleDefinition,
    indicator_value_by_name: Dict[str, IndicatorValue],
) -> RuleEvaluationResult:
    indicator_value = indicator_value_by_name.get(rule_definition.indicator) if rule_definition.indicator else None
    measured_value = None if indicator_value is None else indicator_value.value
    status = STATUS_UNKNOWN
    # A rule without an indicator or without a line to test (a manual rule, a rule not built yet) stays unknown.
    if measured_value is not None and rule_definition.operator is not None:
        operator, threshold = rule_definition.operator, rule_definition.value
        if operator == "less_than":
            is_satisfied = measured_value < threshold
        elif operator == "less_or_equal":
            is_satisfied = measured_value <= threshold
        elif operator == "greater_than":
            is_satisfied = measured_value > threshold
        elif operator == "greater_or_equal":
            is_satisfied = measured_value >= threshold
        elif operator == "between":
            is_satisfied = threshold[0] <= measured_value <= threshold[1]
        elif operator == "is_true":
            is_satisfied = bool(measured_value)
        else:
            raise ValueError("Unknown operator: " + operator)
        status = STATUS_PASS if is_satisfied else STATUS_FAIL
    return RuleEvaluationResult(
        rule_id=rule_definition.rule_id,
        rule_name=rule_definition.rule_name,
        status=status,
        measured_value=measured_value,
        weight=rule_definition.weight,
        veto=rule_definition.veto,
        method=rule_definition.method,
        unit=rule_definition.unit,
    )


def strategy_evaluation_determine_pass_from_rule_results(
    rule_result_list: List[RuleEvaluationResult],
) -> Optional[bool]:
    """Veto: any failed rule marked veto gives False. All veto rules passing gives True.
    Unknown veto rules with no failure give None."""
    veto_status_list = [r.status for r in rule_result_list if r.veto and r.status != STATUS_NOT_APPLICABLE]
    if STATUS_FAIL in veto_status_list:
        return False
    if STATUS_UNKNOWN in veto_status_list:
        return None
    return True


def strategy_evaluation_calculate_strategy_score_percent_from_rule_results(
    rule_result_list: List[RuleEvaluationResult],
) -> Optional[float]:
    passed_weight = sum(r.weight for r in rule_result_list if r.status == STATUS_PASS)
    judged_weight = sum(r.weight for r in rule_result_list if r.status in (STATUS_PASS, STATUS_FAIL))
    return None if judged_weight == 0 else round(passed_weight / judged_weight * 100, 1)


def strategy_evaluation_calculate_unknown_weight_ratio_from_rule_results(
    rule_result_list: List[RuleEvaluationResult],
) -> float:
    """Manual rules are always unknown, so they are left out; otherwise one manual rule would grey every score."""
    counted_list = [r for r in rule_result_list if r.status != STATUS_NOT_APPLICABLE and r.method != "manual"]
    counted_weight = sum(r.weight for r in counted_list)
    unknown_weight = sum(r.weight for r in counted_list if r.status == STATUS_UNKNOWN)
    return 0.0 if counted_weight == 0 else round(unknown_weight / counted_weight, 3)


def strategy_evaluation_evaluate_gate_from_indicator_values(
    gate_definition: GateDefinition,
    indicator_value_by_name: Dict[str, IndicatorValue],
) -> GateEvaluationResult:
    rule_result_list = [
        strategy_evaluation_evaluate_rule_against_indicator_values(rule, indicator_value_by_name)
        for rule in gate_definition.rule_list
    ]
    return GateEvaluationResult(
        gate_id=gate_definition.gate_id,
        display_name=gate_definition.display_name,
        is_pass=strategy_evaluation_determine_pass_from_rule_results(rule_result_list),
        rule_result_list=rule_result_list,
    )


def strategy_evaluation_evaluate_contract_gate_for_best_expiration_window(
    gate_definition: GateDefinition,
    shared_indicator_value_by_name: Dict[str, IndicatorValue],
    option_indicator_value_by_window_label: Dict[str, Dict[str, IndicatorValue]],
) -> GateEvaluationResult:
    """Evaluate the gate once per expiration window. The best scoring window is the result;
    the others are kept in alternative_window_result_list."""
    window_result_list = []
    for window_label, option_indicator_value_by_name in option_indicator_value_by_window_label.items():
        window_result = strategy_evaluation_evaluate_gate_from_indicator_values(
            gate_definition, {**shared_indicator_value_by_name, **option_indicator_value_by_name})
        window_result.expiration_window_label = window_label
        window_result_list.append(window_result)
    if not window_result_list:
        empty_result = strategy_evaluation_evaluate_gate_from_indicator_values(
            gate_definition, shared_indicator_value_by_name)
        empty_result.expiration_window_label = None
        return empty_result

    def score_of(window_result: GateEvaluationResult) -> float:
        score = strategy_evaluation_calculate_strategy_score_percent_from_rule_results(
            window_result.rule_result_list)
        return -1.0 if score is None else score

    best_result = max(window_result_list, key=score_of)
    best_result.alternative_window_result_list = [r for r in window_result_list if r is not best_result]
    return best_result


def strategy_evaluation_evaluate_strategy_for_symbol(
    strategy_definition: StrategyDefinition,
    symbol: str,
    shared_indicator_value_by_name: Dict[str, IndicatorValue],
    option_indicator_value_by_window_label: Dict[str, Dict[str, IndicatorValue]],
) -> StrategyEvaluationResult:
    gate_result_list = []
    for gate_definition in strategy_definition.gate_list:
        if gate_definition.per_expiration_window:
            gate_result = strategy_evaluation_evaluate_contract_gate_for_best_expiration_window(
                gate_definition, shared_indicator_value_by_name, option_indicator_value_by_window_label)
        else:
            gate_result = strategy_evaluation_evaluate_gate_from_indicator_values(
                gate_definition, shared_indicator_value_by_name)
        gate_result_list.append(gate_result)
    all_rule_result_list = [r for gate in gate_result_list for r in gate.rule_result_list]
    return StrategyEvaluationResult(
        strategy_id=strategy_definition.strategy_id,
        symbol=symbol,
        is_pass=strategy_evaluation_determine_pass_from_rule_results(all_rule_result_list),
        score_percent=strategy_evaluation_calculate_strategy_score_percent_from_rule_results(all_rule_result_list),
        unknown_weight_ratio=strategy_evaluation_calculate_unknown_weight_ratio_from_rule_results(all_rule_result_list),
        gate_result_list=gate_result_list,
    )
