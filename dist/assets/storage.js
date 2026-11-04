/* Local-only confirmed document adapter. Never loads JP Wealth storage. */
var S;
var DEFAULTS = {};
(function (root) {
  'use strict';
  const KEY = 'planejamento_patrimonial_state_v1';
  const RECOVERY_PREFIX = 'planejamento_patrimonial_recovery_';
  const FORMAT = 'planejamento_patrimonial_state';
  const LIMIT = 32 * 1024 * 1024;
  const clone = value => structuredClone(value);
  const object = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const id = () => root.crypto.randomUUID();
  const owner = id(), recoveryKey = RECOVERY_PREFIX + owner;
  const UNREAD = Symbol('unread');
  const listeners = new Set();
  let expectedRaw = UNREAD, confirmed = {}, revision = 0, epoch = 0;
  let phase = 'BLOCKED', reason = '', unknown = false, pending = null;
  let lastRecovery = null, recoveryDiscoveryIssue = false;
  const secret = /password|passwd|senha|secret|token|credential|authorization|api[-_]?key|private[-_]?key/i;
  function safe(value, seen = new Set()) {
    if (value === null || typeof value === 'string' || typeof value === 'boolean') return;
    if (typeof value === 'number' && Number.isFinite(value)) return;
    if (!value || typeof value !== 'object' || seen.has(value)) throw Error('Conteúdo não serializável.');
    seen.add(value);
    for (const key of Object.keys(value)) {
      if (secret.test(key) || ['__proto__', 'prototype', 'constructor'].includes(key)) throw Error('Segredos ou campos de controle não são aceitos.');
      safe(value[key], seen);
    }
    seen.delete(value);
  }
  function exact(value, keys) {
    return object(value) && Object.keys(value).sort().join(',') === keys.slice().sort().join(',');
  }
  function bytes(raw) { return new TextEncoder().encode(raw).byteLength; }
  function validateDocument(value) {
    safe(value);
    if (!object(value) || Object.keys(value).some(k => k !== 'patrimonialPlanning')) throw Error('Documento contém dados de outro aplicativo.');
    if (Object.prototype.hasOwnProperty.call(value, 'patrimonialPlanning')) {
      const engine = root.JPWPlanning && root.JPWPlanning.engine;
      if (!engine) throw Error('Motor de planejamento indisponível.');
      const issues = engine.validateEnvelope(value.patrimonialPlanning);
      if (issues.length) throw Error(issues.join(' '));
    }
    const raw = JSON.stringify(value);
    if (bytes(raw) > LIMIT) throw Error('Documento excede o limite de32MiB.');
    return clone(value);
  }
  function parse(raw) {
    if (raw === null) return {revision: 0, document: {}};
    if (typeof raw !== 'string' || bytes(raw) > LIMIT) throw Error('Base excede o limite ou não pode ser lida.');
    const value = JSON.parse(raw);
    if (!exact(value, ['format', 'schemaVersion', 'revision', 'document', 'writeId']) || value.format !== FORMAT || value.schemaVersion !== 1 ||
        !Number.isSafeInteger(value.revision) || value.revision < 0 || typeof value.writeId !== 'string' || !value.writeId || value.writeId.length > 120) {
      throw Error('Base incompatível ou versão não suportada. Preserve uma cópia para recuperação.');
    }
    safe(value);
    return {revision: value.revision, document: validateDocument(value.document)};
  }
  function status() { return {status: phase, reason, revision, epoch}; }
  function notify() { for (const fn of listeners) { try { fn(status()); } catch (_) {} } }
  function change(next, why) { phase = next; reason = why || ''; notify(); }
  function read() { return localStorage.getItem(KEY); }
  function initialRecovery(raw) {
    let length, pendingCopy = false, unreadable = false;
    try { length = localStorage.length; }
    catch (_) { return {pendingCopy: false, unreadable: true}; }
    for (let i = 0; i < length; i++) {
      let key;
      try { key = localStorage.key(i); }
      catch (_) { unreadable = true; continue; }
      if (!key || !key.startsWith(RECOVERY_PREFIX)) continue;
      // One opaque entry must neither conceal later copies nor certify them.
      try {
        const text = localStorage.getItem(key);
        if (typeof text !== 'string' || bytes(text) > LIMIT * 2 + 4096) throw Error('Cópia ilegível.');
        const item = JSON.parse(text);
        if (!exact(item, ['format', 'schemaVersion', 'owner', 'at', 'outcome', 'previousRaw', 'candidateRaw']) ||
            item.format !== 'planejamento_patrimonial_recovery' || item.schemaVersion !== 1 ||
            typeof item.owner !== 'string' || !item.owner || item.owner.length > 120 ||
            typeof item.at !== 'string' || !Number.isFinite(Date.parse(item.at)) ||
            !['pending', 'confirmed', 'refused'].includes(item.outcome) ||
            !(item.previousRaw === null || typeof item.previousRaw === 'string') || typeof item.candidateRaw !== 'string') throw Error('Cópia incompatível.');
        parse(item.candidateRaw);
        if (item.outcome === 'pending' && item.candidateRaw !== raw) {
          lastRecovery = item; pendingCopy = true;
        }
      } catch (_) { unreadable = true; }
    }
    return {pendingCopy, unreadable};
  }
  function load(initial) {
    let raw;
    try { raw = read(); expectedRaw = raw; }
    catch (_) { change('BLOCKED', 'Não foi possível acessar a base local. Os dados não foram substituídos.'); return status(); }
    let value;
    try { value = parse(raw); }
    catch (error) { epoch++; change('BLOCKED', error.message); return status(); }
    confirmed = clone(value.document); S = clone(confirmed); revision = value.revision; unknown = false; pending = null; epoch++;
    const discovery = initial ? initialRecovery(raw) : null;
    if (discovery) recoveryDiscoveryIssue = discovery.unreadable;
    if (discovery && (discovery.pendingCopy || discovery.unreadable)) change('RECOVERY', discovery.unreadable ?
      'Há cópias de recuperação ilegíveis ou incompatíveis, preservadas para revisão. Exporte a recuperação e reconfira explicitamente a base atual antes de editar.' :
      'Uma tentativa anterior precisa de conferência. Exporte a recuperação ou reconfira a base atual antes de editar.');
    else change('READY', initial ? '' : recoveryDiscoveryIssue ?
      'Base atual reconferida por sua ação. Cópias de recuperação ilegíveis continuam preservadas para revisão.' :
      'Base atual reconferida. Cópias de recuperação preservadas.');
    return status();
  }
  function journal(outcome) {
    const item = {format: 'planejamento_patrimonial_recovery', schemaVersion: 1, owner, at: new Date().toISOString(),
      outcome, previousRaw: pending.before, candidateRaw: pending.after};
    const raw = JSON.stringify(item);
    localStorage.setItem(recoveryKey, raw);
    if (localStorage.getItem(recoveryKey) !== raw) throw Error('Cópia de recuperação não confirmada.');
    lastRecovery = item;
  }
  function refuse(why, message) { reason = message; notify(); return {status: 'REFUSED', reason: why}; }
  function uncertain(message) { unknown = true; epoch++; change('UNKNOWN', message); return {status: 'UNKNOWN', reason: 'READ_AFTER_WRITE'}; }
  function persist(candidate, options = {}, restoring = false) {
    if (unknown && !restoring) return {status: 'UNKNOWN', reason: 'RECOVERY_REQUIRED'};
    if (phase !== 'READY' && !restoring) return refuse(phase === 'CONFLICT' ? 'CONFLICT' : 'BLOCKED', reason || 'A base precisa de recuperação.');
    if (!Number.isSafeInteger(options.expectedEpoch) || options.expectedEpoch !== epoch) return refuse('CONFLICT', 'O contexto mudou. Confira novamente antes de salvar.');
    let document;
    try { document = validateDocument(candidate); }
    catch (error) { return refuse('INVALID', error.message); }
    let before;
    try { before = read(); }
    catch (_) { change('BLOCKED', 'Não foi possível conferir a base antes da gravação.'); return {status: 'REFUSED', reason: 'READ_BEFORE_WRITE'}; }
    if (expectedRaw === UNREAD || before !== expectedRaw) { epoch++; change('CONFLICT', 'A base mudou em outra aba. Preserve o preenchimento e reconfira a base.'); return {status: 'REFUSED', reason: 'CONFLICT'}; }
    if (revision >= Number.MAX_SAFE_INTEGER) return refuse('INVALID', 'Limite de revisões alcançado. Exporte uma cópia.');
    const after = JSON.stringify({format: FORMAT, schemaVersion: 1, revision: revision + 1, document, writeId: id()});
    if (bytes(after) > LIMIT) return refuse('INVALID', 'Base excede o limite de32MiB.');
    pending = {before, after, document};
    try { journal('pending'); }
    catch (_) { pending = null; return refuse('RECOVERY_WRITE_REFUSED', 'Não foi possível preservar a cópia anterior. Nenhum dado foi confirmado. Verifique o espaço disponível.'); }
    try {
      if (read() !== before) { epoch++; change('CONFLICT', 'A base mudou durante a preparação. Cópia preservada; confira antes de repetir.'); try { journal('refused'); } catch (_) {} return {status: 'REFUSED', reason: 'CONFLICT'}; }
    } catch (_) { change('BLOCKED', 'Não foi possível reconferir a base. A tentativa não foi executada.'); return {status: 'REFUSED', reason: 'READ_BEFORE_WRITE'}; }
    let threw = false;
    try { localStorage.setItem(KEY, after); } catch (_) { threw = true; }
    let actual;
    try { actual = read(); }
    catch (_) { return uncertain('Não foi possível confirmar a gravação. Exporte a recuperação e confira a base antes de repetir.'); }
    if (actual !== after) {
      if (threw && actual === before) { try { journal('refused'); } catch (_) {} pending = null; return refuse('WRITE_REFUSED', 'Gravação recusada. A base anterior foi preservada.'); }
      return uncertain('O resultado da gravação mudou ou não foi confirmado. Cópia da tentativa preservada para recuperação.');
    }
    expectedRaw = after; confirmed = clone(document); S = clone(document); revision++; epoch++; unknown = false;
    try { journal('confirmed'); } catch (_) { /* Main exact read-back confirmed; journal remains recoverable. */ }
    pending = null; change('READY', 'Salvo neste navegador.');
    return {status: 'CONFIRMED', payload: after};
  }
  root.jpWealthPersistenceEpoch = () => epoch;
  root.jpWealthConfirmedStateSnapshot = () => clone(confirmed);
  root.jpWealthPersistenceOutcomeIsUnknown = () => unknown;
  root.markJPWealthPersistenceOutcomeUnknown = message => uncertain(message || 'Gravação indeterminada; confira a recuperação.');
  root.jpWealthPersistDocument = (candidate, options) => persist(candidate, options);
  root.PlanningStore = Object.freeze({KEY, RECOVERY_PREFIX, MAX_BYTES: LIMIT, status, epoch: () => epoch,
    validateDocument, reload: () => load(false), recoverLatest: () => load(false),
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    exportDocument() {
      if (phase !== 'READY') throw Error('A base precisa ser reconferida. Use a cópia de recuperação.');
      let actual;
      try { actual = read(); } catch (_) { change('BLOCKED', 'A leitura da base está indisponível.'); throw Error(reason); }
      if (actual !== expectedRaw) { epoch++; change('CONFLICT', 'A base mudou em outra aba; reconfira antes de exportar.'); throw Error(reason); }
      return validateDocument(confirmed);
    },
    restoreDocument(document, options) { return persist(document, options, true); },
    exportRecovery() {
      let raw = expectedRaw === UNREAD ? null : expectedRaw, readError = null;
      try { raw = read(); } catch (_) { readError = 'Leitura atual indisponível.'; }
      const recoveryCopies = [];
      let recoveryReadError = null;
      try {
        for (let i = 0; i < localStorage.length; i++) {
          let key;
          try { key = localStorage.key(i); }
          catch (_) { recoveryReadError = 'Nem todas as cópias de recuperação puderam ser lidas.'; continue; }
          if (!key || !key.startsWith(RECOVERY_PREFIX)) continue;
          try { recoveryCopies.push({key, raw: localStorage.getItem(key)}); }
          catch (_) {
            recoveryCopies.push({key, raw: null, readError: 'Leitura indisponível.'});
            recoveryReadError = 'Nem todas as cópias de recuperação puderam ser lidas.';
          }
        }
      } catch (_) { recoveryReadError = 'Nem todas as cópias de recuperação puderam ser lidas.'; }
      return {format: 'planejamento_patrimonial_recovery_export', schemaVersion: 1, createdAt: new Date().toISOString(),
        status: status(), raw, readError, lastConfirmedDocument: clone(confirmed), candidateDocument: pending ? clone(pending.document) : null,
        recovery: lastRecovery ? clone(lastRecovery) : null, recoveryCopies, recoveryReadError};
    }
  });
  S = {};
  load(true);
  if (root.addEventListener) root.addEventListener('storage', event => {
    if (event.key === KEY && event.newValue !== expectedRaw) { epoch++; change('CONFLICT', 'Outra aba alterou a base. Preserve o preenchimento e reconfira antes de continuar.'); }
  });
})(window);
