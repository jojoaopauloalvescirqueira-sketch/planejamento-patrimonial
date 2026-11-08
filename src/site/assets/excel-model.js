(function (root) {
  'use strict';
  const app = root.JPWPlanning;
  const usd = label => [label + ' · US$', 'usd'];
  const brl = label => [label + ' · R$', 'brl'];
  const rate = label => [label + ' · %', 'rate'];
  const month = label => [label, 'month'];
  const date = label => [label, 'date'];
  const integer = label => [label, 'integer'];
  const fx = ['Câmbio · R$/US$', 'fx'];
  const keys = ['Conta', 'ID da conta', 'ID do plano'];
  const status = {
    CONFIRMED: 'Confirmado', PARTIAL: 'Parcial', PROJECTED: 'Projetado',
    WAITING_CLOSURE: 'Aguardando fechamento', INVALID: 'Cálculo indisponível',
    ACHIEVED: 'Atingida', PENDING_DATA: 'Aguardando dados', NOT_REACHED: 'Fora do horizonte',
    NOT_INFORMED: 'Não informada',
  };
  const table = (name, headers) => ({name, headers, rows: []});
  const closed = (row, through) => through ? row : null;
  function detailTables(prefix = '') {
    return {
      monthly: table(prefix + 'Mensal', [...keys, month('Mês'), 'Situação dos registros', 'Base do patrimônio', usd('Abertura'),
        usd('Resultado'), rate('Resultado'), usd('Saque'), usd('Aporte'), usd('Patrimônio'), brl('Patrimônio'),
        fx, 'Fonte do câmbio', date('Data da cotação'), month('Mês pendente'), 'Motivo / observação']),
      movements: table(prefix + 'Lançamentos', [...keys, month('Mês'), 'Tipo', 'Situação', 'ID do registro',
        integer('Revisão'), date('Data do registro (UTC)'), usd('Valor'), brl('Valor'), 'Motivo registrado']),
      closures: table(prefix + 'Fechamentos', [...keys, 'Tipo', month('Início do período'), month('Fim do período'), 'Situação',
        integer('Revisão'), date('Confirmação (UTC)'), date('Reabertura (UTC)'), 'Responsável', 'Declaração',
        'Motivo da reabertura', usd('Abertura registrada'), usd('Resultado registrado'), usd('Aporte registrado'),
        usd('Saque registrado'), usd('Patrimônio registrado'), fx, 'Fonte do câmbio', date('Data da cotação')]),
      accounts: table(prefix + 'Contas e metas', [...keys, 'Situação do plano', month('Início'), month('Fim'), usd('Capital inicial'),
        'Perfil', rate('Taxa do perfil'), usd('Aporte previsto por mês'), month('Parada de aportes'), 'Meta',
        usd('Renda informada'), brl('Renda informada'), usd('Renda equivalente'), usd('Patrimônio necessário'),
        'Situação da meta', month('Prazo atualizado'), month('Prazo original'), integer('Meses restantes'), fx,
        'Fonte do câmbio da meta', date('Data do câmbio da meta'), date('Arquivamento (UTC)')]),
      projections: table(prefix + 'Projeções', [...keys, month('Mês'), usd('Patrimônio original'), usd('Aporte original'),
        usd('Resultado original'), rate('Taxa original'), usd('Patrimônio atualizado'), usd('Resultado atualizado'),
        usd('Aporte previsto atualizado'), rate('Taxa atualizada'), 'Base atualizada', month('Mês pendente'), 'Motivo / observação']),
    };
  }

  function quoteFields(q) {
    return Number.isFinite(q?.rate) && q.rate > 0
      ? [q.rate, q.source ?? null, q.referenceDate ?? null] : [null, null, null];
  }

  function addDetails(t, a, model, options, archive) {
    const p = a.plan;
    const who = [a.name, a.id, p.id];
    const reference = new Map(model.referenceRows.map(r => [r.month, r]));
    for (const r of model.rows) {
      const actual = r.month <= options.month;
      const inputs = app.monthlyInputs.status(p, r.month);
      const q = r.finalized && p.closures[r.month]?.fxQuote || (r.month < options.month ? options.historicalQuotes?.[r.month] : options.quote);
      const [fxRate, fxSource, fxDate] = r.fxRate === q?.rate ? quoteFields(q) : [r.fxRate, null, null];
      const missing = actual && !r.finalized && [
        !inputs.result && 'resultado', !inputs.withdrawal && 'saque', !inputs.contribution && 'aporte',
      ].filter(Boolean).join(', ');
      const reason = [
        r.blockingMonth && 'Saldo dependente do fechamento anterior',
        r.provisional && 'Taxa prevista não informada',
        r.issues?.join(' · '),
        missing && 'A preencher: ' + missing,
        r.closeUsd !== null && r.closeBrl === null && 'Conversão indisponível',
      ].filter(Boolean).join(' · ');
      t.monthly.rows.push([...who, r.month, r.finalized ? 'Finalizado' : actual ? 'Em aberto' : 'Projeção',
        status[r.balanceStatus] ?? null, r.openUsd, r.resultUsd, actual && !(r.openUsd > 0) ? null : r.rate,
        actual && !inputs.withdrawal && !r.finalized ? null : r.withdrawalUsd,
        actual && !inputs.contribution && !r.finalized ? null : r.contributionUsd,
        r.closeUsd, r.closeBrl, fxRate, fxSource, fxDate, r.blockingMonth, reason || null]);
      const ref = reference.get(r.month);
      t.projections.rows.push([...who, r.month, ref?.closeUsd, ref?.contributionUsd, ref?.resultUsd, ref?.rate,
        r.closeUsd, r.resultUsd, r.plannedContributionUsd, actual && !(r.openUsd > 0) ? null : r.rate,
        status[r.balanceStatus] ?? null, r.blockingMonth,
        [!ref && 'Referência original indisponível', reason].filter(Boolean).join(' · ') || null]);
    }

    const flows = [];
    const reasons = new Map();
    for (const event of p.history ?? []) {
      if (!event.reason) continue;
      const after = event.after;
      const key = after?.id ?? after?.month;
      const revision = after?.revision ?? after?.value?.revision;
      if (key && revision) reasons.set(key + '/' + revision, event.reason);
    }
    function addFlow(kind, item, atMonth, noMovement = false, eventStatus = null) {
      for (let v = item, current = true; v; v = v.previous, current = false) {
        flows.push([...who, atMonth, kind,
          eventStatus ?? (current ? noMovement ? 'Ausência confirmada' : kind !== 'Resultado' && v.usd === 0 ? 'Anulado' : 'Vigente' : 'Revisão anterior'),
          v.id ?? null, v.revision, v.recordedAt ?? v.confirmedAt, noMovement ? null : v.usd,
          noMovement ? null : v.brl, reasons.get((v.id ?? atMonth) + '/' + v.revision) ?? null]);
      }
    }
    for (const [key, v] of Object.entries(p.results ?? {})) addFlow('Resultado', v, key);
    for (const v of p.contributions ?? []) addFlow('Aporte', v, v.month);
    for (const v of p.withdrawals ?? []) addFlow('Saque', v, v.month);
    // Absences have no linked revision chain. Their history also captures superseded confirmations.
    const absences = p.monthlyInputs?.noMovement ?? {};
    const absenceEvents = new Set();
    for (const event of p.history ?? []) {
      if (event.type !== 'no-movement-confirmed') continue;
      const {month: key, kind, value} = event.after ?? {};
      if (!value || !['contribution', 'withdrawal'].includes(kind)) continue;
      const signature = [key, kind, value.confirmedAt, value.revision].join('/');
      if (absenceEvents.has(signature)) continue;
      absenceEvents.add(signature);
      const current = absences[key]?.[kind];
      addFlow(kind === 'contribution' ? 'Sem aporte' : 'Sem saque', value, key, true,
        current?.confirmedAt === value.confirmedAt && current?.revision === value.revision ? 'Ausência confirmada' : 'Revisão anterior');
    }
    for (const [key, items] of Object.entries(absences)) {
      for (const [kind, v] of Object.entries(items)) {
        if (!absenceEvents.has([key, kind, v.confirmedAt, v.revision].join('/'))) {
          addFlow(kind === 'contribution' ? 'Sem aporte' : 'Sem saque', v, key, true);
        }
      }
    }
    flows.sort((a, b) => String(a[3]).localeCompare(String(b[3])) || String(a[8]).localeCompare(String(b[8])));
    for (const flow of flows) t.movements.rows.push(flow);

    for (const [kind, entries] of [['Mensal', p.closures], ['Anual', p.annualClosures?.years]]) {
      for (const [period, record] of Object.entries(entries ?? {}).sort()) {
        for (let v = record, current = true; v; v = v.previous, current = false) {
          const summary = v.summary ?? v.snapshot;
          const reopened = v.invalidatedAt ?? v.reopenedAt;
          t.closures.rows.push([...who, kind, v.startMonth ?? period, v.endMonth ?? period,
            v.confirmed ? current ? 'Confirmado' : 'Confirmação anterior' : current ? 'Reaberto' : 'Reabertura anterior',
            v.revision, v.confirmedAt, reopened, v.signerName, v.declaration, v.invalidationReason ?? v.reason ?? v.reopenReason,
            summary?.openUsd, summary?.resultUsd, summary?.contributionUsd, summary?.withdrawalUsd, summary?.closeUsd,
            ...quoteFields(v.fxQuote)]);
        }
      }
    }
    const profile = app.engine.profiles.find(v => v.id === p.profileId);
    for (const [key, label] of [['adequate', 'Renda adequada'], ['ideal', 'Renda ideal']]) {
      const g = p.goals?.[key], read = model.goals[key];
      t.accounts.rows.push([...who, archive ? 'Arquivado' : 'Ativo', p.startMonth, model.rows.at(-1)?.month, p.initialUsd,
        profile?.name ?? p.profileId, profile?.rate, p.monthlyContributionUsd, p.stopAfter, label,
        g?.currency === 'USD' ? g.value : null, g?.currency === 'BRL' ? g.value : null, g?.usd,
        read?.requiredCapitalUsd, status[read?.status] ?? null, read?.month, read?.referenceMonth, read?.remainingMonths,
        ...quoteFields(g?.quote), archive?.archivedAt]);
    }
  }

  function prepare(document, options) {
    const envelope = document.patrimonialPlanning;
    const calc = {...options, balancePolicy: 'confirmed-projection'};
    const active = envelope?.accounts.filter(a => a.active) ?? [];
    const summary = table('Resumo', ['Conta', usd('Patrimônio confirmado'), usd('Aportes confirmados'),
      usd('Resultado confirmado'), month('Confirmado até'), integer('Meses finalizados'), integer('Meses decorridos'),
      'Base da posição', month('Mês pendente')]);
    const details = detailTables();
    const base = {INITIAL_CAPITAL: 'Capital inicial', CLOSED: 'Fechamentos calculáveis', NOT_STARTED: 'Plano ainda não iniciado'};
    for (const a of active) {
      const model = app.engine.account(a, calc);
      const {confirmed: s, confirmedThrough: through, rows} = model;
      summary.rows.push([a.name, s.balanceUsd, closed(s.contributionsUsd, through), closed(s.resultUsd, through),
        through, rows.filter(r => r.finalized).length, rows.filter(r => r.month <= options.month).length,
        base[s.basis], model.blockingMonth]);
      addDetails(details, a, model, calc);
    }
    const portfolio = active.length ? app.engine.sheetView(envelope, {...calc, chartPeriod: 'full'}) : null;
    const s = portfolio?.sheet?.summary;
    summary.metrics = [s?.balanceUsd, s?.contributionsUsd, s?.resultUsd];
    summary.basis = s ? base[s.basis] ?? 'Posição calculável da carteira' : 'Nenhuma conta ativa';
    summary.through = portfolio?.confirmedThrough;
    summary.series = portfolio?.sheet?.chart.series ?? [];
    const tables = [summary, ...Object.values(details)];
    if (options.includeArchived && envelope) {
      const archived = detailTables('Arq. ');
      const records = new Map();
      for (const a of envelope.accounts.filter(a => !a.active && a.plan)) {
        const event = a.plan.history?.findLast(item => item.type === 'account-archived');
        records.set(a.plan.id, {account: a, archive: {archivedAt: event?.at}});
      }
      for (const v of envelope.archive ?? []) {
        if (v.plan) records.set(v.plan.id, {account: {...v.account, id: v.accountId, plan: v.plan}, archive: v});
      }
      for (const {account, archive} of records.values()) {
        const end = archive.archivedAt?.slice(0,7);
        const atArchive = end ? {...calc, month:end, quote:undefined} : calc;
        addDetails(archived, account, app.engine.account(account, atArchive), atArchive, archive);
      }
      if (records.size) tables.push(...Object.values(archived));
    }
    return tables;
  }
  app.excelModel = Object.freeze({prepare});
})(window);
