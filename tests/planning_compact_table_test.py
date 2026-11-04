"""Unchanged source-grounded monthly geometry/value oracles, isolated from the original runner."""
import re
PRIMARY_LABELS=['Saldo inicial','Resultado','Saque','Aporte','Finalizado']
DETAIL_LABELS=['Pago no mês','Câmbio utilizado','Preço médio dos aportes','Última cotação disponível','Variação cambial','Cobertura','situação']
def monthly_geometry(page):
    """The wrapper width, not the viewport/layout name, selects the contract."""
    grid = page.locator('#planning [data-pl-monthly-grid]')
    assert grid.count() == 1, 'one monthly table must remain available'
    data = grid.evaluate('''table=>{
      const viewport=table.closest('[data-pl-monthly-viewport]')||table.parentElement,
        shell=table.closest('.pl-shell'),root=table.closest('[data-pl-monthly-layout]'),
        visible=el=>!!el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden',
        rect=el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width};},
        headers=[...table.querySelectorAll('thead th')].filter(visible),
        rows=[...table.querySelectorAll('[data-pl-grid-month]')];
      return {width:viewport.clientWidth,viewport:innerWidth,mode:root?.dataset.plMonthlyLayout,
        wrapper:rect(viewport),table:rect(table),client:viewport.clientWidth,scroll:viewport.scrollWidth,
        shell:{client:shell.clientWidth,scroll:shell.scrollWidth},
        headers:headers.map(el=>el.textContent.trim()),
        rows:rows.map(el=>({month:el.dataset.plGridMonth,cells:[...el.children].filter(visible).length})),
        truncated:[...table.querySelectorAll('td,th,button,input,select,[data-pl-month-details] *')]
          .filter(visible).filter(el=>getComputedStyle(el).textOverflow==='ellipsis'||
            el.scrollWidth>el.clientWidth+1&&['hidden','clip'].includes(getComputedStyle(el).overflowX))
          .map(el=>({text:el.textContent.trim().slice(0,90),tag:el.tagName})),
        details:[...table.querySelectorAll('[data-pl-month-details]')].filter(visible)
          .map(el=>({box:rect(el),client:el.clientWidth,scroll:el.scrollWidth}))};
    }''')
    expected = 7 if data['width'] >= 900 else 3
    assert len(data['headers']) == expected, ('monthly visible columns', expected, data)
    assert data['mode'] == ('wide' if expected == 7 else 'compact'), ('monthly mode follows useful width', data)
    expected_names = ['Mês', 'Saldo inicial', 'Resultado', 'Saque', 'Aporte', 'Patrimônio', 'Finalizado'] if expected == 7 else ['Mês', 'Resultado', 'Patrimônio']
    assert all(name in actual for name, actual in zip(expected_names, data['headers'])), ('approved header order', data)
    assert len(data['rows']) == 120 and len({r['month'] for r in data['rows']}) == 120, ('exactly120distinctmonths', data)
    assert all(r['cells'] == expected for r in data['rows']), ('row/header alignment', data)
    assert data['scroll'] <= data['client'] + 1, ('monthly horizontal overflow', data)
    assert data['table']['width'] <= data['wrapper']['width'] + 1, ('wide table hidden by overflow CSS', data)
    assert data['shell']['scroll'] <= data['shell']['client'] + 1, ('monthly shell horizontal overflow', data)
    assert data['wrapper']['left'] >= -.25 and data['wrapper']['right'] <= data['viewport'] + .25, ('monthly wrapper escapes viewport', data)
    assert not data['truncated'], ('financial content ellipsized/clipped', data['truncated'])
    assert len(data['details']) <= 1, ('multiple month details visible', data['details'])
    for detail in data['details']:
        assert detail['scroll'] <= detail['client'] + 1, ('detail horizontal overflow', detail)
    return data

def open_details(page, month, keyboard=False, touch=False):
    trigger = page.locator('#planning [data-pl-select-month="' + month + '"]')
    assert trigger.count() == 1, ('one month details trigger', month)
    if trigger.get_attribute('aria-expanded') != 'true':
        if keyboard:
            trigger.focus()
            page.keyboard.press('Enter')
        elif touch:
            trigger.tap()
        else:
            trigger.click()
    details = page.locator('#planning [data-pl-month-details="' + month + '"]')
    assert details.count() == 1 and details.is_visible(), ('month inline details available', month)
    assert trigger.get_attribute('aria-expanded') == 'true', ('trigger exposes expansion', month)
    assert details.get_attribute('id') and trigger.get_attribute('aria-controls') == details.get_attribute('id'), ('accessible details relationship', month)
    visible = page.locator('#planning [data-pl-month-details]:visible')
    assert visible.count() == 1, ('one expanded month', month, visible.count())
    return details

def future_input_values(page, row):
    today = page.evaluate("new Date().getFullYear()+'-'+String(new Date().getMonth()+1).padStart(2,'0')")
    if row['month'] <= today:
        return None
    # Formatting only: preserve the read-model distinction between blank and0.
    expected = page.evaluate('''r=>({
      rate:r.provisional?'':Number.isFinite(r.rate)?String(r.rate*100):'',
      contributionUsd:r.contributionBlank?'':Number.isFinite(r.contributionUsd)?String(r.contributionUsd):''
    })''', row)
    observed = {}
    for field, value in expected.items():
        control = page.locator('[data-pl-inline-month="' + row['month'] + '"][data-pl-inline-open=' + field + ']')
        assert control.count() == 1 and control.is_visible(), ('accessible unique future cell', row['month'], field)
        actual = control.get_attribute('data-pl-premise-value')
        assert actual == value, ('future cell preserves read-model value including blank/zero', row['month'], field, value, actual)
        displayed = control.locator('[data-pl-month-value=rate]').inner_text() if field == 'rate' else control.inner_text()
        expected_display = page.evaluate("([r,f])=>f==='rate'?(r.provisional?'—':(r.rate*100).toLocaleString('pt-BR',{maximumFractionDigits:2})+'%'):(r.contributionBlank?'—':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'USD'}).format(r.contributionUsd))", [row, field])
        assert normalized(displayed) == normalized(expected_display), ('readonly future cell displays the correct model value', row['month'], field, displayed, expected_display)
        observed[field] = {'expected': value, 'actual': actual, 'displayed': displayed}
    return observed

def normalized(text):
    return ' '.join(str(text).replace('\u00a0', ' ').split())

def bound_value(locator, field, expected, identity, strip_rate_label=False):
    """Check a value in its own actual container; equal values elsewhere cannot pass."""
    observed = locator.evaluate_all('''(els,stripRateLabel)=>els.map(el=>{
      if(!stripRateLabel)return el.innerText;
      const copy=el.cloneNode(true);copy.querySelectorAll('.pl-rate-label').forEach(n=>n.remove());return copy.textContent;
    })''', strip_rate_label)
    assert len(observed) == 1 and locator.is_visible(), ('one accessible value container', identity, field, len(observed))
    actual = observed[0]
    candidates = expected if isinstance(expected, list) else [expected]
    assert normalized(actual) in [normalized(value) for value in candidates], ('value in its named container', identity, field, candidates, actual)
    return {'expected': candidates, 'actual': actual}

def detail_field(details, label):
    term = details.locator('.pl-month-extra-details dt').filter(has_text=re.compile(r'^\s*' + re.escape(label) + r'\s*$'))
    assert term.count() == 1, ('one named detail field', label, term.count())
    return term.locator('..').locator(':scope > dd')

def month_field_values(page, row, principal, details, mode, expected, future_values):
    identity = row['month']
    values = {}
    scopes = '[data-pl-grid-month="' + identity + '"] [data-pl-month-value="{key}"],[data-pl-month-details="' + identity + '"] [data-pl-month-value="{key}"]'
    for key, model_key in [('open', 'openUsd'), ('withdrawal', 'withdrawalUsd')]:
        values[model_key] = bound_value(page.locator(scopes.format(key=key)), model_key, expected[model_key], identity)
    if future_values is None:
        values['rate'] = bound_value(page.locator(scopes.format(key='rate')), 'rate', expected['rate'], identity, strip_rate_label=True)
        values['contributionUsd'] = bound_value(page.locator(scopes.format(key='contribution')), 'contributionUsd', expected['contributionUsd'], identity)
    finalized = page.locator('[data-pl-finalized-month="' + identity + '"]')
    assert finalized.count() == 1 and finalized.is_visible(), ('one accessible finalization control', identity)
    assert finalized.input_value() == ('Sim' if row['finalized'] else 'Não'), ('finalization control value', identity)
    cells = principal.locator(':scope > th,:scope > td')
    result_index, balance_index = (2, 5) if mode == 'wide' else (1, 2)
    for index, usd_key, brl_key in [(result_index, 'resultUsd', 'resultBrl'), (balance_index, 'closeUsd', 'closeBrl')]:
        values[usd_key] = bound_value(cells.nth(index).locator('.pl-money-primary'), usd_key, expected[usd_key], identity)
        values[brl_key] = bound_value(cells.nth(index).locator('.pl-money-secondary'), brl_key, expected[brl_key], identity)
    labels = {'paidBrl': 'Pago no mês', 'fxVariation': 'Variação cambial',
              'costCoverage': 'Cobertura', 'costStatus': 'Situação do custo'}
    for key, label in labels.items():
        wanted = expected[key]
        if wanted == '—':
            wanted = ['—', '— · Indisponível']
        values[key] = bound_value(detail_field(details, label), key, wanted, identity)
    for key, label in [('fxRate', 'Câmbio utilizado · R$/US$'),
                       ('averageRate', 'Preço médio dos aportes · R$/US$'),
                       ('quoteRate', 'Última cotação disponível · R$/US$')]:
        wanted = page.evaluate('''value=>Number.isFinite(value)?[
          value.toLocaleString('pt-BR',{minimumFractionDigits:4,maximumFractionDigits:4}),
          value.toLocaleString('pt-BR',{maximumFractionDigits:4}),
          new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value)]:['—','— · Indisponível']''', row[key])
        values[key] = bound_value(detail_field(details, label), key, wanted, identity)
    return values

def detail_values(page, row):
    details = open_details(page, row['month'])
    principal = page.locator('[data-pl-grid-month="' + row['month'] + '"]')
    mode = principal.evaluate('el=>el.closest("[data-pl-monthly-layout]")?.dataset.plMonthlyLayout')
    assert mode in ['wide', 'compact'], ('month detail has an explicit layout mode', row['month'], mode)
    labels = details.inner_text()
    # FX/cost references belong in details in both modes. Wide primary labels
    # may stay in the table; compact details must expose the removed fields.
    primary_labels = labels if mode == 'compact' else ' '.join([
        page.locator('[data-pl-monthly-grid] thead').inner_text(), principal.inner_text(), labels])
    for label in PRIMARY_LABELS:
        assert label.casefold() in primary_labels.casefold(), ('accessible primary month label', row['month'], mode, label, primary_labels)
    for label in DETAIL_LABELS:
        assert label.casefold() in labels.casefold(), ('complete accessible month detail label', row['month'], label, labels)
    future_values = future_input_values(page, row)
    # Currency/percentage formatting only. All values are taken from the read-model.
    expected = page.evaluate('''r=>{
      const money=(v,c='USD')=>Number.isFinite(v)?new Intl.NumberFormat('pt-BR',{style:'currency',currency:c}).format(v):'—',
        percent=v=>Number.isFinite(v)?(v*100).toLocaleString('pt-BR',{maximumFractionDigits:2})+'%':'—';
      return {openUsd:money(r.openUsd),resultUsd:money(r.resultUsd),resultBrl:money(r.resultBrl,'BRL'),
        withdrawalUsd:money(r.withdrawalUsd),contributionUsd:money(r.contributionUsd),closeUsd:money(r.closeUsd),
        closeBrl:money(r.closeBrl,'BRL'),paidBrl:money(r.paidBrl,'BRL'),fxVariation:percent(r.fxVariation),
        rate:percent(r.rate),costCoverage:percent(r.costCoverage),costStatus:r.costStatus};
    }''', row)
    normalize = lambda s: ' '.join(str(s).replace('\u00a0', ' ').split())
    # The union includes principal values; compact details supply removed fields.
    text = normalize(principal.inner_text() + ' ' + labels)
    for key, value in expected.items():
        if key in ['rate', 'contributionUsd'] and future_values is not None:
            continue  # Every future row was checked against its actual inputs.
        assert normalize(value) in text, ('read-model value preserved in principal/detail', row['month'], key, value, text)
    for key in ['fxRate', 'averageRate', 'quoteRate']:
        candidates = page.evaluate('''value=>Number.isFinite(value)?[
          value.toLocaleString('pt-BR',{minimumFractionDigits:4,maximumFractionDigits:4}),
          value.toLocaleString('pt-BR',{maximumFractionDigits:4}),
          new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value)]:['—']''', row[key])
        assert any(normalize(value) in text for value in candidates), ('exchange reference value preserved', row['month'], key, candidates, text)
    control = details.locator('[data-pl-finalized-month="' + row['month'] + '"]')
    if control.count():
        assert control.input_value() == ('Sim' if row['finalized'] else 'Não'), ('finalization value', row['month'])
    bound = month_field_values(page, row, principal, details, mode, expected, future_values)
    return {'month': row['month'], 'mode': mode, 'labels': PRIMARY_LABELS + DETAIL_LABELS,
            'read_model_values': expected, 'future_input_values': future_values, 'bound_fields': bound}
