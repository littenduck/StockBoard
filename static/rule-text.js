/* The text about a rule's indicator, shared by the rule catalog page and the hover card: what it measures and every line of that measure. */
function ruleTextRenderIndicator(rule, canLink) {
  if (!rule.indicator_description) return '';
  const lineText = rule.indicator_line_list.map(item =>
    `${canLink ? `<a href="#rule-${item.rule_id}">${item.rule_id}</a>` : item.rule_id} ${languageEscape(item.line[languageGetActive()])}`).join(' · ');
  return `<small>${languageRenderText(rule.indicator_description)}</small><small>${languageEscape(languageText('indicator_lines', { id:rule.indicator_id }))}: ${lineText}</small>`;
}
