# Planejamento Patrimonial

Aplicativo independente, com as três áreas **Comece aqui**, **Consolidado** e **Preenchimento mensal**. Simula120meses, preserva contas e históricos, permite registrar resultados/aportes/saques e confirmar fechamentos. Cálculos e comandos são cópias verificadas por hash da versão de origem; não há conexão com o software JP Wealth.

## Dados no navegador

Não há cadastro ou sincronização em nuvem. A hospedagem recebe os arquivos do aplicativo, nunca os seus planos. Câmbio diário e histórico são consultados no Frankfurter; apenas par/data saem do navegador. Referência diária não é cotação intradiária. Sem rede, valores indisponíveis continuam explícitos; previsões não são garantias.

**Backup e dados → Exportar backup** prepara um JSON próprio. Guarde esse arquivo fora do navegador. Para levar planos a outro dispositivo, use **Restaurar backup**, confira o resumo e confirme a substituição. Backups completos do JP Wealth não são aceitos. Rascunhos restaurados permitem leitura/cópia e exigem nova revisão no formulário.

Gravação só é confirmada após leitura idêntica do armazenamento. Quota, conflitos ou corrupção não viram base vazia. Resultado indeterminado bloqueia repetição: exporte a cópia de recuperação e confira a base gravada. O controle entre abas é otimista; não representa uma transação atômica universal. Uma restauração pode confirmar a base e ficar com preferências pendentes; o aviso identifica o estado e permite retomar. Cancelar pendência arquiva seu conteúdo para recuperação.

Limpar os dados do navegador pode remover seus planos. O backup é o mecanismo de recuperação; não prometemos persistência antes da confirmação de gravação nem recuperação de um navegador apagado sem arquivo exportado.

## Desenvolvimento e verificação

Runtime: Node22+ e Python3.10+ com as dependências de `requirements-dev.txt` e Chromium do Playwright. Sem dependências de runtime/frontend ou instalação de pacotesJS.

```sh
node tools/build.js
node tools/check.js
node tools/test.js
python3 -m http.server 8010 --bind 127.0.0.1 --directory dist
```

Para instalações com ambientes separados, configure `PP_PYTHON` e `PP_CHROMIUM` ao rodar a suíte. O único artefato publicado é `dist/`. Logs/capturas e dados sintéticos ficam em `outputs/`, ignorados pelo Git. Build reprodutível identificado em `dist/assets/version.js`.

A suíte inclui49casos de motor,17de paridade matemática,87de comandos/estado, testes de câmbio e24grupos do novo armazenamento/backup;15jornadas de navegador cobrem os fluxos copiados, recuperação, restauração entre contextos, quota de preferências, dados não enviados, temas/320px e zoom nativo200%. Falhas brutas são preservadas nos recibos; números só representam execuções quando o recibo do candidato confirmaPASS.

## Proveniência e publicação

`docs/source-provenance.json` identifica os fontes de origem, hashes e adaptações. O motor/estado não são modificados. A apresentação foi extraída e recebeu marca e chaves próprias; o shell adiciona armazenamento/backup/tema e alvos44px. A origem permanece intacta.

Publicação solicitada no Sites com endereço próprio e acesso público anônimo. `.openai/hosting.json` identifica unicamente este projeto. Commit e push para o repositório exclusivo da hospedagem aguardam autorização do proprietário sobre o candidato pronto. Nenhum Git ou publicação no JP Wealth integra esta entrega.
