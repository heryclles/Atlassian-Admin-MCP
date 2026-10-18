---
name: jira-prioridades
description: Modelo de prioridades e esquemas de prioridade do Jira (/rest/api/3/priority e /rest/api/3/priorityscheme) - prioridade global com ordem e icone, esquema com subconjunto de prioridades e padrao, projeto ligado a um esquema, esquema padrao do site - com os corpos de criar, editar, reordenar e excluir prioridades, criar e alterar esquemas (ids inteiros, add/remove aninhados), mover projetos entre esquemas, o POST de consulta /priorityscheme/mappings e os mapeamentos "in" e "out" que migram as issues. Use SEMPRE antes de criar, alterar ou excluir prioridades e esquemas de prioridade, antes de qualquer POST ou PUT em /priorityscheme, e quando o pedido for "que prioridades o projeto X usa" ou "trocar o esquema de prioridade do projeto".
---

# Prioridades e esquemas de prioridade do Jira

Todas as escritas exigem admin do Jira. Ids de prioridade, esquema e projeto sao
numericos: no caminho vao como texto; no corpo, o tipo muda por endpoint (secao
"Tipos no corpo"). Os endpoints de esquema de prioridade estao marcados como
experimentais na doc da Atlassian.

## Endpoints

| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |
|---|---|---|---|---|
| Listar prioridades na ordem global | atlassian_ler | `GET /rest/api/3/priority/search` | startAt | params id, projectId, priorityName, onlyDefault; expand=schemes traz ate 15 esquemas por prioridade |
| Obter prioridade | atlassian_ler | `GET /rest/api/3/priority/{prioridadeId}` | nao | |
| Criar prioridade | atlassian_escrever | `POST /rest/api/3/priority` | nao | 201 com id; nasce no fim da ordem e fora de todo esquema |
| Editar prioridade | atlassian_escrever | `PUT /rest/api/3/priority/{prioridadeId}` | nao | 204; global, muda em todos os esquemas |
| Excluir prioridade | atlassian_excluir | `DELETE /rest/api/3/priority/{prioridadeId}` | nao | assincrona: o 303 ja vem seguido e a resposta e a tarefa; 409 se ja houver exclusao em andamento |
| Reordenar prioridades | atlassian_escrever | `PUT /rest/api/3/priority/move` | nao | 204; ordem global |
| Padrao global (legado) | atlassian_escrever | `PUT /rest/api/3/priority/default` | nao | 204; id null apaga; o que vale no projeto e o padrao do esquema |
| Listar esquemas | atlassian_ler | `GET /rest/api/3/priorityscheme` | startAt | params schemeId, schemeName, priorityId, onlyDefault=true, orderBy, expand=priorities,projects |
| Criar esquema | atlassian_escrever | `POST /rest/api/3/priorityscheme` | nao | 201 com id; 202 com task quando migra issues de projetos |
| Alterar esquema | atlassian_escrever | `PUT /rest/api/3/priorityscheme/{esquemaId}` | nao | 202 com priorityScheme e task; 409 enquanto outra tarefa do esquema roda |
| Excluir esquema | atlassian_excluir | `DELETE /rest/api/3/priorityscheme/{esquemaId}` | nao | 204; so esquema sem projetos |
| Prioridades de um esquema | atlassian_ler | `GET /rest/api/3/priorityscheme/{esquemaId}/priorities` | startAt | na ordem global (sequence) |
| Prioridades fora de um esquema | atlassian_ler | `GET /rest/api/3/priorityscheme/priorities/available` | startAt | params schemeId (obrigatorio), query, exclude |
| Projetos de um esquema | atlassian_ler | `GET /rest/api/3/priorityscheme/{esquemaId}/projects` | startAt | params projectId (confere se esta no esquema), query (nome do projeto) |
| Prioridades a mapear numa mudanca | atlassian_ler | `POST /rest/api/3/priorityscheme/mappings` | startAt | POST de consulta, nao altera nada; startAt e maxResults vao no corpo; mande priorities e projects mesmo vazios (sem projects da 500) |
| Tarefa de migracao ou exclusao | atlassian_ler | `GET /rest/api/3/task/{tarefaId}` | nao | status ENQUEUED, RUNNING, COMPLETE, FAILED, CANCELLED, DEAD |
| Contar issues de uma prioridade | atlassian_ler | `POST /rest/api/3/search/approximate-count` | nao | corpo com jql `priority = <id>` |

## O modelo

```
Prioridades do site (globais, ordem unica: sequence 1 = mais alta)
 └─ Esquema de prioridade = subconjunto dessas prioridades + defaultPriorityId
     └─ Projetos (cada projeto usa exatamente 1 esquema)

Esquema padrao do site (isDefault true): vale para projetos novos e para os
que saem de um esquema.
```

- Prioridade e global: renomear, trocar cor ou icone muda em todos os esquemas.
- A ordem e global (`PUT /rest/api/3/priority/move`); o esquema so escolhe quais
  entram, nao reordena. `sequence` nas listas de esquema e essa ordem global.
- O padrao que vale num projeto e o `defaultPriorityId` do esquema dele. O padrao
  global (`PUT /rest/api/3/priority/default`, `isDefault` da prioridade) e legado,
  marcado como obsoleto pela Atlassian.
- O esquema padrao do site se acha com `onlyDefault=true` em
  `GET /rest/api/3/priorityscheme` (vem com `isDefault` true). Nao confiar no nome:
  um esquema chamado "Default priority scheme" pode nao ser o padrao.
- Prioridade nova nao entra em esquema nenhum: adicione pelo PUT do esquema com
  `priorities.add`.

## Leituras

```
atlassian_ler(intencao="Listar as prioridades do site na ordem global",
              caminho="/rest/api/3/priority/search", limite=200,
              manter=["values.id", "values.name", "values.statusColor", "values.avatarId"])

atlassian_ler(intencao="Achar o esquema de prioridade padrao do site, com suas prioridades",
              caminho="/rest/api/3/priorityscheme",
              params={"onlyDefault": "true", "expand": "priorities"})
```

| Pergunta | Como |
|---|---|
| Prioridades do site, na ordem | `GET /rest/api/3/priority/search` com `limite` |
| Em quais esquemas esta uma prioridade | `GET /rest/api/3/priority/search` com `params={"id": ["<id>"], "expand": "schemes"}` (ate 15) ou `GET /rest/api/3/priorityscheme` com `params={"priorityId": [<id>]}` |
| Prioridades de um esquema | `GET /rest/api/3/priorityscheme/{esquemaId}/priorities` com `limite` |
| Prioridades que podem entrar num esquema | `GET /rest/api/3/priorityscheme/priorities/available` com `params={"schemeId": "<id>"}` |
| Projetos de um esquema | `GET /rest/api/3/priorityscheme/{esquemaId}/projects` com `limite` |
| Esquema de um projeto | abaixo |
| Prioridades que um projeto oferece | `GET /rest/api/3/priority/search` com `params={"projectId": ["<id>"]}` |
| Issues com uma prioridade | `POST /rest/api/3/search/approximate-count` com `corpo={"jql": "priority = <id>"}` |

Esquema de um projeto: `GET /rest/api/3/priorityscheme` nao filtra por projeto. Pegue
o `id` numerico do projeto (`GET /rest/api/3/project/{projetoChave}`), liste os
esquemas (`manter=["values.id", "values.name"]`) e consulte os projetos de todos de
uma vez com o caminho em lista e `projectId`: o esquema cujo `total` vier 1 e o do
projeto.

```
atlassian_ler(intencao="Descobrir qual esquema de prioridade o projeto 10200 usa",
              caminho=["/rest/api/3/priorityscheme/10100/projects",
                       "/rest/api/3/priorityscheme/10101/projects"],
              params={"projectId": [10200]}, manter=["total", "values.key"])
```

Com `expand=priorities,projects` na lista de esquemas, cada esquema traz so a
primeira pagina de cada lista (com `total`); use limite pequeno (ex. 10), porque cada
esquema pode trazer 50 projetos. O resto sai nos endpoints proprios.

## Tipos no corpo

| Corpo | Campo | Tipo |
|---|---|---|
| Criar e editar prioridade | `avatarId` | inteiro |
| Reordenar | `ids`, `after` | texto |
| Padrao global | `id` | texto ou null |
| Criar esquema | `priorityIds`, `projectIds` | lista de inteiros |
| Criar e alterar esquema | `defaultPriorityId` | inteiro |
| Alterar esquema | `priorities.add.ids`, `priorities.remove.ids`, `projects.add.ids`, `projects.remove.ids` | lista de inteiros |
| Consulta de mapeamento | `schemeId`, `startAt`, `maxResults`, listas de `priorities` e `projects` | inteiros |
| Mapeamentos | chave = prioridade antiga | texto |
| Mapeamentos | valor = prioridade nova | inteiro |

## Criar e editar prioridade

```
atlassian_escrever(intencao="Criar a prioridade Critica, vermelha, com o icone da prioridade Highest",
                   metodo="POST", caminho="/rest/api/3/priority",
                   corpo={"name": "Critica", "statusColor": "#d04437", "avatarId": 10500,
                          "description": "Parada total do servico"})
```

- `name` e `statusColor` sao obrigatorios na criacao; no PUT, mande so o que muda
  (ao menos um de `name`, `statusColor`, `avatarId`, `description`).
- `statusColor`: hexadecimal de 3 ou 6 digitos (`"#d04437"`).
- `avatarId`: o icone. Reaproveite o `avatarId` de uma prioridade existente com o
  icone desejado (`GET /rest/api/3/priority/search`). O antigo `iconUrl` foi
  descontinuado pela Atlassian em marco de 2025: nao envie (e nunca junto com
  `avatarId`).
- `name`: unico no site, ate 60 caracteres.
- A prioridade nasce no fim da ordem; o move coloca no lugar: `ids` (texto) na ordem
  desejada e `after` (id fora de `ids`) ou `position` (`First`/`Last`).

```
atlassian_escrever(intencao="Colocar a prioridade Critica (10006) no topo da ordem global",
                   metodo="PUT", caminho="/rest/api/3/priority/move",
                   corpo={"ids": ["10006"], "position": "First"})
```

## Criar e alterar esquema

Criar (`POST /rest/api/3/priorityscheme`): `name`, `priorityIds` e
`defaultPriorityId` obrigatorios; `defaultPriorityId` tem de estar em `priorityIds`.
`projectIds` ja associa os projetos (e tira cada um do esquema anterior).

```
{"name": "Suporte", "description": "Prioridades do suporte",
 "priorityIds": [10000, 10001, 10002], "defaultPriorityId": 10001,
 "projectIds": [10200],
 "mappings": {"in": {"10007": 10001}}}
```

Alterar (`PUT /rest/api/3/priorityscheme/{esquemaId}`): mande so o que muda. As
listas sao aninhadas em `add`/`remove`, cada uma com `ids`:

```
{"name": "Suporte N2",
 "defaultPriorityId": 10000,
 "priorities": {"add": {"ids": [10006]}, "remove": {"ids": [10004]}},
 "projects": {"add": {"ids": [10200]}, "remove": {"ids": [10300]}},
 "mappings": {"in": {"10004": 10003, "10007": 10001}, "out": {"10006": 10002}}}
```

A resposta (202) traz `priorityScheme` e `task`. Em criacao com projetos que migram
issues, o 202 traz `id` e `task`.

## Mapeamentos: migrar as issues

Quando uma mudanca deixa issues com prioridade que o esquema nao tera, a API exige
dizer para qual prioridade cada uma vai. Formato (chave = prioridade antiga, texto;
valor = prioridade nova, numero):

```json
{"in": {"10002": 10000, "10005": 10001}, "out": {"10001": 10005}}
```

| Mudanca no esquema | Exige | Chave (antiga) | Valor (nova) |
|---|---|---|---|
| Adicionar prioridades | nada | | |
| Remover prioridades | `in` | prioridade removida | prioridade que **fica** no esquema |
| Adicionar projetos | `in` | prioridade usada no esquema atual do projeto e ausente neste | prioridade **deste** esquema |
| Remover projetos | `out` | prioridade deste esquema ausente no esquema padrao do site | prioridade do **esquema padrao do site** |

Na criacao so existe `in` (para os `projectIds`); `out` e so de alteracao.

A API recusa (400) mapeamento faltando, sobrando ou apontando para prioridade fora
do lugar certo, e a mensagem lista os ids. Mande so as chaves exigidas.

### Descobrir as chaves de `in`

`POST /rest/api/3/priorityscheme/mappings` so calcula (vai por `atlassian_ler` com
`corpo`). Mande as mesmas listas que irao para a alteracao, com ids inteiros; a
resposta lista (paginada, `values`) as prioridades que precisam de chave em `in`.
Nao cobre remocao de projetos: `out` se compara a mao (prioridades do esquema que
nao estao no esquema padrao do site).

```
{"schemeId": 10100, "startAt": 0, "maxResults": 50,
 "priorities": {"add": [10006], "remove": [10004]},
 "projects": {"add": [10200]}}
```

Aqui as listas sao planas (`"remove": [10004]`), sem o `ids` do PUT.

Armadilha: mande sempre os dois objetos, `priorities` (com `add` e `remove`) e
`projects` (com `add`), mesmo vazios. Sem `projects`, a API responde 500
(NullPointerException em getProjects) em vez de calcular. Corpo seguro para so
remover uma prioridade:

```
{"schemeId": 10100, "startAt": 0, "maxResults": 50,
 "priorities": {"add": [], "remove": [10004]},
 "projects": {"add": []}}
```

## Fluxo seguro de alteracao de esquema

1. Ler o estado: prioridades e projetos do esquema
   (`/priorityscheme/{esquemaId}/priorities` e `/projects`); se houver remocao de
   projetos, as prioridades do esquema padrao (`onlyDefault=true`,
   `expand=priorities`).
2. Descobrir as chaves de `in` com o POST de consulta `/priorityscheme/mappings`
   (nao altera nada; corpo sempre com `priorities` e `projects`, mesmo vazios).
   Cada prioridade devolvida precisa de uma chave em `in`. Para
   `out`, comparar a mao.
3. Mostrar ao usuario o plano (o que entra, sai e para onde vai cada prioridade) e
   pedir confirmacao: a migracao altera issues de verdade.
4. `PUT /rest/api/3/priorityscheme/{esquemaId}` com as mudancas e `mappings`.
5. A resposta traz `task`; acompanhar em `GET /rest/api/3/task/{tarefaId}` ate
   `COMPLETE` (ou `FAILED`/`DEAD`, que se reporta com `message` e `result`). Enquanto
   ela roda, nova alteracao no mesmo esquema da 409.

Exemplo: esquema 10100 perde a prioridade 10004 (issues vao para 10003) e recebe o
projeto 10200, cujo esquema atual usa 10007 (issues vao para 10001):

```
atlassian_ler(intencao="Calcular quais prioridades precisam de mapeamento ao tirar 10004 e incluir o projeto 10200 no esquema 10100",
              caminho="/rest/api/3/priorityscheme/mappings",
              corpo={"schemeId": 10100, "startAt": 0, "maxResults": 50,
                     "priorities": {"add": [], "remove": [10004]}, "projects": {"add": [10200]}},
              limite=100)

atlassian_escrever(intencao="Tirar a prioridade 10004 do esquema 10100 e incluir o projeto 10200, migrando as issues",
                   metodo="PUT", caminho="/rest/api/3/priorityscheme/10100",
                   corpo={"priorities": {"remove": {"ids": [10004]}},
                          "projects": {"add": {"ids": [10200]}},
                          "mappings": <abaixo>})
```

```json
{"in": {"10004": 10003, "10007": 10001}}
```

## Mover um projeto de esquema

Nao ha "associar": o projeto entra no esquema novo pelo PUT dele com
`"projects": {"add": {"ids": [<projeto>]}}` e `mappings.in`, e sai sozinho do
anterior. Remover o projeto de um esquema (`projects.remove`) o devolve ao esquema
padrao do site (com `out`).

## Excluir

- **Esquema**: so sem projetos. Tire os projetos antes (`projects.remove`, ou
  `projects.add` em outro esquema); as prioridades continuam.
- **Prioridade**: global e assincrona (devolve a tarefa). A documentacao da API nao
  diz o que acontece com as issues que a usam nem aceita prioridade substituta.
  Antes de excluir: contar as issues (`priority = <id>`); se houver, tire a
  prioridade de cada esquema com `priorities.remove` e mapeamento `in` (isso migra
  as issues) e so entao exclua. Nao ha como desfazer.
