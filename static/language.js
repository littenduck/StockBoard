/* Interface text and bilingual rendering shared by every page. Rules: docs/language.md. */
const UI_TEXT = {
  switch_language: { en:'Switch to Chinese', zh:'切换到英文' },
  loading_data: { en:'Loading data…', zh:'正在获取数据…' },
  strategy: { en:'Strategy', zh:'策略' },
  market: { en:'Market', zh:'市场指标' },
  symbols: { en:'Symbols', zh:'标的' },
  rule_catalog: { en:'Rule catalog', zh:'规则目录' },
  select_symbol: { en:'Select a symbol on the left to see its strategy tree', zh:'选择左侧的标的查看策略树' },
  switch_theme: { en:'Switch light or dark mode', zh:'切换浅色或深色模式' },
  pass: { en:'Pass', zh:'通过' }, fail: { en:'Fail', zh:'未通过' }, veto: { en:'Veto', zh:'否决' },
  unknown: { en:'Unknown', zh:'未知' }, not_applicable: { en:'N/A', zh:'不适用' },
  unavailable: { en:'Unavailable', zh:'获取失败' },
  symbol_summary: { en:'{symbol}, {status}, score {score}', zh:'{symbol}，{status}，分数 {score}' },
  insufficient_data: { en:'Insufficient data', zh:'数据不足' },
  disconnected: { en:'Disconnected, retrying', zh:'连接断开，正在重试' },
  market_closed: { en:'Market closed · Last update {time}', zh:'休市 · 最后更新 {time}' },
  data_stale: { en:'Data is stale · Last update {time}', zh:'数据已过期 · 最后更新 {time}' },
  market_open: { en:'Market open · Updated {age}', zh:'开盘中 · 更新于 {age}' },
  generated_at: { en:'Data generated at {time}', zh:'数据生成于 {time}' },
  just_now: { en:'just now', zh:'刚刚' },
  minutes_ago: { en:'{count} min ago', zh:'{count} 分钟前' },
  hours_ago: { en:'{count} h ago', zh:'{count} 小时前' },
  yes: { en:'Yes', zh:'是' }, no: { en:'No', zh:'否' },
  back_to_list: { en:'↑ List', zh:'↑ 列表' },
  verdict: { en:'Verdict', zh:'结论' }, score: { en:'Score', zh:'分数' },
  missing_weight: { en:'Missing-data weight {percent}% (unknown rules are left out of the score)', zh:'数据缺失权重 {percent}%（未知规则不计入分数）' },
  about_strategy: { en:'About {name}', zh:'{name} 策略说明' },
  close: { en:'Close', zh:'关闭说明' },
  source: { en:'Source: {source}', zh:'来源：{source}' },
  see_all_rules: { en:'See all rules and how IDs work →', zh:'查看全部规则和编号说明 →' },
  best_window: { en:'Expiration {label} days (best) · Gate score {score}', zh:'到期窗口 {label} 天（最佳） · 本层分数 {score}' },
  alternative_window: { en:'Alternative expiration {label} days · Gate score {score}', zh:'备选到期窗口 {label} 天 · 本层分数 {score}' },
  open_rule: { en:'Open {id} in the rule catalog', zh:'在规则目录中查看 {id}' },
  dashboard_title: { en:'StockBoard', zh:'StockBoard' },
  rules_title: { en:'Rule catalog · StockBoard', zh:'规则目录 · StockBoard' },
  back_to_dashboard: { en:'← Back to dashboard', zh:'← 返回看板' },
  rule_summary: { en:'{total} rules · {automatic} automatic · {used} used by strategies', zh:'共 {total} 条规则 · 可自动计算 {automatic} 条 · 被策略使用 {used} 条' },
  id_explanation: { en:'How IDs work: a letter plus two digits. The letter is the group the rule comes from: A to F and Z come from the six strategies and the common layer of the Notion stock option scorecard; T, R and M were added for the stock strategies. One ID means the same rule in every strategy.',
    zh:'编号规则：字母加两位数字。字母表示规则来自哪一组：A 到 F 和 Z 来自 Notion「个股期权评分卡」的六个策略和公共补充层，T、R、M 是后来为股票策略新增的。同一个编号在所有策略里指的是同一条规则。' },
  gap_explanation: { en:'Each strategy uses only the rules it needs that can be computed, so IDs inside one gate are not consecutive. When a loose tier (such as A07, 10Y < 5.0%) comes before a strict tier (such as A02, 10Y < 4.5%), both belong to one variant group and only the strictest passing tier counts.',
    zh:'每个策略只挑选它需要、并且能自动计算的规则，所以策略树里同一层的编号不连续。同一层里如果先出现宽松档（如 A07「10Y < 5.0%」）再出现严格档（如 A02「10Y < 4.5%」），是因为两者属于同一个变体组，只计算通过的最严格那一档。' },
  availability: { en:'Availability', zh:'数据状态' },
  show: { en:'Show', zh:'显示' },
  all_rules: { en:'All rules', zh:'全部规则' },
  used_rules: { en:'Used by a strategy', zh:'已被策略使用的规则' },
  automatic_rules: { en:'Can be computed automatically', zh:'可以自动计算的规则' },
  column_id: { en:'ID', zh:'编号' }, column_rule: { en:'Rule', zh:'说明' }, column_weight: { en:'Weight', zh:'默认权重' },
  column_used_by: { en:'Used by', zh:'使用它的策略' },
  same_as: { en:'Same as {id}', zh:'同 {id}' },
  not_used: { en:'Not used', zh:'未被使用' },
  loading_rules: { en:'Loading rules…', zh:'正在读取规则…' },
  rules_failed: { en:'Could not load rules. Check that the server is running.', zh:'读取规则失败，请确认服务正在运行。' },
  automatic: { en:'Automatic', zh:'自动计算' },
  automatic_explanation: { en:'decided from data the dashboard already fetches', zh:'用看板已经抓取的数据就能判断' },
  missing_data_source: { en:'No data source', zh:'缺少数据源' },
  missing_data_source_explanation: { en:'needs data with no stable free source yet, such as FGI, IV percentile, news, fundamentals', zh:'需要暂时没有稳定免费来源的数据，如 FGI、IV 百分位、新闻、基本面' },
  account_data: { en:'Needs account data', zh:'需要账户数据' },
  account_data_explanation: { en:'needs your brokerage net value, cash, positions or option level', zh:'需要券商账户的净值、现金、持仓或期权权限' },
  user_answer: { en:'Needs your answer', zh:'需要你回答' },
  user_answer_explanation: { en:'only you can answer it, such as whether you would hold the stock long term', zh:'只有你能回答，如是否愿意长期持有' },
  trade_plan: { en:'Trade plan', zh:'交易计划项' },
  trade_plan_explanation: { en:'a plan for after the trade (take profit, stop loss), not a screen', zh:'是下单后的计划（止盈、止损），不是筛选条件' },
  not_implemented: { en:'Not built yet', zh:'尚未实现' },
  not_implemented_explanation: { en:'computable in principle, not built yet', zh:'原则上可以计算，还没有做' },
};
const LANGUAGE_STORAGE_KEY = 'stockboard-language';
let activeLanguage = 'en', hasStoredLanguageChoice = false;

const languageEscape = text => String(text ?? '').replace(/[&<>"]/g, character => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' })[character]);
const languageFill = (localizedText, values = {}) => Object.fromEntries(['en', 'zh'].map(code =>
  [code, localizedText[code].replace(/\{(\w+)\}/g, (match, name) => values[name] ?? match)]));
const languageLocalize = (key, values) => languageFill(UI_TEXT[key], values);
const languageText = (key, values) => languageLocalize(key, values)[activeLanguage];
const languageGetActive = () => activeLanguage;

function languageInitialize(defaultLanguage) {
  let storedChoice = null;
  try { storedChoice = localStorage.getItem(LANGUAGE_STORAGE_KEY); } catch (error) { /* storage blocked: use the default */ }
  hasStoredLanguageChoice = storedChoice === 'en' || storedChoice === 'zh';
  activeLanguage = hasStoredLanguageChoice ? storedChoice : (defaultLanguage === 'zh' ? 'zh' : 'en');
  languageApplyDocument();
}
function languageApplyServerDefault(defaultLanguage, onChange) {
  if (!hasStoredLanguageChoice && (defaultLanguage === 'zh' ? 'zh' : 'en') !== activeLanguage) { activeLanguage = defaultLanguage; languageApplyDocument(); onChange(); }
}
function languageApply(languageCode, onChange) {
  activeLanguage = languageCode; hasStoredLanguageChoice = true;
  try { localStorage.setItem(LANGUAGE_STORAGE_KEY, languageCode); } catch (error) { /* storage blocked: lasts this visit only */ }
  languageApplyDocument();
  onChange();
}
function languageApplyDocument() {
  document.documentElement.lang = activeLanguage === 'zh' ? 'zh-Hans' : 'en';
  if (document.body.dataset.titleKey) document.title = languageText(document.body.dataset.titleKey);
  const languageButton = document.getElementById('language-button');
  if (languageButton) { languageButton.setAttribute('aria-label', languageText('switch_language')); languageButton.title = languageText('switch_language'); }
}
/* In Chinese mode the English goes in <small lang="en">, always on its own line directly under the Chinese. */
function languageRenderText(localizedText) {
  const primary = languageEscape(localizedText[activeLanguage]);
  if (activeLanguage !== 'zh') return primary;
  return `${primary}<small lang="en">${languageEscape(localizedText.en)}</small>`;
}
function languageRenderParagraphs(localizedText) {
  const split = text => text.split(/\n\s*\n/).map(paragraph => paragraph.trim()).filter(Boolean);
  const englishList = split(localizedText.en);
  if (activeLanguage !== 'zh') return englishList.map(paragraph => `<p>${languageEscape(paragraph)}</p>`).join('');
  return split(localizedText.zh).map((paragraph, index) => `<p>${languageEscape(paragraph)}</p>`
    + (englishList[index] ? `<small lang="en">${languageEscape(englishList[index])}</small>` : '')).join('');
}
function languageBindSwitch(onChange) {
  document.getElementById('language-button').onclick = () => languageApply(activeLanguage === 'zh' ? 'en' : 'zh', onChange);
  languageApplyDocument();
}
