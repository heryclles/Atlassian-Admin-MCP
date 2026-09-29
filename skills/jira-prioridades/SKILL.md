---
name: jira-prioridades
description: Modelo de prioridades e esquemas de prioridade do Jira - prioridade global com ordem e icone, esquema com subconjunto de prioridades e padrao, projeto ligado a um esquema, esquema padrao do site - com o fluxo de criar, editar, reordenar e excluir prioridades, criar e alterar esquemas, mover projetos entre esquemas e montar os mapeamentos "in" e "out" que migram as issues. Use SEMPRE antes de criar, alterar ou excluir prioridades e esquemas de prioridade, antes de chamar jira_salvar_esquema_prioridade ou jira_criar_esquema_prioridade, e quando o pedido for "que prioridades o projeto X usa" ou "trocar o esquema de prioridade do projeto".
---

# Prioridades e esquemas de prioridade do Jira

Todas as escritas exigem admin do Jira. Ids de prioridade, esquema e projeto sao
numericos; as ferramentas aceitam texto ("10001") e mandam inteiro para a API.

## O modelo

```
Prioridades do site (globais, ordem unica: sequence 1 = mais alta)
 └─ Esquema de prioridade = subconjunto dessas prioridades + defaultPriorityId
     └─ Projetos (cada projeto usa exatamente 1 esquema)

Esquema padrao do site (isDefault true): vale para projetos novos e para os
que saem de um esquema.
```

- Prioridade e global: renomear, trocar cor ou icone muda em todos os esquemas.
- A ordem e global (`jira_mover_prioridades`); o esquema so escolhe quais entram,
  nao reordena. `sequence` nas listas de esquema e essa ordem global.
- O padrao que vale num projeto e o `defaultPriorityId` do esquema dele. O padrao
  global (`jira_salvar_padrao_prioridade`, `isDefault` da prioridade) e legado.
- O esquema padrao do site se acha com
  `jira_listar_esquemas_prioridade(somente_padrao=True)`. Nao confiar no nome: um
  esquema chamado "Default priority scheme" pode nao ser o padrao.
- Prioridade nova nao entra em esquema nenhum: adicione com
  `jira_salvar_esquema_prioridade(adicionar_prioridades=[...])`.

## Leituras

| Pergunta | Caminho |
|---|---|
| Prioridades do site, na ordem | `jira_listar_prioridades` (paginas por `inicio`) |
| Em quais esquemas esta uma prioridade | `jira_listar_prioridades(ids=[id], incluir_esquemas=True)` ou `jira_listar_esquemas_prioridade(prioridade_ids=[id])` |
| Prioridades de um esquema | `jira_listar_prioridades_esquema` |
| Projetos de um esquema | `jira_usos_esquema_prioridade` |
| Esquema de um projeto | `jira_obter_projeto` da o `id`; para cada esquema de `jira_listar_esquemas_prioridade`, `jira_usos_esquema_prioridade(esquema, projeto_ids=[id])`: o que tiver `total` 1 e o do projeto |
| Prioridades que um projeto oferece | `jira_listar_prioridades(projeto_ids=[id])` |
| Issues com uma prioridade | `jira_contar_issues('priority = <id>')` |

## Criar e editar prioridade

- `cor`: hexadecimal de 3 ou 6 digitos (`"#d04437"`).
- `avatar_id`: o icone. Reaproveite o `avatarId` de uma prioridade existente com o
  icone desejado (`jira_listar_prioridades`). O antigo `iconUrl` foi descontinuado
  pela Atlassian em marco de 2025 e as ferramentas nao o enviam.
- `nome`: unico no site, ate 60 caracteres.
- A prioridade nasce no fim da ordem; `jira_mover_prioridades` coloca no lugar:
  `ids` na ordem desejada e `depois_de` (id fora de `ids`) ou `posicao`
  (`First`/`Last`).

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

Na criacao so existe `in` (para os `projeto_ids`); `out` e so de alteracao.

A API recusa (400) mapeamento faltando, sobrando ou apontando para prioridade fora
do lugar certo, e a mensagem lista os ids. Mande so as chaves exigidas.

## Fluxo seguro de alteracao de esquema

1. Ler o estado: `jira_listar_prioridades_esquema` e `jira_usos_esquema_prioridade`
   do esquema; se houver remocao de projetos, as prioridades do esquema padrao
   (`somente_padrao=True`, `incluir_prioridades=True`).
2. Descobrir as chaves de `in`: `jira_listar_prioridades_mapear` com as mesmas
   listas que irao para a alteracao (nao altera nada). Cada prioridade devolvida
   precisa de uma chave em `in`. Para `out`, comparar a mao: prioridades do esquema
   que nao estao no esquema padrao.
3. Mostrar ao usuario o plano (o que entra, sai e para onde vai cada prioridade) e
   pedir confirmacao: a migracao altera issues de verdade.
4. `jira_salvar_esquema_prioridade` com as mudancas e `mapeamentos`.
5. A resposta traz `task`; acompanhar em `jira_obter_tarefa(task.id)` ate
   `COMPLETE` (ou `FAILED`/`DEAD`, que se reporta com `message` e `result`). Enquanto
   ela roda, nova alteracao no mesmo esquema da 409.

Exemplo: esquema 10100 perde a prioridade 10004 (issues vao para 10003) e recebe o
projeto 10200, cujo esquema atual usa 10007 (issues vao para 10001):

```
jira_listar_prioridades_mapear("10100", remover_prioridades=["10004"], adicionar_projetos=["10200"])
jira_salvar_esquema_prioridade("10100", remover_prioridades=["10004"], adicionar_projetos=["10200"],
                               mapeamentos=<abaixo>)
```

```json
{"in": {"10004": 10003, "10007": 10001}}
```

## Mover um projeto de esquema

Nao ha "associar": o projeto entra no esquema novo por
`jira_salvar_esquema_prioridade(<novo>, adicionar_projetos=[id], mapeamentos={"in": ...})`
e sai sozinho do anterior. Remover o projeto de um esquema o devolve ao esquema
padrao do site (com `out`).

## Excluir

- **Esquema**: so sem projetos. Tire os projetos antes (`remover_projetos`, ou
  `adicionar_projetos` em outro esquema); as prioridades continuam.
- **Prioridade**: global e assincrona (devolve a tarefa). A documentacao da API nao
  diz o que acontece com as issues que a usam nem aceita prioridade substituta.
  Antes de excluir: `jira_contar_issues('priority = <id>')`; se houver issues,
  tire a prioridade de cada esquema com `remover_prioridades` e mapeamento `in`
  (isso migra as issues) e so entao exclua. Nao ha como desfazer.
