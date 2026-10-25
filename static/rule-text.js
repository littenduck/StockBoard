/* The text about a rule's indicator, shared by the rule catalog page and the hover card: what it measures and every line of that measure. */
function ruleTextRenderIndicator(rule, canLink) {
  if (!rule.indicator_description) return '';
  const lineText = rule.indicator_line_list.map(item =>
    `${canLink ? `<a href="#rule-${item.rule_id}">${item.rule_id}</a>` : item.rule_id} ${languageEscape(item.line)}`).join(' · ');
  return `<small>${languageRenderText(rule.indicator_description)}</small><small>${languageEscape(languageText('indicator_lines', { id:rule.indicator_id }))}: ${lineText}</small>`;
}

/* The fields of a rule as the rule catalog page lists them, in the order of config/rules.yaml. */
const RULE_TEXT_FIELD_LIST = ['indicator', 'operator', 'value', 'band_of', 'method', 'quantifiable', 'status', 'backtestable', 'history_source', 'history_start',
  'fetch_every', 'max_age', 'legacy_id'];
const RULE_TEXT_DASH = '<p class="muted">—</p>';
function ruleTextRenderFieldValue(rule, name, colorByStatus) {
  const value = rule[name];
  if (value == null || value === '') return RULE_TEXT_DASH;
  if (name === 'band_of') return `<p><a href="#rule-${value}">${languageEscape(value)}</a></p>`;
  return `<p${name === 'status' ? ` class="${colorByStatus[value]}"` : ''}>${languageEscape(Array.isArray(value) ? value.join(', ') : String(value)).replace(/([_:+])/g, '$1<wbr>')}</p>`;
}
