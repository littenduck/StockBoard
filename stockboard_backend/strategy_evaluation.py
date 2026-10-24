"""Pure functions that score a strategy against indicator values. No network, no files."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_APPLICABLE = "not_applicable"
VETO_WEIGHT = 5


@dataclass
class IndicatorValue:
    indicator_id: str
    value: Any
    source: str
    change_value: Optional[float] = None
    change_unit: Optional[str] = None  # "percent" or "basis_points"


@dataclass
class RuleDefinition:
    rule_id: str
    description: str
    indicator: str
    operator: str
    weight: int
    value: Any = None
    variant_group: Optional[str] = None


@dataclass
class GateDefinition:
    gate_id: str
    display_name: str
    rule_list: List[RuleDefinition]
    per_expiration_window: bool = False


@dataclass
class StrategyThresholds:
    max_unknown_weight_ratio: float = 0.20


@dataclass
class StrategyDefinition:
    strategy_id: str
    display_name: str
    source: str
    thresholds: StrategyThresholds
    gate_list: List[GateDefinition]


@dataclass
class RuleEvaluationResult:
    rule_id: str
    description: str
    status: str
    measured_value: Any
    weight: int
    variant_group: Optional[str] = None


@dataclass
class GateEvaluationResult:
    gate_id: str
    display_name: str
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
    indicator_value_by_id: Dict[str, IndicatorValue],
) -> RuleEvaluationResult:
    indicator_value = indicator_value_by_id.get(rule_definition.indicator)
    measured_value = None if indicator_value is None else indicator_value.value
    status = STATUS_UNKNOWN
    if measured_value is not None:
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
        description=rule_definition.description,
        status=status,
        measured_value=measured_value,
        weight=rule_definition.weight,
        variant_group=rule_definition.variant_group,
    )


def strategy_evaluation_apply_variant_group_strictest_pass(
    rule_result_list: List[RuleEvaluationResult],
) -> List[RuleEvaluationResult]:
    """Rules in one variant group are listed loose to strict. Keep only the strictest passing one;
    if none pass, keep only the loosest one. The others become not_applicable."""
    member_list_by_group: Dict[str, List[RuleEvaluationResult]] = {}
    for rule_result in rule_result_list:
        if rule_result.variant_group:
            member_list_by_group.setdefault(rule_result.variant_group, []).append(rule_result)
    kept_rule_id_set = set()
    for member_list in member_list_by_group.values():
        passing_list = [member for member in member_list if member.status == STATUS_PASS]
        kept_rule_id_set.add((passing_list[-1] if passing_list else member_list[0]).rule_id)
    adjusted_list = []
    for rule_result in rule_result_list:
        is_dropped = rule_result.variant_group and rule_result.rule_id not in kept_rule_id_set
        adjusted_list.append(
            RuleEvaluationResult(**{**rule_result.__dict__, "status": STATUS_NOT_APPLICABLE})
            if is_dropped else rule_result
        )
    return adjusted_list


def strategy_evaluation_determine_pass_from_rule_results(
    rule_result_list: List[RuleEvaluationResult],
) -> Optional[bool]:
    """Veto: any failed weight 5 rule gives False. All weight 5 rules passing gives True.
    Unknown weight 5 rules with no failure give None."""
    veto_status_list = [r.status for r in rule_result_list
                        if r.weight == VETO_WEIGHT and r.status != STATUS_NOT_APPLICABLE]
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
    counted_weight = sum(r.weight for r in rule_result_list if r.status != STATUS_NOT_APPLICABLE)
    unknown_weight = sum(r.weight for r in rule_result_list if r.status == STATUS_UNKNOWN)
    return 0.0 if counted_weight == 0 else round(unknown_weight / counted_weight, 3)


def strategy_evaluation_evaluate_gate_from_indicator_values(
    gate_definition: GateDefinition,
    indicator_value_by_id: Dict[str, IndicatorValue],
) -> GateEvaluationResult:
    rule_result_list = strategy_evaluation_apply_variant_group_strictest_pass([
        strategy_evaluation_evaluate_rule_against_indicator_values(rule, indicator_value_by_id)
        for rule in gate_definition.rule_list
    ])
    return GateEvaluationResult(
        gate_id=gate_definition.gate_id,
        display_name=gate_definition.display_name,
        is_pass=strategy_evaluation_determine_pass_from_rule_results(rule_result_list),
        rule_result_list=rule_result_list,
    )


def strategy_evaluation_evaluate_contract_gate_for_best_expiration_window(
    gate_definition: GateDefinition,
    shared_indicator_value_by_id: Dict[str, IndicatorValue],
    option_indicator_value_by_window_label: Dict[str, Dict[str, IndicatorValue]],
) -> GateEvaluationResult:
    """Evaluate the gate once per expiration window. The best scoring window is the result;
    the others are kept in alternative_window_result_list."""
    window_result_list = []
    for window_label, option_indicator_value_by_id in option_indicator_value_by_window_label.items():
        window_result = strategy_evaluation_evaluate_gate_from_indicator_values(
            gate_definition, {**shared_indicator_value_by_id, **option_indicator_value_by_id})
        window_result.expiration_window_label = window_label
        window_result_list.append(window_result)
    if not window_result_list:
        empty_result = strategy_evaluation_evaluate_gate_from_indicator_values(
            gate_definition, shared_indicator_value_by_id)
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
    shared_indicator_value_by_id: Dict[str, IndicatorValue],
    option_indicator_value_by_window_label: Dict[str, Dict[str, IndicatorValue]],
) -> StrategyEvaluationResult:
    gate_result_list = []
    for gate_definition in strategy_definition.gate_list:
        if gate_definition.per_expiration_window:
            gate_result = strategy_evaluation_evaluate_contract_gate_for_best_expiration_window(
                gate_definition, shared_indicator_value_by_id, option_indicator_value_by_window_label)
        else:
            gate_result = strategy_evaluation_evaluate_gate_from_indicator_values(
                gate_definition, shared_indicator_value_by_id)
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
