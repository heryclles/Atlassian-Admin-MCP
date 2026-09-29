---
name: jira-config-campos
description: Modelo das configuracoes de campo e dos esquemas de configuracao de campo do Jira company-managed (API antiga /fieldconfiguration e /fieldconfigurationscheme, obsoleta mas ativa na maioria dos sites) - projeto, esquema, item por tipo de issue, configuracao e os itens de cada campo (obrigatorio, oculto, descricao, renderizador) - com o caminho para descobrir como um campo se comporta num projeto, os payloads e o fluxo seguro de alteracao. Use SEMPRE antes de mudar obrigatorio, oculto ou descricao de campos pela API antiga, antes de criar, ligar ou associar configuracoes e esquemas de configuracao de campo, e quando o pedido for "o campo X e obrigatorio no projeto Y" ou "por que o campo nao aparece" num site sem o beta de esquemas de campos.
---

# Configuracoes de campo do Jira (API antiga)

`/rest/api/3/fieldconfiguration` e `/fieldconfigurationscheme`. A Atlassian marcou
como obsoletas em favor dos esquemas de campos (API nova, em beta, skill
`jira-esquemas-campos`), mas elas continuam sendo as que funcionam em sites sem o
beta. Se o pedido nao disser qual API usar: esta, a menos que
`jira_listar_esquemas_campos` responda sem o aviso de "desligada".

Vale so para projetos **company-managed**; exige admin do Jira.

## A cadeia

```
Projeto
 └─ 1 esquema de configuracao de campo            (fieldconfigurationscheme)
     ├─ item "default" ─> configuracao de campo    (tipos sem item proprio)
     └─ item <tipo>    ─> configuracao de campo    (fieldconfiguration)
                            └─ 1 item por campo do site:
                               isRequired, isHidden, description, renderer
```

- Projeto sem esquema proprio usa o esquema padrao do site, que aponta para a
  configuracao padrao (`jira_listar_configs_campo(somente_padrao=True)`).
- Varios projetos e tipos podem dividir a mesma configuracao: mudar um item muda
  todos eles.
- **Configuracao de campo**: como o campo se comporta. **Tela** (skill `jira-telas`):
  onde aparece. **Contexto do campo customizado**: opcoes e valor padrao.

| Item | Efeito |
|---|---|
| `isRequired` | Nao deixa criar ou editar a issue com o campo vazio |
| `isHidden` | O campo some do projeto e tipo, mesmo estando na tela |
| `description` | Texto de ajuda que aparece embaixo do campo |
| `renderer` | Campos de texto: `wiki-renderer` (editor rico) ou `text-renderer` (simples) |

## Como o campo X se comporta no projeto Y, tipo T

1. `jira_obter_projeto("Y")`: `id` do projeto e `issueTypes` (id de T).
2. `jira_listar_config_projetos([<id>])`: esquema do projeto. Grupo sem
   `fieldConfigurationScheme` = esquema padrao do site; nesse caso a configuracao e a
   padrao (`somente_padrao=True`) e pula o passo 3.
3. `jira_listar_itens_config([<esquema>])`: item de T; sem item proprio, vale o
   `issueTypeId: "default"`. Da o `fieldConfigurationId`.
4. `jira_listar_campos_config(<configuracao>, campo_ids=["X"])`: o item do campo.
   Se vier em `nao_encontrados`, o campo nao esta na configuracao.

Para "quais campos sao obrigatorios no projeto": passos 1 a 3 para cada tipo e
`jira_listar_campos_config` paginado, filtrando `isRequired` (so ao responder, a
ferramenta nao filtra por regra).

"Quais projetos usam esta configuracao": `jira_listar_itens_config` (todas as
paginas) da os esquemas que a usam; `jira_listar_config_projetos` com os ids de
`jira_listar_projetos` diz o esquema de cada projeto.

## Payloads

### Itens de campo (`jira_salvar_campos_config`)

So o que vier no item muda. `id` e o id do campo (`jira_listar_campos`).

```json
[{"id": "customfield_10000", "isRequired": true},
 {"id": "environment", "isHidden": true},
 {"id": "description", "description": "Passos para reproduzir", "renderer": "wiki-renderer"}]
```

- **Ocultar apaga** obrigatorio, descricao e renderizador do campo; reexibir volta aos
  valores padrao, nao aos anteriores. Antes de ocultar, anote o item atual.
- Nao da para trocar o renderizador de campo com `autocomplete-renderer`.
- Campos essenciais do sistema (ex. `summary`, `issuetype`) sao sempre obrigatorios e
  visiveis no Jira: nao tente muda-los.

### Itens do esquema (`jira_adicionar_itens_config`)

Tipo de issue -> configuracao. Cria ou troca o item do tipo; cada tipo uma vez so
por chamada.

```json
[{"issueTypeId": "default", "fieldConfigurationId": "10000"},
 {"issueTypeId": "10001", "fieldConfigurationId": "10002"}]
```

`jira_remover_itens_config` tira itens de tipos (eles voltam ao `default`).

## Fluxo seguro

1. Seguir a cadeia ate a configuracao do projeto e tipo.
2. Ver quem mais usa essa configuracao (secao acima). Se for compartilhada e a
   mudanca for so para um projeto ou tipo:
   - `jira_criar_config_campo` (nasce com os campos da padrao, todos opcionais):
     reproduzir nela os itens que importam da configuracao atual;
   - se o esquema tambem for compartilhado, `jira_criar_esquema_config` e
     `jira_adicionar_itens_config` copiando os itens atuais;
   - ligar o tipo a configuracao nova (`jira_adicionar_itens_config`) e, se preciso,
     o projeto ao esquema novo (`jira_associar_esquema_config`).
3. Mostrar ao usuario o plano e pedir confirmacao.
4. `jira_salvar_campos_config` e conferir com `jira_listar_campos_config(campo_ids=...)`.
5. Campo obrigatorio: conferir se ele esta na tela de criacao do tipo (skill
   `jira-telas`); obrigatorio fora da tela impede criar a issue.

## Renomear e excluir

- `jira_salvar_config_campo` e `jira_salvar_esquema_config` sobrescrevem nome **e**
  descricao: repita a descricao atual para mante-la.
- Exclua so configuracao que nao esta em nenhum esquema e esquema sem projetos (a
  especificacao nao diz o que a API faz nos outros casos). Para esvaziar um esquema,
  associe os projetos a outro, ou ao padrao com `jira_associar_esquema_config` sem
  esquema_id.
