# Atlassian MCP for Admins

Plugin do Claude Code para administrar Jira Cloud, Jira Service Management e Jira
Forms pelas APIs Atlassian. O plugin junta duas coisas que nao existem separadas:

- **Servidor MCP** (`src/`): quatro ferramentas genericas, divididas por risco, que
  chamam qualquer endpoint do site configurado.
- **Skills** (`skills/`): uma por area da API, com a tabela de endpoints, os
  payloads, os tipos dos ids, as armadilhas e o fluxo seguro de alteracao. E nelas
  que fica o conhecimento de cada endpoint.

## Instalar

Requer o [uv](https://docs.astral.sh/uv/) no PATH (`uv --version`). A instalacao
clona o repositorio por git: a copia instalada so tem arquivos do commit, nunca o
`.env` nem a `.venv`. Instale sempre pelo repositorio publicado no GitHub, cujo
`.claude-plugin/marketplace.json` serve de catalogo. Nunca adicione um clone local
como marketplace: nesse modo o Claude Code copia a pasta inteira, com os arquivos
fora do git.

```bash
claude plugin marketplace add heryclles/Atlassian-Admin-MCP
claude plugin install atlassian-admin@atlassian-admin
```

Na primeira sessao, o `uv` cria o ambiente Python do plugin na pasta de dados dele
(`~/.claude/plugins/data/atlassian-admin-atlassian-admin/venv`), a partir do `uv.lock`. Esse
ambiente sobrevive as atualizacoes.

## Credenciais

O servidor precisa da URL do site, do e-mail da conta administradora e de um
[API token](https://id.atlassian.com/manage-profile/security/api-tokens). O metodo
padrao, que funciona igual no Claude Code CLI e na aba Code do Claude Desktop, e um
arquivo no seu usuario:

```bash
mkdir -p ~/.config/atlassian-admin
cat > ~/.config/atlassian-admin/.env <<'ENV'
JIRA_URL=https://empresa.atlassian.net
JIRA_EMAIL=admin@empresa.com
JIRA_TOKEN=cole-o-token-aqui
ENV
chmod 600 ~/.config/atlassian-admin/.env
```

Troque os tres valores (URL sem barra no final) e abra uma sessao nova. O arquivo
fica fora do repositorio e da copia instalada: nao vai para o git, vale para
qualquer forma de instalacao e sobrevive as atualizacoes do plugin.

Conferir: `claude mcp list` deve mostrar `plugin:atlassian-admin:api ... Connected`.
Sem credencial o servidor nao sobe: o conector `api` aparece como falho, e o log
dele diz o que falta e o caminho do arquivo. Credencial errada (token vencido) so
aparece ao usar uma ferramenta; `atlassian_conexao` confere a conexao e mostra em
qual site e com qual conta o plugin esta.

A aba Chat do Claude (web e Desktop) nao roda servidor MCP local: la o plugin so
carrega a skill. Veja a [tabela de componentes por app](https://claude.com/docs/plugins/platform-support).

### Outras fontes

O servidor usa o primeiro valor preenchido, nesta ordem. Na pratica, use so o
arquivo acima; as outras existem para casos especificos:

| Ordem | Fonte | Quando usar |
|---|---|---|
| 1 | Opcoes do plugin, via `/plugin configure atlassian-admin@atlassian-admin` (token no Keychain) | So no terminal do Claude Code; util para apontar uma instalacao para outro site, porque vence o arquivo |
| 2 | `.env` na raiz do repositorio | Desenvolvimento e testes (secao [Desenvolver](#desenvolver)) |
| 3 | `~/.config/atlassian-admin/.env` | **Padrao** |

## Atualizar

Depois de um commit publicado no GitHub, com a versao de `.claude-plugin/plugin.json`
aumentada:

```bash
claude plugin marketplace update atlassian-admin
claude plugin update atlassian-admin@atlassian-admin
```

A mudanca vale na proxima sessao.

## Desenvolver

Os testes rodam no repositorio, com a `.venv` local e as credenciais do `.env`
(`cp .env.example .env`), que nunca vai para o plugin instalado:

```bash
uv sync
```

## Testar

```bash
.venv/bin/python -m unittest discover -s tests   # sem rede: paginacao, ferramentas, plugin, skills
.venv/bin/python -m tests.ao_vivo                # leituras contra o site e GET dos endpoints das skills
.venv/bin/python -m tests.mcp_stdio              # o servidor pelo protocolo MCP
```

## Ferramentas

No Claude Code aparecem como `mcp__plugin_atlassian-admin_api__<nome>`.

| Ferramenta | Faz | Pede confirmacao |
|---|---|---|
| `atlassian_conexao` | site, usuario autenticado e cloudId | nao |
| `atlassian_ler` | GET em qualquer endpoint e os POST que so consultam (busca JQL, contagem, leituras em lote) | nao |
| `atlassian_escrever` | POST, PUT, PATCH | sim |
| `atlassian_excluir` | DELETE | sim |

- **intencao:** as tres genericas exigem uma frase em portugues dizendo o que a
  chamada faz. E o que aparece no transcript e no pedido de confirmacao.
- **leitura:** `atlassian_ler` segue a paginacao da API sozinha (`limite`, com
  `continuar` para o resto), filtra por igualdade (`filtro`), recorta a resposta
  (`manter`), le varios caminhos numa chamada e recusa resposta grande demais com a
  orientacao de pedir menos.
- **host:** so o site configurado e `api.atlassian.com`; o token nunca vai para
  outro host.

O Claude Code casa permissao de ferramenta MCP so pelo nome. Para nao confirmar
leituras, libere as duas de leitura no `settings.json` e mantenha a confirmacao nas
de escrita e exclusao:

```json
{"permissions": {"allow": ["mcp__plugin_atlassian-admin_api__atlassian_ler",
                           "mcp__plugin_atlassian-admin_api__atlassian_conexao"]}}
```

## Skills

As instrucoes do servidor dizem qual skill carregar para cada prefixo de caminho.

| Skill | Area |
|---|---|
| `atlassian-admin:atlassian-chamadas` | uso das ferramentas: intencao, paginacao, filtro, manter, varios caminhos, teto de tamanho, status das escritas, tarefas assincronas, erros |
| `atlassian-admin:jira-issues` | busca e contagem JQL, issue, comentarios, historico, projetos, campos, tipos de issue, usuarios e grupos |
| `atlassian-admin:jira-status-workflows` | status, workflows, esquemas de workflow e quem usa cada um |
| `atlassian-admin:jira-telas` | telas, abas, campos da aba, esquemas de tela e esquemas de tela por tipo de issue; qual tela o projeto mostra |
| `atlassian-admin:jira-prioridades` | prioridades, esquemas de prioridade, mapeamentos in/out, tarefas assincronas |
| `atlassian-admin:jira-config-campos` | configuracao de campo e esquema de configuracao de campo (API antiga) |
| `atlassian-admin:jira-esquemas-campos` | esquemas de campos (API nova, beta), lotes com resultado parcial (207) |
| `atlassian-admin:jira-notificacoes` | esquemas de notificacao, eventos, destinatarios e papeis de projeto |
| `atlassian-admin:jsm-request-types` | service desks, request types, campos, grupos, filas e SLAs |
| `atlassian-admin:forms-design` | templates de formulario: JSON de design, publicacao no portal, formulario do request type |
| `atlassian-admin:forms-respostas` | formularios anexados a issues: respostas, status, visibilidade, dados externos, anexos |
