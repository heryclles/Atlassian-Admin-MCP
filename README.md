# Atlassian MCP for Admins

Plugin do Claude Code com ferramentas administrativas para Jira Cloud, Jira
Service Management e Jira Forms. O plugin junta duas coisas que nao existem
separadas:

- **Servidor MCP** (`src/`): cada operacao da API vira uma ferramenta.
- **Skills** (`skills/`): explicam os payloads complexos que as ferramentas
  recebem, como o JSON de design do Forms. Ferramenta que depende de skill avisa
  na propria descricao, e um teste garante que a skill existe.

## Instalar

Requer o [uv](https://docs.astral.sh/uv/) no PATH (`uv --version`). A instalacao
clona o repositorio por git: a copia instalada so tem arquivos do commit, nunca o
`.env` nem a `.venv`. Nunca adicione a pasta do repositorio como marketplace: nesse
modo o Claude Code copia a pasta inteira, com os arquivos fora do git.

### Repositorio publicado (GitHub)

O `.claude-plugin/marketplace.json` do repositorio serve de catalogo:

```bash
claude plugin marketplace add heryclles/Atlassian-Admin-MCP
claude plugin install atlassian-admin@atlassian-admin
```

### Clone local, sem remoto

O `claude plugin marketplace add` nao aceita `file://`. Crie um catalogo pequeno
fora do repositorio, cuja fonte do plugin e a URL git do clone:

```bash
M=~/.claude/marketplaces-locais/atlassian-admin-local
mkdir -p "$M/.claude-plugin"
cat > "$M/.claude-plugin/marketplace.json" <<JSON
{
  "name": "atlassian-admin-local",
  "owner": { "name": "$(git config user.name)" },
  "plugins": [
    { "name": "atlassian-admin",
      "source": { "source": "url", "url": "file://$HOME/project/atlassian-lab" } }
  ]
}
JSON
claude plugin marketplace add "$M"
claude plugin install atlassian-admin@atlassian-admin-local
```

Na primeira sessao, o `uv` cria o ambiente Python do plugin na pasta de dados dele
(`~/.claude/plugins/data/<plugin>-<marketplace>/venv`), a partir do `uv.lock`. Esse
ambiente sobrevive as atualizacoes.

## Credenciais

O plugin exige tres opcoes: `jira_url`, `jira_email` e `jira_token` (este vai
para o Keychain). Sem elas o servidor nao conecta: o `/mcp` mostra o conector
`api` como falho, e o log dele diz o que falta e qual comando rodar. Preencha num
terminal com o Claude Code, usando o nome do marketplace da instalacao, e depois
reconecte o servidor pelo `/mcp` ou abra uma sessao nova:

```
/plugin configure atlassian-admin@atlassian-admin-local
```

Conferir: `claude mcp list` deve mostrar `plugin:atlassian-admin:api ... Connected`.

## Atualizar

Depois de um commit novo, com a versao de `.claude-plugin/plugin.json` aumentada:

```bash
claude plugin marketplace update <marketplace>
claude plugin update atlassian-admin@<marketplace>
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
.venv/bin/python -m unittest discover -s tests   # sem rede: paginacao, plugin, skills
.venv/bin/python -m tests.ao_vivo                # leituras contra o site
.venv/bin/python -m tests.mcp_stdio              # o servidor pelo protocolo MCP
```

## Ferramentas

No Claude Code aparecem como `mcp__plugin_atlassian-admin_api__<nome>`.

| Grupo | Leitura | Escrita |
|---|---|---|
| Geral | `atlassian_conexao`, `atlassian_get` | `atlassian_requisicao` |
| Jira | `jira_buscar_issues`, `jira_contar_issues`, `jira_obter_issue`, `jira_listar_comentarios`, `jira_listar_projetos`, `jira_obter_projeto`, `jira_listar_campos`, `jira_listar_status`, `jira_usos_status`, `jira_listar_workflows`, `jira_usos_workflow` | |
| JSM | `jsm_listar_service_desks`, `jsm_listar_request_types`, `jsm_obter_request_type`, `jsm_listar_campos_request_type`, `jsm_listar_grupos_request_type` | `jsm_criar_request_type`, `jsm_excluir_request_type` |
| Forms | `forms_listar`, `forms_obter`, `forms_obter_do_request_type`, `forms_listar_da_issue`, `forms_obter_respostas` | `forms_criar`, `forms_salvar`, `forms_excluir` |

`atlassian_get` e `atlassian_requisicao` cobrem qualquer endpoint sem ferramenta
propria. So aceitam o site configurado e `api.atlassian.com`: o token nunca vai
para outro host.

## Skills

| Skill | Ferramentas | Conteudo |
|---|---|---|
| `atlassian-admin:forms-design` | `forms_obter`, `forms_obter_do_request_type`, `forms_criar`, `forms_salvar` | tipos de pergunta, validacao, opcoes, secoes, condicoes, layout, publicacao, fluxo seguro de edicao |
