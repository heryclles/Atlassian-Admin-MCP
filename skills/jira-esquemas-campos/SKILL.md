---
name: jira-esquemas-campos
description: Modelo dos esquemas de campos do Jira (API nova /config/fieldschemes, em beta, que substitui configuracao de campo e esquema de configuracao de campo) - quais campos existem em cada projeto, obrigatorio, descricao (texto de ajuda) e renderizador, excecoes por tipo de issue, restricao a tipos de issue, associacao a projetos - com os payloads em lote, os resultados parciais e o fluxo seguro de alteracao. Use SEMPRE antes de adicionar ou remover campos de esquemas, mudar obrigatoriedade ou descricao de campos, copiar ou associar esquemas de campos, e quando o pedido for "o campo X e obrigatorio no projeto Y", "deixar campo obrigatorio so para Bug" ou "por que o campo nao aparece".
---

# Esquemas de campos do Jira (API nova)

`/rest/api/3/config/fieldschemes`, em beta: so responde em sites que entraram no
programa beta. Com a funcionalidade desligada, qualquer chamada da 404 sem corpo e
as ferramentas avisam isso. Ela substitui a API antiga de configuracao de campo e
esquema de configuracao de campo. Todas as ferramentas exigem admin do Jira.

As duas APIs ficam no plugin. Use esta quando o pedido falar em "API nova", "beta"
ou "esquema de campos"; a antiga (ferramentas `*_config*`, skill
`jira-config-campos`) quando falar em "API antiga", "legado" ou "configuracao de
campo". Sem indicacao, e se esta responder "desligada", use a antiga.

## O que o esquema de campos decide

```
Projeto
 └─ 1 esquema de campos
     └─ campos associados (o que nao esta no esquema nao existe no projeto)
         ├─ parameters: isRequired, description, rendererType   (valem para todos os tipos)
         ├─ workTypeParameters: excecoes por tipo de issue      (sobrepoem parameters)
         └─ restrictedToWorkTypes: o campo so existe nesses tipos (vazio = todos)
```

- **Esquema de campos**: quais campos o projeto tem e como se comportam
  (obrigatorio, texto de ajuda, editor rico ou simples), por tipo de issue.
- **Tela** (skill `jira-telas`): onde o campo aparece (criar, editar, ver).
- **Contexto do campo customizado**: opcoes e valor padrao do campo.

"Oculto" nao existe mais: tirar o campo do esquema (`jira_remover_campos_esquema`)
ou restringi-lo a alguns tipos (`restrictedToWorkTypes`).

`workType` = tipo de issue: `workTypeId` e o id de `jira_listar_tipos_issue`.

## Leituras

| Pergunta | Caminho |
|---|---|
| Esquema de um projeto | `jira_obter_projeto` da o `id`; `jira_listar_esquemas_campos(projeto_ids=[id])` |
| Projetos de um esquema | `jira_usos_esquema_campos` |
| Campos de um esquema e como se comportam | `jira_listar_campos_esquema` (todas as paginas) |
| O campo X no projeto Y | esquema do projeto; `jira_listar_campos_esquema(esquema, campo_ids=["X"])`: sem resultado = o campo nao existe no projeto |
| Obrigatorio para o tipo T | `workTypeParameters` do tipo T, se houver; senao `parameters.isRequired`. Se `restrictedToWorkTypes` nao estiver vazio e nao tiver T, o campo nem existe em T |
| O que da para mudar no campo | `allowedOperations` (ex. `REMOVE`, `CHANGE_REQUIRED`, `CHANGE_DESCRIPTION`): operacao fora da lista a API recusa |

Ids de campo: `jira_listar_campos` (ex. `description`, `customfield_10000`).

## Payloads (escritas em lote)

As quatro escritas de campos recebem um mapa `{id do campo: ...}`. Ids de esquema e de
tipo de issue sao numeros (as ferramentas convertem texto). Limites: 100 campos por
chamada e 50 esquemas por item.

### Adicionar campos (`jira_adicionar_campos_esquema`)

Poe o campo nos esquemas. `restrictedToWorkTypes` substitui a restricao atual; sem
ele o campo vale para todos os tipos. Tambem serve para mudar so a restricao de um
campo que ja esta no esquema.

```json
{"customfield_10000": [{"schemeIds": [10000, 10001], "restrictedToWorkTypes": [10002]}],
 "customfield_10001": [{"schemeIds": [10000]}]}
```

### Remover campos (`jira_remover_campos_esquema`)

```json
{"customfield_10000": {"schemeIds": [10000, 10001]}}
```

### Parametros (`jira_salvar_parametros_campos`)

`parameters` vale para todos os tipos; `workTypeParameters` cria ou troca a excecao
de cada tipo. Parametro omitido fica como esta. `rendererType`: `jira-text-renderer`
(texto simples) ou `atlassian-wiki-renderer` (editor rico), so em campos de texto.
O campo precisa estar no esquema antes.

```json
{"customfield_10000": [{"schemeIds": [10000],
                        "parameters": {"isRequired": false, "description": "Versao onde o erro aparece"},
                        "workTypeParameters": [{"workTypeId": 10002, "isRequired": true}]}]}
```

Exemplo acima: o campo e opcional no esquema 10000, mas obrigatorio para o tipo 10002.

### Remover excecoes (`jira_remover_parametros_campos`)

O tipo volta a seguir `parameters`. Nomes: `isRequired`, `description`, `rendererType`.
Maximo de 100 remocoes por chamada (tipos x nomes, somados).

```json
{"customfield_10000": [{"schemeId": 10000, "workTypeIds": [10002], "parameters": ["isRequired"]}]}
```

## Resultados parciais

As escritas em lote respondem 200 ou 207 com `results`: um item por campo e esquema
(ou projeto), com `success` e `error`. **207 = parte falhou**: leia cada item e diga
ao usuario o que nao foi aplicado. Resposta vazia (204) = tudo aplicado.

## Fluxo seguro

1. Achar o esquema do projeto e ver quem mais o usa (`jira_usos_esquema_campos`).
   Mudanca no esquema vale para todos esses projetos.
2. Se o esquema for compartilhado e a mudanca for so para um projeto:
   `jira_copiar_esquema_campos` e depois `jira_associar_esquema_campos` do projeto ao
   esquema novo. Confirmar com o usuario antes: trocar o esquema do projeto troca
   todos os campos dele.
3. Ler o estado atual do campo (`jira_listar_campos_esquema(campo_ids=[...])`) e
   conferir `allowedOperations`.
4. Mostrar ao usuario o que muda e aplicar. Conferir `results`.
5. Campo obrigatorio: conferir se ele esta na tela de criacao do tipo
   (skill `jira-telas`); obrigatorio fora da tela impede criar a issue.

## Esquemas

- `jira_criar_esquema_campos` nasce so com os campos essenciais do sistema; para
  partir de um existente, `jira_copiar_esquema_campos`.
- `jira_excluir_esquema_campos`: a API recusa o esquema do sistema (400) e esquema
  com projetos (409). Mova os projetos antes com `jira_associar_esquema_campos`.
