(function (root) {
  'use strict';
  const main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
  const office = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  const packageNs = 'http://schemas.openxmlformats.org/package/2006';
  const chartNs = 'http://schemas.openxmlformats.org/drawingml/2006/chart';
  const drawingNs = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing';
  const artNs = 'http://schemas.openxmlformats.org/drawingml/2006/main';
  const fileHead = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  function text(value) {
    const string = String(value);
    if (string.length > 32767) throw Error('Há um texto que excede o limite de uma célula do Excel.');
    return esc(string.replace(/_x[0-9a-f]{4}_/gi, match => '_x005F_' + match.slice(1))
      .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\uD800-\uDFFF\uFFFE\uFFFF]/gu,
        c => '_x' + c.charCodeAt(0).toString(16).padStart(4, '0') + '_'));
  }
  function column(n) {
    let name = '';
    for (n++; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + (n - 1) % 26) + name;
    return name;
  }
  const rels = rows => '<Relationships xmlns="' + packageNs + '/relationships">' +
    rows.map(([id, type, target]) => '<Relationship Id="rId' + id + '" Type="' + (type.startsWith('http') ? type : office + '/' + type) +
      '" Target="' + target + '"/>').join('') + '</Relationships>';
  const formats = [
    ['usd', 164, '"US$ "#,##0.00;[Red]("US$ "#,##0.00);"US$ "0.00'],
    ['brl', 165, '"R$ "#,##0.00;[Red]("R$ "#,##0.00);"R$ "0.00'],
    ['rate', 166, '0.00%;[Red](0.00%);0.00%'],
    ['month', 167, 'mm/yyyy'],
    ['date', 168, 'dd/mm/yyyy hh:mm'],
    ['fx', 169, '0.0000'],
    ['integer', 1, '0'],
  ];
  const typeStyle = Object.fromEntries(formats.map(([type], i) => [type, i + 1]));
  const style = {title: 8, note: 9, header: 10, metric: 11, confirmed: 12, pending: 13, projected: 14, wrap: 15};
  const xf = (num, font, fill, alignment = '') => '<xf numFmtId="' + num + '" fontId="' + font + '" fillId="' + fill +
    '" borderId="0" xfId="0" applyFont="1" applyFill="1" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"' + alignment + '/></xf>';
  function styles() {
    const fonts = [[10,'14243A'],[19,'123D67',true],[10,'4B5D72'],[10,'FFFFFF',true],[16,'123D67',true]];
    const fills = ['153E68','E4F3EA','FDEBEE','E9F1FE'];
    const xfs = [xf(0,0,0), ...formats.map(([,n]) => xf(n,0,0,' horizontal="right"')),
      xf(0,1,0),xf(0,2,0),xf(0,3,2,' wrapText="1"'),xf(164,4,0),
      xf(0,0,3),xf(0,0,4),xf(0,0,5),xf(0,0,0,' wrapText="1"')];
    return '<styleSheet xmlns="' + main + '"><numFmts count="6">' + formats.filter(([,n]) => n >= 164)
      .map(([,n,f]) => '<numFmt numFmtId="' + n + '" formatCode="' + esc(f) + '"/>').join('') +
      '</numFmts><fonts count="' + fonts.length + '">' + fonts.map(([size,color,bold]) => '<font>' + (bold ? '<b/>' : '') +
        '<sz val="' + size + '"/><color rgb="FF' + color + '"/><name val="Arial"/><family val="2"/></font>').join('') +
      '</fonts><fills count="6"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>' +
      fills.map(color => '<fill><patternFill patternType="solid"><fgColor rgb="FF' + color + '"/><bgColor indexed="64"/></patternFill></fill>').join('') +
      '</fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
      '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
      '<cellXfs count="' + xfs.length + '">' + xfs.join('') + '</cellXfs>' +
      '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
      '<tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/></styleSheet>';
  }
  function cell(row, col, value, type, formatting) {
    if (value === null || value === undefined || value === '') return '';
    if (type === 'month' || type === 'date') {
      const raw = type === 'month' ? value + '-01T00:00:00Z' : value;
      const timestamp = Date.parse(raw);
      if (!Number.isFinite(timestamp)) throw Error('O relatório encontrou uma data incompatível.');
      value = timestamp / 86400000 + (timestamp < Date.UTC(1900, 2, 1) ? 25568 : 25569);
    }
    const s = formatting ?? typeStyle[type] ?? 0;
    const tag = '<c r="' + column(col) + row + '" s="' + s + '"';
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) throw Error('O relatório encontrou um valor numérico incompatível.');
      return tag + '><v>' + value + '</v></c>';
    }
    return tag + ' t="inlineStr"><is><t xml:space="preserve">' + text(value) + '</t></is></c>';
  }
  const nameOf = h => Array.isArray(h) ? h[0] : h;
  function formatRow(val, header) {
    const name = nameOf(header);
    if (/^(Situação|Base)/.test(name)) {
      if (/^(Confirmado|Finalizado|Atingida|Ausência confirmada)$/.test(val)) return style.confirmed;
      if (/^(Projetado|Projeção)$/.test(val)) return style.projected;
      if (/^(Em aberto|Aguardando|Parcial|Reaberto|Cálculo indisponível)/.test(val)) return style.pending;
    }
    if (name === 'Conta' || /Declaração|Motivo/.test(name)) return style.wrap;
  }
  function rowXML(r, body, height) {
    return '<row r="' + r + '"' + (height ? ' ht="' + height + '" customHeight="1"' : '') + '>' + body + '</row>';
  }
  function width(h) {
    const name = nameOf(h);
    if (/Declaração/.test(name)) return 60;
    if (/Motivo/.test(name)) return 48;
    if (/^ID do/.test(name) || name === 'ID da conta') return 41;
    if (name === 'Conta' || /Fonte|^Base|^Situação/.test(name)) return 29;
    return Math.max(15, Math.min(27, name.length * .8 + 5));
  }
  const pointKeys = ['confirmed', 'planning', 'registered-contributions', 'planned-contributions'];
  function chartData(summary) {
    const labels = [...new Set(summary.series.flatMap(s => s.points.map(p => p.month)))].sort();
    const maps = new Map(summary.series.map(s => [s.id, new Map(s.points.map(p => [p.month, p.value]))]));
    return labels.map(m => [m, ...pointKeys.map(k => maps.get(k)?.get(m))]);
  }
  function sheet(table, index, options, points, hasCharts) {
    const summary = index === 1;
    const source = table.name === 'Projeções' && hasCharts;
    const headerRow = summary && hasCharts ? 25 : summary ? 9 : 4;
    const ref = 'A' + headerRow + ':' + column(table.headers.length - 1) + (headerRow + Math.max(1,table.rows.length));
    if (headerRow + table.rows.length > 1048576) throw Error('Uma aba excede o limite de linhas do Excel.');
    const cells = new Map();
    const put = (r,c,v,t,f) => cells.set(r, (cells.get(r) ?? '') + cell(r,c,v,t,f));
    put(1,0, summary ? 'Planejamento Patrimonial by JP Wealth' : table.name, null, style.title);
    put(2,0, summary ? 'Exportado em ' + options.at + ' · Revisão ' + options.revision + ' · Build ' + options.version : 'Dados em ' + options.month + ' · Valores da revisão exportada', null, style.note);
    if (summary) {
      ['Patrimônio confirmado · US$','Aportes confirmados · US$','Resultado confirmado · US$'].forEach((label,i) => {
        put(4,i*4,label,null,style.note);
        put(5,i*4,table.metrics[i] ?? '—',null,table.metrics[i] == null ? style.note : style.metric);
      });
      put(6,0,table.basis + (table.through ? ' · posição até ' + table.through : ''),null,style.note);
      put(7,0,'Projeção do formulário · simulação independente. Aportes excluem o capital inicial. Lacunas indicam dados indisponíveis.',null,style.note);
    }
    for (const [i,h] of table.headers.entries()) put(headerRow,i,nameOf(h),null,style.header);
    const maxRow = Math.max(headerRow + Math.max(1,table.rows.length), source ? 4 + points.length : 0);
    const result = [];
    const wrapCols = table.headers.flatMap((h,i) => /Declaração|Motivo|^Conta$/.test(nameOf(h)) ? [i] : []);
    const wrapLines = (values,i) => Math.ceil(String(values[i] ?? '').length / (i===0 ? 24 : 45));
    let size = 0;
    for (let r = 1; r <= maxRow; r++) {
      let body = cells.get(r) ?? '';
      const values = table.rows[r - headerRow - 1];
      if (values) body += values.map((v,i) => cell(r,i,v,Array.isArray(table.headers[i]) ? table.headers[i][1] : null,formatRow(v,table.headers[i]))).join('');
      if (source && r === 4) body += ['Mês','Histórico confirmado','Projeção do planejamento','Aportes registrados','Aportes previstos']
        .map((v,i) => cell(r,16+i,v,null,style.header)).join('');
      if (source && points[r-5]) body += points[r-5].map((v,i) => cell(r,16+i,v,i ? 'usd' : null)).join('');
      if (body || r === headerRow + 1) {
        size += body.length;
        if (size > 128 * 1024 * 1024) throw Error('Uma aba excede a capacidade da exportação Excel.');
        const lines = values && wrapCols.length ? Math.max(1,...wrapCols.map(i => wrapLines(values,i))) : 1;
        result.push(rowXML(r,body,r === 1 ? 30 : r === headerRow ? 32 : summary && r === 5 ? 27 : lines > 1 ? Math.min(120,15 * lines) : null));
      }
    }
    const cols = summary ? [25,17,17,17,15,12,12,21,15,12,12,12] : table.headers.map(width);
    if (source) cols.push(4,12,25,25,25,25);
    const pane = summary ? '' : '<pane xSplit="1" ySplit="4" topLeftCell="D5" activePane="bottomRight" state="frozen"/><selection pane="bottomRight" activeCell="D5" sqref="D5"/>';
    return {ref, xml: '<worksheet xmlns="' + main + '" xmlns:r="' + office + '"><sheetViews><sheetView showGridLines="0" workbookViewId="0">' +
      pane + '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="19"/><cols>' + cols.map((w,i) => '<col min="' + (i+1) +
        '" max="' + (i+1) + '" width="' + w + '" customWidth="1"' + (!summary && (i===1 || i===2) ? ' hidden="1"' : '') +
        '/>').join('') + '</cols><sheetData>' + result.join('') +
      '</sheetData><pageMargins left="0.35" right="0.35" top="0.45" bottom="0.45" header="0.2" footer="0.2"/>' +
      (summary && hasCharts ? '<drawing r:id="rId2"/>' : '') + '<tableParts count="1"><tablePart r:id="rId1"/></tableParts></worksheet>'};
  }
  function nativeTable(table, id, ref) {
    return '<table xmlns="' + main + '" id="' + id + '" name="PPDados' + id + '" displayName="PPDados' + id + '" ref="' + ref +
      '" totalsRowShown="0"><autoFilter ref="' + ref + '"/><tableColumns count="' + table.headers.length + '">' +
      table.headers.map((h,i) => '<tableColumn id="' + (i+1) + '" name="' + text(nameOf(h)) + '"/>').join('') +
      '</tableColumns><tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" showLastColumn="0" showRowStripes="1" showColumnStripes="0"/></table>';
  }
  function chart(title, indexes, points) {
    const titles = ['Histórico confirmado','Projeção do planejamento','Aportes registrados','Aportes previstos'];
    const colors = ['14528C','00899A','287347','AD5A20'];
    const ref = (col) => "'Projeções'!$" + col + '$5:$' + col + '$' + (points.length+4);
    const cache = i => '<c:ptCount val="' + points.length + '"/>' +
      points.map((p,n) => p[i] == null ? '' : '<c:pt idx="' + n + '"><c:v>' + esc(p[i]) + '</c:v></c:pt>').join('');
    const series = indexes.map((i,n) => '<c:ser><c:idx val="' + n + '"/><c:order val="' + n +
      '"/><c:tx><c:v>' + esc(titles[i]) + '</c:v></c:tx><c:spPr><a:ln w="28575"><a:solidFill><a:srgbClr val="' +
      colors[i] + '"/></a:solidFill>' + (i % 2 ? '<a:prstDash val="dash"/>' : '') +
      '</a:ln></c:spPr><c:marker><c:symbol val="' + (i % 2 ? 'none' : 'circle') + '"/><c:size val="4"/></c:marker>' +
      '<c:cat><c:strRef><c:f>' + esc(ref('Q')) + '</c:f><c:strCache>' + cache(0) + '</c:strCache></c:strRef></c:cat>' +
      '<c:val><c:numRef><c:f>' + esc(ref(column(17+i))) + '</c:f><c:numCache><c:formatCode>General</c:formatCode>' +
      cache(i+1) + '</c:numCache></c:numRef></c:val><c:smooth val="0"/></c:ser>').join('');
    return '<c:chartSpace xmlns:c="' + chartNs + '" xmlns:a="' + artNs + '"><c:lang val="pt-BR"/><c:chart><c:title><c:tx><c:rich>' +
      '<a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="pt-BR" sz="1300" b="1"/><a:t>' + esc(title) +
      '</a:t></a:r></a:p></c:rich></c:tx></c:title><c:plotArea><c:layout/><c:lineChart><c:grouping val="standard"/>' + series +
      '<c:axId val="101"/><c:axId val="102"/></c:lineChart><c:catAx><c:axId val="101"/><c:scaling><c:orientation val="minMax"/></c:scaling>' +
      '<c:axPos val="b"/><c:tickLblPos val="low"/><c:crossAx val="102"/><c:crosses val="autoZero"/><c:auto val="1"/>' +
      '<c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:tickLblSkip val="' + Math.max(1,Math.ceil(points.length/8)) +
      '"/></c:catAx><c:valAx><c:axId val="102"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="l"/>' +
      '<c:majorGridlines/><c:numFmt formatCode="#,##0" sourceLinked="0"/><c:tickLblPos val="nextTo"/><c:crossAx val="101"/>' +
      '<c:crosses val="autoZero"/><c:crossBetween val="between"/></c:valAx></c:plotArea><c:legend><c:legendPos val="b"/>' +
      '<c:overlay val="0"/></c:legend><c:plotVisOnly val="0"/><c:dispBlanksAs val="gap"/><c:showDLblsOverMax val="0"/></c:chart></c:chartSpace>';
  }
  function drawing() {
    const anchor = (tag,col,row) => '<xdr:' + tag + '><xdr:col>' + col + '</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>' +
      row + '</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:' + tag + '>';
    return '<xdr:wsDr xmlns:xdr="' + drawingNs + '" xmlns:a="' + artNs + '" xmlns:c="' + chartNs + '" xmlns:r="' + office + '">' +
      [0,1].map(i => '<xdr:twoCellAnchor editAs="oneCell">' + anchor('from', i * 6, 8) + anchor('to', (i+1)*6, 23) +
        '<xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr id="' + (i+1) + '" name="Gráfico ' + (i+1) +
        '"/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr><xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>' +
        '<a:graphic><a:graphicData uri="' + chartNs + '"><c:chart r:id="rId' + (i+1) +
        '"/></a:graphicData></a:graphic></xdr:graphicFrame><xdr:clientData/></xdr:twoCellAnchor>').join('') + '</xdr:wsDr>';
  }

  // ZIP STORE framing adapted from tools/package-netlify.js for Uint8Array.
  const crcTable = Uint32Array.from({length:256}, (_,n) => {
    for (let i = 0; i < 8; i++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1;
    return n;
  });
  function crc32(bytes) {
    let crc = -1;
    for (const n of bytes) crc = crcTable[(crc ^ n) & 255] ^ (crc >>> 8);
    return (crc ^ -1) >>> 0;
  }
  function zip(parts) {
    const local = [], directory = [], encoder = new TextEncoder();
    let offset = 0, directorySize = 0;
    const u16 = (a,k,v) => new DataView(a.buffer).setUint16(k,v,true);
    const u32 = (a,k,v) => new DataView(a.buffer).setUint32(k,v,true);
    for (const [path, xml] of parts) {
      const name = encoder.encode(path), data = encoder.encode(fileHead + xml);
      if (offset + data.length > 128 * 1024 * 1024) throw Error('O arquivo Excel excede 128 MiB. Tente sem os planos arquivados.');
      const crc = crc32(data), l = new Uint8Array(30), d = new Uint8Array(46);
      u32(l,0,0x04034b50); u16(l,4,20); u16(l,6,0x800); u16(l,12,0x21);
      u32(l,14,crc); u32(l,18,data.length); u32(l,22,data.length); u16(l,26,name.length);
      u32(d,0,0x02014b50); u16(d,4,20); u16(d,6,20); u16(d,8,0x800); u16(d,14,0x21);
      u32(d,16,crc); u32(d,20,data.length); u32(d,24,data.length); u16(d,28,name.length); u32(d,42,offset);
      local.push(l,name,data); directory.push(d,name);
      offset += l.length + name.length + data.length;
      directorySize += d.length + name.length;
    }
    const end = new Uint8Array(22);
    u32(end,0,0x06054b50); u16(end,8,parts.size); u16(end,10,parts.size); u32(end,12,directorySize); u32(end,16,offset);
    return new Blob([...local,...directory,end], {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
  }
  function workbook(tables, options) {
    const parts = new Map(), types = [];
    let xmlSize = 0;
    function add(path, xml, type) {
      xmlSize += xml.length;
      if (xmlSize > 128 * 1024 * 1024) throw Error('O arquivo Excel excede 128 MiB. Tente sem os planos arquivados.');
      parts.set(path, xml);
      if (type) types.push('<Override PartName="/' + path + '" ContentType="application/vnd.openxmlformats-officedocument.' + type + '+xml"/>');
    }
    const points = chartData(tables[0]), hasCharts = points.some(p => p.slice(1).some(Number.isFinite));
    const sheetRels = tables.map((_,i) => [i+1,'worksheet','worksheets/sheet'+(i+1)+'.xml']);
    add('_rels/.rels', rels([[1,'officeDocument','xl/workbook.xml']]));
    add('xl/workbook.xml', '<workbook xmlns="' + main + '" xmlns:r="' + office + '"><bookViews><workbookView/></bookViews><sheets>' +
      tables.map((t,i) => '<sheet name="' + esc(t.name) + '" sheetId="' + (i+1) + '" r:id="rId' + (i+1) + '"/>').join('') +
      '</sheets></workbook>', 'spreadsheetml.sheet.main');
    add('xl/_rels/workbook.xml.rels',rels([...sheetRels,[tables.length+1,'styles','styles.xml']]));
    add('xl/styles.xml', styles(), 'spreadsheetml.styles');
    for (const [i,t] of tables.entries()) {
      const id = i+1, view = sheet(t,id,options,points,hasCharts);
      add('xl/worksheets/sheet'+id+'.xml',view.xml,'spreadsheetml.worksheet');
      add('xl/worksheets/_rels/sheet'+id+'.xml.rels',rels([[1,'table','../tables/table'+id+'.xml'],
        ...(id===1 && hasCharts ? [[2,'drawing','../drawings/drawing1.xml']] : [])]));
      add('xl/tables/table'+id+'.xml',nativeTable(t,id,view.ref),'spreadsheetml.table');
    }
    if (hasCharts) {
      add('xl/drawings/drawing1.xml',drawing(),'drawing');
      add('xl/drawings/_rels/drawing1.xml.rels',rels([[1,'chart','../charts/chart1.xml'],[2,'chart','../charts/chart2.xml']]));
      add('xl/charts/chart1.xml',chart('Patrimônio · US$',[0,1],points),'drawingml.chart');
      add('xl/charts/chart2.xml',chart('Aportes acumulados · US$',[2,3],points),'drawingml.chart');
    }
    add('[Content_Types].xml','<Types xmlns="' + packageNs + '/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
      '<Default Extension="xml" ContentType="application/xml"/>' + types.join('') + '</Types>');
    return zip(parts);
  }
  root.JPWPlanning.excelWriter = Object.freeze({workbook});
})(window);
