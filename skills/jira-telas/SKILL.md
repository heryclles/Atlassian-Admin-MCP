---
name: jira-telas
description: Modelo de telas do Jira company-managed - projeto, esquema de tela por tipo de issue, esquema de tela, tela, abas e campos - com o caminho para descobrir qual tela um projeto mostra ao criar, editar ou ver uma issue, os payloads de esquemas e itens (default, create, edit, view, null), a ordem de campos e abas e as restricoes de exclusao. Use SEMPRE antes de criar, alterar, associar ou interpretar esquemas de tela e esquemas de tela por tipo de issue, antes de mover campos, e quando o pedido for "que tela/campos aparecem no projeto X" ou "quais projetos usam esta tela".
---

# Telas e esquemas de tela do Jira

Vale so para projetos **company-managed** (classicos). Projeto team-managed tem
telas proprias, fora destas APIs: nao aparece nas listagens e nao pode ser
associado. Todas as ferramentas exigem admin do Jira; as leituras de abas e
campos aceitam `projeto` (chave) para quem e so admin do projeto.

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
- Transicoes de workflow tambem usam telas (tela de transicao), fora dessa cadeia.
  Por isso uma tela pode estar em uso sem aparecer em nenhum esquema.
- Tela define **onde** o campo aparece. Obrigatorio e oculto vem da configuracao de
  campo, outra API: um campo na tela pode continuar escondido por ela.

## Qual tela o projeto mostra

Para "que campos aparecem ao criar um <tipo> no projeto SUP":

1. `jira_obter_projeto("SUP")`: `id` do projeto e `issueTypes` (id de cada tipo).
2. `jira_listar_tipo_tela_projetos([<id do projeto>])`: o esquema de tela por tipo
   de issue do projeto (`issueTypeScreenScheme.id`).
3. `jira_listar_itens_tipo_tela([<id desse esquema>])`: item do tipo; sem item
   proprio, vale o item `issueTypeId: "default"`. Da o `screenSchemeId`.
4. `jira_listar_esquemas_tela(ids=[<screenSchemeId>])`: `screens.create`; se nao
   houver, vale `screens.default`.
5. `jira_obter_tela(<id da tela>)`: abas e campos na ordem.

## Quem usa o que

| Pergunta | Caminho |
|---|---|
| Projetos que usam um esquema de tela por tipo de issue | `jira_usos_esquema_tipo_tela` |
| Projetos que usam um esquema de tela | `jira_listar_esquemas_tela(ids=[id], incluir_usos=True)` da os esquemas por tipo de issue; para cada um, `jira_usos_esquema_tipo_tela` |
| Projetos que usam uma tela | `jira_listar_esquemas_tela` (todas as paginas) e filtrar os esquemas cujo `screens` contem a tela; dai seguir a linha acima. Telas de transicao nao aparecem assim |
| Telas em que um campo esta | `jira_usos_campo` (com a aba de cada tela) |

## Payloads

### Esquema de tela (`telas`)

Chaves em ingles, valores com o id da tela:

```json
{ "default": 10000, "create": 10001, "edit": 10002, "view": 10000 }
```

- Criar (`jira_criar_esquema_tela`): `default` obrigatorio; as outras, opcionais.
- Salvar (`jira_salvar_esquema_tela`): mande so as operacoes que mudam. `null` em
  `create`, `edit` ou `view` tira a tela da operacao (volta a valer a `default`).
  `default` nunca pode ser `null`. Chave ausente fica como esta.

```json
{ "create": 10003, "view": null }
```

### Itens do esquema de tela por tipo de issue (`itens`)

```json
[
  { "issueTypeId": "default", "screenSchemeId": "10000" },
  { "issueTypeId": "10001", "screenSchemeId": "10002" }
]
```

- Criar (`jira_criar_esquema_tipo_tela`): o item `"default"` e obrigatorio.
- `jira_adicionar_itens_tipo_tela`: so tipos de issue reais, nunca `"default"`.
- Trocar o padrao: `jira_salvar_padrao_tipo_tela(esquema_id, esquema_tela_id)`.
- `jira_remover_itens_tipo_tela`: lista de ids de tipos de issue; eles passam a
  usar o padrao.
- Ids de tipos de issue: `jira_obter_projeto` (tipos do projeto) ou
  `jira_listar_tipos_issue`.

## Ordem de abas e campos

- Abas: `jira_mover_aba(tela, aba, posicao)`, posicao comeca em 0.
- Campos, dentro da mesma aba: `jira_mover_campo_aba` com
  - `depois_de`: id do campo apos o qual ele fica (ex. `"summary"`), ou
  - `posicao`: `First`, `Last`, `Earlier` (sobe uma), `Later` (desce uma).
  Com os dois, a API usa `depois_de`. Nao ha como pedir "antes de X": use
  `depois_de` com o campo anterior a X, ou `First`.
- Trocar de aba: `jira_remover_campo_aba` na atual e `jira_adicionar_campo_aba`
  na outra (entra no fim; depois mover).
- Um campo aparece uma vez por tela. `jira_listar_campos_disponiveis` lista o que
  ainda cabe. Ids de campo: `jira_listar_campos` (ex. `duedate`,
  `customfield_10000`).

## Telas grandes

- `jira_obter_tela` traz em cada aba `total_campos` e so os primeiros
  `limite_campos`. Se `total_campos` for maior, leia o resto com
  `jira_listar_campos_aba` seguindo `proximo_inicio`.
- A API pode devolver o mesmo campo varias vezes em sequencia na mesma aba. Venha
  como vier: ao contar campos, conte ids distintos e, se houver repeticao, avise o
  usuario, porque nao e o normal de uma tela.
- `jira_usos_campo` so aceita campo customizado (`customfield_...`); campo do
  sistema da 404.

## Restricoes

| Acao | A API recusa quando |
|---|---|
| Excluir tela | esta em esquema de tela, em transicao de workflow ou em rascunho de workflow |
| Excluir esquema de tela | esta em algum esquema de tela por tipo de issue |
| Excluir esquema de tela por tipo de issue | algum projeto o usa |
| Nomes de tela e de esquemas | ja existem (sao unicos) ou passam de 255 caracteres |

Excluir tela, aba ou esquema nao tem desfazer. Excluir uma aba tira da tela os
campos dela; fora isso, nada e excluido em cascata.

## Fluxo seguro de edicao

1. Antes de alterar uma tela ou esquema, veja quem usa (tabela "Quem usa o que") e
   diga ao usuario quais projetos serao afetados.
2. Para mudar um projeto so, sem mexer nos outros que dividem o esquema: crie
   uma tela ou esquema novo (copiando a composicao atual), ajuste e associe so a
   esse projeto com `jira_associar_esquema_tipo_tela`.
3. Depois de salvar, leia de novo (`jira_obter_tela`, `jira_listar_itens_tipo_tela`)
   e confira o resultado.
