/* Filter the symbol list by asset type. The company numbers exist only for stocks, so an ETF shows a dash in the stock strategies. */
const ASSET_FILTER_TEXT = { all:{ en:'All', zh:'全部' }, stock:{ en:'Stocks', zh:'股票' }, etf:{ en:'ETFs', zh:'ETF' } };
const assetFilter = document.getElementById('asset-filter');
assetFilter.innerHTML = Object.keys(ASSET_FILTER_TEXT).map(key => `<option value="${key}">${ASSET_FILTER_TEXT[key][languageGetActive()]}</option>`).join('');

function assetFilterCards(cardList) {
  return assetFilter.value === 'all' ? cardList : cardList.filter(card => card.asset_type === assetFilter.value);
}

assetFilter.onchange = () => renderSymbolList(assetFilterCards(latestSnapshot.symbol_card_list), latestSnapshot.failed_symbol_list);
