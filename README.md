# Planejamento Patrimonial

Aplicativo independente, com as três áreas **Comece aqui**, **Consolidado** e **Preenchimento mensal**. Simula120meses, preserva contas e históricos, permite registrar resultados/aportes/saques e confirmar fechamentos. A origem do motor é preservada por hash e por uma cópia de referência; sua política de leitura tem adaptação local documentada; a camada de comandos tem adaptação local documentada para o fechamento mensal; não há conexão com o software JP Wealth.

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

`docs/source-provenance.json` identifica os fontes de origem, hashes e adaptações. Fórmulas, limites e precisão do motor original são preservados. A leitura ativa usa a política `confirmed-projection`, que exige o fechamento da base antes de liberar projeções; o modo original continua disponível para paridade e cenários iniciais isolados. A camada de comandos foi adaptada exclusivamente neste projeto para exigir Resultado, Saque e Aporte antes do fechamento, preservando o escritor confirmado e as regras financeiras existentes. A apresentação foi extraída e recebeu marca e chaves próprias; o shell adiciona armazenamento/backup/tema e alvos44px. A origem permanece intacta.

Publicação solicitada no Sites com endereço próprio e acesso público anônimo. `.openai/hosting.json` identifica unicamente este projeto. Commit e push para o repositório exclusivo da hospedagem aguardam autorização do proprietário sobre o candidato pronto. Nenhum Git ou publicação no JP Wealth integra esta entrega.

## Preenchimento e fechamento mensal

Abra as células com borda e seta para editar Resultado, Saque e Aporte. Revisar mostra os valores; Confirmar registro grava. Nenhum campo é salvo ao perder foco. Resultado zero exige informar zero. Aporte/saque sem movimento exigem escolher e confirmar Sem aporte/Sem saque. Isso registra uma confirmação administrativa, sem criar fluxo financeiro. Lançamentos anulados não contam como confirmação de ausência.

O check de Finalizado só é liberado com as três informações e os demais requisitos de fechamento satisfeitos. O resumo exige confirmação explícita. Meses finalizados anteriormente continuam válidos; meses abertos não recebem zeros por inferência. Confirmações opcionais ficam no plano em `monthlyInputs` versão1 e viajam no backup próprio atual. Documentos antigos são aceitos sem migração ou gravação na leitura. Um leitor anterior a esta atualização não aplica a nova exigência; eventual reversão deve manter este leitor/guard compatível até exportar e tratar explicitamente esses dados.

A suíte inclui também11grupos focais de comandos/armazenamento (incluindo as8combinações de preenchimento) e12jornadas focais de interface. Resultados efetivos e identificação do candidato ficam em `outputs/full-result.json`; não interpretar números de inventário como evidência de execução.

## Saldo parcial e projeções

Em Preenchimento mensal, os meses atuais/passados mostram somente registros efetivos. O primeiro mês aberto usa a abertura confirmada e ignora rendimento e aporte previstos no saldo parcial; ausência permanece pendente, sem criar um lançamento zero. Se faltar fechamento anterior, a abertura e o patrimônio ficam indisponíveis. Um mês preenchido mas aberto é identificado como Registrado; o fechamento continua explícito.

A projeção futura aguarda o fechamento dos meses atuais e anteriores do plano. Enquanto houver bloqueio, abertura/resultado monetário/patrimônio dependentes ficam indisponíveis; premissas futuras continuam editáveis. Fechar novembro em1000 libera dezembro com abertura1000, retorno3% e aporte200: encerramento1230; janeiro abre1230. Corrigir/reabrir novembro volta a bloquear os dependentes. Na virada para dezembro, sua previsão anterior não vira resultado real: o mês passa a usar somente registros efetivos e janeiro aguarda seu fechamento.

A mesma política central (`balancePolicy: confirmed-projection`) alimenta modelos de conta, carteira, tabela, gráficos, metas, subtotais, simulações de contas existentes e PDF. `projectionStatus` e `blockingMonth` são metadados de leitura, nunca persistidos. Uma conta pendente impede o total projetado correspondente, sem somá-la como zero. O adaptador `monthly-view.js` só apresenta os mesmos valores do motor, sem calcular uma trajetória independente. Referência inicial e simulações de novos planos permanecem cenários identificados, sem alteração de registros.

Os testes `closure_sequence.test.js` incluem18grupos de continuidade, bloqueio, reabertura, virada de mês, várias contas, ausência deFX, backup e paridade com a origem imutável em `tests/fixtures/planning-engine-source.js`. `monthly_alignment.py` mantém9casos de layout/teclado/zoom nativo. Nenhum resultado de inventário substitui o recibo do candidato.

## Atualização de arquivos

O build identifica HTML, scripts, estilos e ícone com a mesma chave de conteúdo. URLs dos recursos recebem `?v=<build>` para impedir mistura entre motor antigo em cache e interface nova. O hash normaliza esses parâmetros para manter o build reproduzível; o protocolo de versionamento participa da identidade. O teste `asset_cache_browser.py` aquece o cache com a versão original do motor, abre o aplicativo novo na mesma origem e confirma a leitura correta sem alterar a base financeira.

## Abrir e retomar formulários

No Comece aqui, Preencher novo formulário sempre abre uma nova configuração com custo mensal e renda desejada emBRL. Não reabre silenciosamente o plano salvo. Editar plano existente é a ação separada que preserva a moeda salva. Continuar rascunho retoma os campos e a moeda escolhida; abrir outro formulário não descarta os rascunhos anteriores, que também permanecem exportáveis. Nenhuma dessas navegações confirma ou grava um plano.

### Resultado realizado e meses pendentes

Meses passados ainda abertos usam destaque vermelho claro (escuro adaptado ao tema); meses finalizados preservam o estado confirmado. O destaque segue a preferência de destacar meses passados. O editor de Resultado recebe somente o total em US$, moeda das contas do aplicativo; lucro é positivo, prejuízo negativo e zero é explícito. A rentabilidade é calculada sobre o saldo inicial disponível e positivo, sem incluir aportes do mês no denominador. Sem essa base, o percentual fica indisponível. O primeiro botão Confirmar abre a conferência e não grava; Confirmar registro mantém a confirmação de persistência e o histórico de correções. A entrada percentual permanece apenas nas premissas futuras e no contrato compatível do motor, sem seletor no registro realizado.

### Mês vigente, percentual e base inicial

O mês vigente usa azul claro, com adaptação ao tema escuro. A tabela mensal tem uma coluna de Resultado · % somente de leitura à esquerda de Resultado · US$. No celular ambas permanecem em colunas distintas; saldo inicial, movimentos e fechamento continuam nos detalhes. As premissas futuras de rentabilidade continuam configuráveis pelo editor da projeção.

Antes do primeiro fechamento, a posição patrimonial mostra somente o capital inicial cadastrado das contas já iniciadas, identificando essa base e a espera pelo fechamento. Não inclui resultados de meses abertos, aportes previstos ou capitais de contas que começam no futuro; não cria lançamentos. Após fechar, usa o saldo no fechamento contínuo comum, que já inclui o capital inicial uma única vez. Resultado e aportes mensais confirmados permanecem indisponíveis até haver fechamento. A mesma base de leitura é usada pelo Consolidado e PDF; as fórmulas e a compatibilidade do motor original permanecem preservadas.

### Navegação e encerramento anual

Preenchimento mensal mostra um ano civil por vez, com setas e resumo acima da tabela. Os120meses permanecem no motor; primeiro e último anos cobrem só os meses do plano. Opções da tabela recolhe filtros, sem atravessar o ano selecionado. Correções e lançamentos individuais permanecem nos editores das células; a consulta histórica fica no detalhe do mês.

O resumo distingue meses finalizados, base de abertura disponível e projeções. Encerre o ano após finalizar todos os meses do período, sem antecipar meses futuros. Revise os totais, informe o nome e confirme a declaração. O termo é local: guarda nome, texto/versionamento, data, resumo e revisões mensais; a plataforma não autentica uma identidade externa. Registros realizados e fechamentos do ano seguinte aguardam todos os anos anteriores encerrados; consulta e previsões continuam disponíveis. Anos assinados precisam de reabertura com motivo; termos posteriores são invalidados sem apagar registros ou assinaturas anteriores. Alterações de contexto não reutilizam o aceite.

Armazenamento e backup novos usam envelope versão3, com a mesma chave local anterior. A leitura aceita versões1/2/3 sem gravar durante abertura. A primeira gravação explicitamente confirmada usa3; nenhum termo ou fechamento é inferido em bases antigas. O exportador produz backup3 e o importador aceita1/2/3, validando termos ativos/arquivados e referências dos registros mensais, preservando históricos e tratando rascunhos como texto. Leitores anteriores recusam os envelopes3; fixtures imutáveis verificam essa recusa. Antes desta mudança há cópia recuperável em outputs/before-annual-review, ignorada peloGit e não destinada à publicação.

Reversão: não rebaixar envelopes nem apagar termos. Um rollback visual precisa manter leitor/validador versão3, módulo anual e bloqueios dos comandos, para preservar a base e as declarações. Commit, push e publicação exigem autorização do candidato.

A tabela anual apresenta janeiro a dezembro. Meses anteriores ou posteriores ao plano são linhas cinza sem controles ou valores financeiros; não integram os120 meses do modelo, resumos ou encerramentos anuais. Filtros explícitos continuam aplicáveis à apresentação.

Na célula de Saque, responda primeiro se houve saque. Sim revela o registro individual; Não requer revisão/confirmação explícita de ausência, sem lançamento fictício. Clicar fora das janelas fecha sem confirmar ações. Nos editores mensais, o texto permanece como rascunho da sessão; reabrir exige nova revisão e mantém o contexto original para detectar conflitos. Cancelar continua descartando o rascunho editável (resultados indeterminados preservam a recuperação).

Saque e Aporte apresentam dois botões diretos para informar se houve movimento, antes dos valores realizados. O botão Não fica desabilitado quando há lançamentos positivos. A escolha só prepara a edição; revisão e confirmação continuam necessárias. As previsões futuras permanecem separadas destes registros.

Confirmar nos editores mensais abre uma segunda etapa da mesma janela: o formulário fica oculto e a confirmação apresenta somente os dados revisados. A seta Voltar ao preenchimento mantém os valores e invalida a aprovação preparada; é necessário revisar novamente. Nenhuma mudança é gravada ao avançar, voltar ou fechar.

Os editores de Resultado, Saque e Aporte usam uma única janela de380×260px (limitada ao viewport), com posição estável entre etapas e transições horizontais de180ms. Em Saque/Aporte, Sim substitui a pergunta pelos campos; Não mostra diretamente a revisão de ausência, sem gravar. A seta retorna uma etapa com os valores preservados. Conteúdo longo rola somente dentro da página ativa. Movimento reduzido desativa a animação.

Recuperação e espaço local: novas cópias usam compactação reversível de strings JSON (journal versão2, leitor também aceita versão1). Em Backup e recuperação, Compactar cópias de recuperação confere proprietário e conteúdo e regrava somente a chave confirmada pertencente à instância atual, sem excluir chaves, contas ou históricos. Cópias de outras sessões, pendentes e ilegíveis são preservadas integralmente. O resultado inclui skippedForeign; sem cópia própria compactável, a interface informa que nenhum espaço foi liberado e não rearma uma confirmação recusada. A operação é explícita; abrir o site não migra nada. Exporte uma cópia antes e feche outras abas do mesmo site. A capacidade do navegador continua finita. Recusa por armazenamento tem diagnóstico próprio, mantém o rascunho e exige nova revisão; conflitos e resultados indeterminados continuam bloqueados.

Dimensões atuais dos popups mensais:380×260px, limitadas ao viewport, com14px de margem interna e ações de pelo menos44px. Pergunta,preenchimento e revisão preservam essa moldura compacta. Conteúdo extenso permanece acessível pela rolagem interna da página ativa.

Auditoria de 05/11/2026: a validação dos comandos também confere a sequência efetiva disponível. Um resultado previsto não pode financiar saque realizado quando o resultado do mês ainda não foi registrado. Aberturas dependentes indisponíveis continuam desconhecidas; fórmulas, referências e limites não foram alterados.

### Confirmação mensal independente

O check confirma os registros próprios de Resultado, Saque e Aporte; não atesta um saldo ainda desconhecido. Pode ser marcado fora de ordem dentro do mesmo ano liberado. Cada novo fechamento guarda `recordsReview` versão1, com resultado, revisões dos movimentos e confirmações de ausência conferidos. Abertura, patrimônio e percentual permanecem indisponíveis se faltar a sequência anterior; completá-la recalcula os valores sem exigir um novo check. Corrigir ou reabrir setembro preserva o check de outubro; alterar outubro reabre somente outubro. Termos anuais afetados e posteriores continuam exigindo revisão.

O editor de Resultado apresenta USD e percentual derivado lado a lado, sem edição percentual. Em telas estreitas, as colunas empilham. A base do percentual é a abertura efetiva disponível e positiva; aportes do mês não entram no denominador. Leitura, digitação e revisão não gravam. O encerramento anual continua exigindo todos os meses e resumo calculável. A validação de comandos também inspeciona, sem expor ou adotar como confirmada, uma sequência de registros inteiramente preenchidos para recusar saldos negativos revelados por uma correção.

### Aparência clara

A interface oferece somente o tema claro, sem seletor de tema. Preferências escuras antigas permanecem recuperáveis, mas não são aplicadas ao abrir. Backups antigos continuam aceitos; a restauração explícita aplica o tema claro e preserva as demais preferências e rascunhos. As exportações normais usam light. A marca mantém o ícone azul à esquerda do título e a assinatura by JP Wealth.
