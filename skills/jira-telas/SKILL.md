---
name: jira-telas
description: Modelo de telas do Jira company-managed (/rest/api/3/screens, /screenscheme, /issuetypescreenscheme) - projeto, esquema de tela por tipo de issue, esquema de tela, tela, abas e campos - com os endpoints, o caminho para descobrir qual tela um projeto mostra ao criar, editar ou ver uma issue, os payloads de esquemas e itens (default, create, edit, view, null), os tipos dos ids no corpo, a ordem de campos e abas e as restricoes de exclusao. Use SEMPRE antes de criar, alterar, associar ou interpretar telas, abas, esquemas de tela e esquemas de tela por tipo de issue, antes de adicionar, remover ou mover campos de uma aba, e quando o pedido for "que tela/campos aparecem no projeto X", "em que telas esta o campo Y" ou "quais projetos usam esta tela".
---

# Telas e esquemas de tela do Jira

Vale so para projetos **company-managed** (classicos). Projeto team-managed tem
telas proprias, fora destas APIs: nao aparece nas listagens e nao pode ser
associado. Todos os endpoints exigem admin do Jira; as leituras de abas e campos da
aba aceitam `projectKey` (params) para quem e so admin do projeto, desde que a tela
esteja ligada ao projeto pelos esquemas.

Chamadas: skill `atlassian-chamadas` (intencao, `limite`, `inicio`, `filtro`,
`manter`, caminho em lista, envelope das escritas).

## Endpoints

| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |
|---|---|---|---|---|
| Listar telas | atlassian_ler | `GET /rest/api/3/screens` | startAt | `id` (lista), `queryString` (trecho do nome), `scope` (GLOBAL, TEMPLATE, PROJECT), `orderBy` |
| Criar tela | atlassian_escrever | `POST /rest/api/3/screens` | nao | `{"name", "description"}`; nasce com uma aba vazia. Experimental |
| Renomear tela | atlassian_escrever | `PUT /rest/api/3/screens/{telaId}` | nao | `{"name"}` e/ou `{"description"}`. Experimental |
| Excluir tela | atlassian_excluir | `DELETE /rest/api/3/screens/{telaId}` | nao | recusa se estiver em esquema de tela ou workflow. Experimental |
| Campos que ainda cabem na tela | atlassian_ler | `GET /rest/api/3/screens/{telaId}/availableFields` | inteira | campos fora de todas as abas da tela |
| Adicionar campo a tela padrao | atlassian_escrever | `POST /rest/api/3/screens/addToDefault/{campoId}` | nao | sem corpo; aba padrao da tela padrao do site |
| Telas em que um campo esta | atlassian_ler | `GET /rest/api/3/field/{campoId}/screens` | startAt | `expand=tab` traz a aba; so campo customizado |
| Abas de varias telas | atlassian_ler | `GET /rest/api/3/screens/tabs` | startAt | `screenId`, `tabId` (listas); tamanho em `maxResult` (sem s, ate 100). Experimental |
| Abas de uma tela | atlassian_ler | `GET /rest/api/3/screens/{telaId}/tabs` | inteira | na ordem; `projectKey` opcional |
| Criar aba | atlassian_escrever | `POST /rest/api/3/screens/{telaId}/tabs` | nao | `{"name"}`; entra no fim |
| Renomear aba | atlassian_escrever | `PUT /rest/api/3/screens/{telaId}/tabs/{abaId}` | nao | `{"name"}`; so o nome e editavel |
| Excluir aba | atlassian_excluir | `DELETE /rest/api/3/screens/{telaId}/tabs/{abaId}` | nao | tira da tela os campos dela |
| Mover aba | atlassian_escrever | `POST /rest/api/3/screens/{telaId}/tabs/{abaId}/move/{posicao}` | nao | sem corpo; posicao comeca em 0 |
| Campos de uma aba | atlassian_ler | `GET /rest/api/3/screens/{telaId}/tabs/{abaId}/fields` | inteira | na ordem; pode repetir campo; `projectKey` opcional |
| Adicionar campo a aba | atlassian_escrever | `POST /rest/api/3/screens/{telaId}/tabs/{abaId}/fields` | nao | `{"fieldId"}`; entra no fim; `skipFieldAssociation` (params) |
| Remover campo da aba | atlassian_excluir | `DELETE /rest/api/3/screens/{telaId}/tabs/{abaId}/fields/{campoId}` | nao | o campo continua existindo |
| Mover campo na aba | atlassian_escrever | `POST /rest/api/3/screens/{telaId}/tabs/{abaId}/fields/{campoId}/move` | nao | `{"after"}` ou `{"position"}` |
| Listar esquemas de tela | atlassian_ler | `GET /rest/api/3/screenscheme` | startAt | `id`, `queryString`, `orderBy`; `expand=issueTypeScreenSchemes` da quem usa |
| Criar esquema de tela | atlassian_escrever | `POST /rest/api/3/screenscheme` | nao | `{"name", "description", "screens"}`; `screens.default` obrigatorio |
| Alterar esquema de tela | atlassian_escrever | `PUT /rest/api/3/screenscheme/{esquemaId}` | nao | so as chaves que mudam |
| Excluir esquema de tela | atlassian_excluir | `DELETE /rest/api/3/screenscheme/{esquemaId}` | nao | recusa se estiver em esquema de tela por tipo de issue |
| Listar esquemas de tela por tipo de issue | atlassian_ler | `GET /rest/api/3/issuetypescreenscheme` | startAt | `id`, `queryString`, `orderBy`; `expand=projects` da os projetos |
| Criar esquema de tela por tipo de issue | atlassian_escrever | `POST /rest/api/3/issuetypescreenscheme` | nao | `{"name", "description", "issueTypeMappings"}`; item `default` obrigatorio |
| Renomear esquema de tela por tipo de issue | atlassian_escrever | `PUT /rest/api/3/issuetypescreenscheme/{esquemaId}` | nao | `{"name"}` e/ou `{"description"}` |
| Excluir esquema de tela por tipo de issue | atlassian_excluir | `DELETE /rest/api/3/issuetypescreenscheme/{esquemaId}` | nao | recusa se algum projeto o usa |
| Itens (tipo de issue -> esquema de tela) | atlassian_ler | `GET /rest/api/3/issuetypescreenscheme/mapping` | startAt | `issueTypeScreenSchemeId` (lista) |
| Adicionar ou trocar itens | atlassian_escrever | `PUT /rest/api/3/issuetypescreenscheme/{esquemaId}/mapping` | nao | `{"issueTypeMappings"}`; nunca `default` |
| Trocar o item padrao | atlassian_escrever | `PUT /rest/api/3/issuetypescreenscheme/{esquemaId}/mapping/default` | nao | `{"screenSchemeId"}` |
| Remover itens | atlassian_escrever | `POST /rest/api/3/issuetypescreenscheme/{esquemaId}/mapping/remove` | nao | `{"issueTypeIds"}`; os tipos voltam ao padrao |
| Esquema de tela por tipo de issue dos projetos | atlassian_ler | `GET /rest/api/3/issuetypescreenscheme/project` | startAt | `projectId` (lista, ids numericos) |
| Associar esquema a projeto | atlassian_escrever | `PUT /rest/api/3/issuetypescreenscheme/project` | nao | `{"issueTypeScreenSchemeId", "projectId"}` |
| Projetos de um esquema de tela por tipo de issue | atlassian_ler | `GET /rest/api/3/issuetypescreenscheme/{esquemaId}/project` | startAt | `query`: trecho do nome ou chave do projeto |

Apoio (skill `jira-issues`): `GET /rest/api/3/project/{projetoChave}` (id e
`issueTypes` do projeto), `GET /rest/api/3/issuetype` e
`GET /rest/api/3/issuetype/project` com `projectId` (ids de tipo de issue),
`GET /rest/api/3/field` (ids de campo, ex. `duedate`, `customfield_10000`).

## A cadeia

```
Projeto
 └─ 1 esquema de tela por tipo de issue          (issuetypescreenscheme)
     ├─ item "default" ─> esquema de tela         (tipos sem item proprio)
     └─ item <tipo>    ─> esquema de tela         (screenscheme)
                            ├─ default ─> tela    (vale para operacao sem tela propria)
                            ├─ create  ─> tela    (criar issue)
                            ├─ edit    ─> tela    (editar issue)
                            └─ view    ─> tela    (ver issue)
                                           └─ abas (ordem) ─> campos (ordem)
```

- Um projeto tem exatamente um esquema de tela por tipo de issue. Varios projetos
  podem dividir o mesmo esquema: alterar o esquema, ou uma tela dele, muda todos.
- Esse e o unico caminho de uma tela ate os projetos.
- Transicoes de workflow tambem usam telas (tela de transicao), fora dessa cadeia.
  Por isso uma tela pode estar em uso sem aparecer em nenhum esquema.
- Tela define **onde** o campo aparece. Obrigatorio e oculto vem da configuracao de
  campo ou do esquema de campos (skills `jira-config-campos` e
  `jira-esquemas-campos`): um campo na tela pode continuar escondido por elas.

## Qual tela o projeto mostra

Para "que campos aparecem ao criar um <tipo> no projeto SUP":

```
1. atlassian_ler(intencao="Ler o id e os tipos de issue do projeto SUP",
                 caminho="/rest/api/3/project/SUP",
                 manter=["id", "key", "issueTypes.id", "issueTypes.name"])

2. atlassian_ler(intencao="Ver o esquema de tela por tipo de issue do projeto SUP",
                 caminho="/rest/api/3/issuetypescreenscheme/project",
                 params={"projectId": ["10000"]})
   -> values[].issueTypeScreenScheme.id (e projectIds)

3. atlassian_ler(intencao="Ler os itens do esquema de tela por tipo de issue 10100",
                 caminho="/rest/api/3/issuetypescreenscheme/mapping",
                 params={"issueTypeScreenSchemeId": ["10100"]})
   -> item do tipo; sem item proprio, vale issueTypeId "default". Da o screenSchemeId

4. atlassian_ler(intencao="Ler as telas do esquema de tela 10200",
                 caminho="/rest/api/3/screenscheme", params={"id": ["10200"]})
   -> screens.create; se nao houver, vale screens.default

5. atlassian_ler(intencao="Listar as abas da tela 10300",
                 caminho="/rest/api/3/screens/10300/tabs")

6. atlassian_ler(intencao="Ler os campos de todas as abas da tela 10300",
                 caminho=["/rest/api/3/screens/10300/tabs/10400/fields",
                          "/rest/api/3/screens/10300/tabs/10401/fields"])
```

- Passo 6: um caminho por aba (ate 20), numa chamada so; a resposta e
  `{caminho: lista de campos}` na ordem das abas do passo 5.
- Ha abas com milhares de campos (inclusive o mesmo campo repetido), que passam do
  teto de tamanho. Se o passo 6 for recusado por tamanho, repita com `limite=200`,
  `manter=["id", "name"]` e siga `proximo_inicio` de cada aba.
- O nome da tela: `GET /rest/api/3/screens` com `params={"id": ["10300"]}`.
- Tela que nao existe nao da 404 nessa listagem: volta `values` vazio. Trate
  `values: []` como "tela nao encontrada".
- Para ver a tela inteira de varias telas de uma vez, `GET /rest/api/3/screens/tabs`
  com `params={"screenId": [...], "maxResult": 100}` da as abas de todas (cada item
  com `screenId`, `tabId`, `tabName`); depois os campos por caminho em lista.

## Abas e campos grandes

- Abas, campos da aba e `availableFields` vem inteiros, sem paginacao. Para fatiar,
  `limite` e `inicio`: a fatia volta com `total`, `inicio` e `proximo_inicio`; se
  `proximo_inicio` vier, chame de novo com ele.

```
atlassian_ler(intencao="Ler os 200 primeiros campos da aba 10400 da tela 10300",
              caminho="/rest/api/3/screens/10300/tabs/10400/fields",
              limite=200, inicio=0)
```

- A aba pode repetir o mesmo campo varias vezes em sequencia. Venha como vier: ao
  contar campos, conte ids distintos e, se houver repeticao, avise o usuario, porque
  nao e o normal de uma tela.
- `availableFields` lista o que ainda cabe na tela (campos fora de todas as abas).
  Para achar um campo nela, `filtro={"id": ["customfield_10000"]}` (igualdade
  exata; trecho do nome nao funciona, leia a lista com `manter=["id", "name"]`).
- `GET /rest/api/3/field/{campoId}/screens` so aceita campo customizado
  (`customfield_...`); campo do sistema (`summary`, `duedate`) da 404. Use
  `params={"expand": "tab"}` para saber a aba de cada tela.

## Quem usa o que

| Pergunta | Caminho |
|---|---|
| Projetos que usam um esquema de tela por tipo de issue | `GET /rest/api/3/issuetypescreenscheme/{esquemaId}/project` (com `limite` para todas as paginas) |
| Projetos que usam um esquema de tela | `GET /rest/api/3/screenscheme` com `params={"id": [esquemaId], "expand": "issueTypeScreenSchemes"}` da os esquemas por tipo de issue; para cada um, a linha acima |
| Esquemas de tela que usam uma tela | `GET /rest/api/3/screenscheme` com `filtro={"screens.default": ["10300"]}`, e de novo com `screens.create`, `screens.edit` e `screens.view` (as chaves do filtro somam como E, entao uma chamada por operacao); dai seguir a linha acima. Telas de transicao nao aparecem assim |
| Telas em que um campo esta | `GET /rest/api/3/field/{campoId}/screens` com `expand=tab` |
| Esquemas de tela por tipo de issue com os projetos | `GET /rest/api/3/issuetypescreenscheme` com `params={"expand": "projects"}`; use `limite` pequeno ou `manter` |

## Payloads e tipos

Quem monta o corpo e o Claude: siga o tipo de cada id.

| Corpo | Tipo dos ids |
|---|---|
| `screens` no POST de esquema de tela | inteiro (`10000`) |
| `screens` no PUT de esquema de tela | texto (`"10000"`) ou `null` |
| `issueTypeMappings`: `issueTypeId`, `screenSchemeId` | texto |
| `screenSchemeId` do item padrao | texto |
| `issueTypeIds` da remocao | lista de texto |
| `issueTypeScreenSchemeId`, `projectId` da associacao | texto |
| `fieldId`, `after` | id do campo em texto (`"summary"`, `"customfield_10000"`) |

### Esquema de tela (`screens`)

Chaves em ingles, valores com o id da tela:

```json
{ "default": 10000, "create": 10001, "edit": 10002, "view": 10000 }
```

- Criar: corpo `{"name": "...", "description": "...", "screens": {...}}`, com
  `default` obrigatorio; as outras operacoes sao opcionais. Nome unico, ate 255
  caracteres. Devolve o id do esquema.
- Alterar (PUT): mande so as operacoes que mudam, dentro de `screens`. `null` em
  `create`, `edit` ou `view` tira a tela da operacao (volta a valer a `default`).
  `default` nunca pode ser `null`. Chave ausente fica como esta.

```json
{ "create": "10003", "view": null }
```

```
atlassian_escrever(intencao="Trocar a tela de criacao do esquema de tela 10200 para a tela 10003 e tirar a tela de visualizacao",
                   metodo="PUT", caminho="/rest/api/3/screenscheme/10200",
                   corpo={"screens": {"create": "10003", "view": null}})
```

### Itens do esquema de tela por tipo de issue (`issueTypeMappings`)

Criar o esquema: o item `"default"` e obrigatorio.

```json
[
  { "issueTypeId": "default", "screenSchemeId": "10000" },
  { "issueTypeId": "10001", "screenSchemeId": "10002" }
]
```

```
atlassian_escrever(intencao="Criar o esquema de tela por tipo de issue Suporte - telas",
                   metodo="POST", caminho="/rest/api/3/issuetypescreenscheme",
                   corpo={"name": "Suporte - telas", "issueTypeMappings": [<itens acima>]})
```

- Adicionar ou trocar itens (`PUT .../{esquemaId}/mapping`): so tipos de issue
  reais, nunca `"default"`. Corpo:
  `{"issueTypeMappings": [{"issueTypeId": "10001", "screenSchemeId": "10002"}]}`.
- Trocar o padrao (`PUT .../{esquemaId}/mapping/default`):
  `{"screenSchemeId": "10000"}`; vale para os tipos sem item proprio.
- Remover itens (`POST .../{esquemaId}/mapping/remove`):
  `{"issueTypeIds": ["10001"]}`; esses tipos passam a usar o padrao.
- Renomear (`PUT .../{esquemaId}`): so `name` e `description`; os itens tem os
  endpoints acima.
- Associar a projeto (`PUT /rest/api/3/issuetypescreenscheme/project`):
  `{"issueTypeScreenSchemeId": "10100", "projectId": "10000"}`. O projectId e o id
  numerico (de `GET /rest/api/3/project/{projetoChave}`), em texto. Muda as telas de
  todas as issues do projeto.

## Telas, abas e campos

- Criar tela: `{"name": "SUP - Criar", "description": "..."}`. Nome unico, ate 255
  caracteres. A API cria junto uma aba padrao vazia.
- Renomear tela: `PUT /rest/api/3/screens/{telaId}` com `name` e/ou `description`.
  Abas e campos tem endpoints proprios.
- Criar aba: `{"name": "Detalhes"}` (nome unico na tela, ate 255 caracteres); entra
  no fim. Renomear: o mesmo corpo no PUT; a API so edita o nome.
- Adicionar campo: `{"fieldId": "customfield_10000"}`; entra no fim da aba. Um campo
  so pode estar uma vez na tela (confira `availableFields`). Por padrao, adicionar o
  campo a aba tambem atualiza a configuracao de campo dos projetos ligados a tela,
  para ele aparecer na issue; `params={"skipFieldAssociation": true}` so poe na aba
  (o campo nao aparece na issue ate a associacao ser feita a parte).
- Remover campo: `DELETE .../fields/{campoId}`. O campo continua existindo no Jira
  e nas outras telas.

## Ordem de abas e campos

- Abas: `POST /rest/api/3/screens/{telaId}/tabs/{abaId}/move/{posicao}`, sem corpo;
  posicao comeca em 0 (0 = primeira).
- Campos, dentro da mesma aba: `POST .../fields/{campoId}/move` com
  - `{"after": "summary"}`: id do campo apos o qual ele fica, ou
  - `{"position": "First"}`: `First`, `Last`, `Earlier` (sobe uma), `Later`
    (desce uma).
  Com os dois, a API usa `after`. Nao ha como pedir "antes de X": use `after` com o
  campo anterior a X, ou `First`.

```
atlassian_escrever(intencao="Colocar o campo Data limite (duedate) logo depois de Resumo na aba 10400 da tela 10300",
                   metodo="POST", caminho="/rest/api/3/screens/10300/tabs/10400/fields/duedate/move",
                   corpo={"after": "summary"})
```

- Trocar de aba: remover da atual e adicionar na outra (entra no fim; depois
  mover).

## Restricoes

| Acao | A API recusa quando |
|---|---|
| Excluir tela | esta em esquema de tela, em transicao de workflow ou em rascunho de workflow |
| Excluir esquema de tela | esta em algum esquema de tela por tipo de issue |
| Excluir esquema de tela por tipo de issue | algum projeto o usa |
| Nomes de tela e de esquemas | ja existem (sao unicos) ou passam de 255 caracteres |
| Itens e telas | sao de projeto team-managed (so company-managed e aceito) |

Excluir tela, aba ou esquema nao tem desfazer. Excluir uma aba tira da tela os
campos dela; excluir esquema nao exclui as telas nem os esquemas de tela; fora
isso, nada e excluido em cascata. Todas as escritas respondem 204 sem corpo, menos
criar (201 ou 200 com o id) e as de aba e campo (200 com o objeto).

## Fluxo seguro de edicao

1. Antes de alterar uma tela ou esquema, veja quem usa (tabela "Quem usa o que") e
   diga ao usuario quais projetos serao afetados.
2. Para mudar um projeto so, sem mexer nos outros que dividem o esquema: crie uma
   tela ou esquema novo (copiando a composicao atual), ajuste e associe so a esse
   projeto com `PUT /rest/api/3/issuetypescreenscheme/project`.
3. Uma escrita por vez, com `intencao` especifica e confirmacao do usuario.
4. Depois de salvar, leia de novo (abas e campos da tela, itens do esquema) e
   confira o resultado.
