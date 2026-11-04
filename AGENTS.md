# Planejamento Patrimonial

Projeto independente do JP Wealth. Não modificar o repositório de origem. Motor financeiro e camada de comandos copiados com hashes em docs/source-provenance.json; preservar fórmulas/limites/precisão e confirmação. Marca pública própria. Dados apenas neste navegador; nunca publicar dados/segredos reais. Não incluir outros módulos, analytics ou sincronização. Câmbio externo recebe somente moeda/data.

Adaptador local deve recusar conflitos/corrupção/quota sem adotar RAM; resultado desconhecido bloqueia comandos até recuperação explícita. Nunca limpar localStorage nem substituir erros por padrões. Backup próprio versionado, validado inteiro antes de substituir, sem autorização automática de rascunhos.

Verificar com node tools/check.js e node tools/test.js; testes de navegador descritos no README. Medir320px/temas/foco/zoom nativo200%; artefatos em outputs, dados sintéticos somente. Não afirmar revisão independente sem execução.

Publicação pública solicitada via Sites. Commit/push aguardam autorização específica do candidato pronto; nenhuma operação Git no JP Wealth. Não alterar plataforma de acesso/CI/controles incidentalmente.
