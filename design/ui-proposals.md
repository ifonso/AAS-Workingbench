# Propostas de UI: menos densidade, navegação mais fácil

Status: **proposta**, aplicada no mockup `aas-workingbench-mockup.figcraft` (página *Screens*).
O app ainda não mudou. A página *Reference (real app)* tem os prints de antes, para comparar.

## Telas do mockup

A página *Screens* tem uma ideia por tela, para que nada fique comprimido. Cada tela tem um título e uma frase dizendo o que mostra.

| # | Tela | O que mostra |
|---|---|---|
| 01 | Read / Overview | Árvore e elemento selecionado, sem mais nada |
| 02 | Read / Nothing selected | Estado vazio do detalhe antes do primeiro clique |
| 03 | Read / Filter the tree | Filtro "cycle": as correspondências e seus pais |
| 04 | Read / Search and go to | Paleta Ctrl+K buscando elementos pelo nome |
| 05 | Start / No package open | Primeira tela: abrir, criar ou reabrir um pacote |
| 06 | Edit / Overview | Ações de edição e coluna de tipo de volta |
| 07 | Edit / Change a value | Edição no lugar, valor alterado, pacote não salvo |
| 08 | Edit / Context menu | Menu de contexto da árvore |
| 09 | Edit / Hints grouped by rule | Os 523 hints reais em 4 grupos |
| 10 | Edit / Errors and warnings | Findings de erro e aviso (dados de exemplo) |
| 11 | Edit / Package files | Arquivos do pacote (dados de exemplo) |
| 12 | Edit / Several elements selected | Seleção múltipla e o painel Selection |
| 13–14 | Dark | As telas 01 e 07 no tema escuro |

As telas 02 e 05 desenham estados que o app hoje não trata. A tela 03 redesenha a busca da árvore, que hoje fica em *View > SearchBar*.

## Diagnóstico

Os prints do app (`screenshots/mode_read.png`, `screenshots/mode_edit_validation.png`) mostram que a densidade não vem do espaçamento.
As linhas de 24 px estão boas.
Ela vem de três coisas:

1. **Tudo tem o mesmo peso visual.** Rótulo e valor usam a mesma cor, e a árvore e o painel de detalhe parecem planilhas com cabeçalho.
2. **Metadado demais.** A coluna Type da árvore repete o que o ícone já diz e ocupa cerca de 40% da largura.
   O painel de detalhe mostra o tipo do metamodelo de cada atributo e lista quatro atributos `(empty)`.
3. **A navegação depende só da árvore.** O breadcrumb começa com `...`, as referências não levam a lugar nenhum, e a busca (Ctrl+K) fica escondida no menu.

## Princípios

- **Mostrar primeiro o que a pessoa lê.** O nome legível, o valor e a semântica vêm antes do idShort, do tipo e dos vazios.
- **Não remover nada.** Toda informação que sai da tela fica a um clique: recolhida, em tooltip ou visível no Edit mode.
  Assim a paridade com o Package Explorer não muda (ver `docs/agents/README.md`, *Boundaries*).
- **O Read mode é para ler e o Edit mode é para editar.** No Read mode, o que só serve para editar fica fora da tela.

## Propostas

Cada item diz onde ele aparece no mockup e a parte do código que mudaria.

### 1. Hierarquia visual (tokens e stylesheet)

| # | Proposta | No mockup | Código |
|---|---|---|---|
| 1.1 | Rótulo em `fg/secondary`, valor em `fg/primary` | Componente `Property row` | stylesheet do detalhe |
| 1.2 | Sem cabeçalho "Attribute / Value / Type" nem "Package / Type" | Screens | `treeviews/`, detalhe |
| 1.3 | Uma tipografia só: menus, status e breadcrumb em `type/body` (14/20), não em 15 px | O estilo `type/chrome` foi removido | `ui/theme`, fonte da plataforma |
| 1.4 | Ícone de tipo colorido pela família | Tokens `kind/*`, página Tokens | `domain/design_tokens.py`, `IconRole` |

As famílias do 1.4 são cinco, cada uma com cor própria no Light e no Dark:

| Token | Tipos | Light | Dark |
|---|---|---|---|
| `kind/structure` | Shell, Submodel | `#0F6CBD` | `#479EF5` |
| `kind/container` | Collection, List, Entity | `#00727A` | `#4CC2C8` |
| `kind/data` | Property, Range, MultiLanguageProperty, File | `#6B3FA0` | `#B696E0` |
| `kind/behavior` | Capability, Operation, BasicEventElement | `#A3247C` | `#E58BC9` |
| `kind/relation` | Relationship, AnnotatedRelationship | `#4F52B2` | `#9EA2F2` |

As cores evitam vermelho, laranja e verde, que já significam erro, aviso e sucesso.
O contraste delas ainda precisa ser medido contra `bg/content` e `bg/selected` antes de entrarem em `design_tokens.py`.

### 1.5 Cores de severidade: hint é informação, não aviso

Hoje um hint usa `status/warning` e `bg/warning`, em amarelo, e isso cansa, porque um pacote real tem centenas de hints.
A proposta reserva o amarelo para avisos e o vermelho para erros, e dá aos hints e aos findings de nível Info um azul claro:

| Severidade | Ícone e texto | Fundo |
|---|---|---|
| Erro | `status/error` (vermelho) | `bg/error` |
| Aviso | `status/warning` (amarelo) | `bg/warning` |
| Hint e Info | `status/info` (novo: Light `#0F6CBD`, Dark `#479EF5`) | `bg/info` (novo: Light `#EBF3FC`, Dark `#0E2A47`) |

No mockup isso vale para a barra de hints do detalhe, o "523 hints" da barra de status, os grupos e as contagens do painel de hints e a severidade Info da tabela de findings.
No código, a mudança fica em `domain/design_tokens.py`, com os dois tokens novos e a docstring de `status_warning` e `bg_warning`, que hoje dizem "or text of a hint".

### 2. Árvore do pacote

| # | Proposta | No mockup |
|---|---|---|
| 2.1 | **Coluna Type escondida por padrão.** O tipo fica no tooltip e em *View > Columns*. A árvore cai de 1036 px para 520 px, e o detalhe ganha esse espaço. | `Tree row` |
| 2.2 | **Grupos como títulos de seção.** "Asset Administration Shells" e "Submodels" deixam de ser nós e viram títulos com a contagem, o que tira um nível de recuo de tudo. | `Tree section` |
| 2.3 | **Contagem de filhos nos nós fechados**, por exemplo `Nameplate 18`. | `Tree row`, camada `count` |
| 2.4 | **Cabeçalho do painel com o nome do pacote e um filtro sempre visível.** | `Package tree > Pane header` |
| 2.5 | **Seleção ocupa a linha inteira em `bg/selected`, com barra de destaque à esquerda**, no lugar da caixa com borda só na célula do nome. | `Tree row/Selected` |

### 3. Painel de detalhe (é o que mais ajuda a leitura)

| # | Proposta | No mockup |
|---|---|---|
| 3.1 | **Cabeçalho em dois níveis separados por um divisor.** Em cima fica uma barra de caminho, que diz onde o elemento está: os pais clicáveis, o elemento atual e, à direita, copiar caminho e buscar. Abaixo dela fica um bloco de título com 20 px de respiro, que diz qual é o elemento: o ícone do tipo, o **idShort como título** (o mesmo nome da árvore e da aba) e o tipo como etiqueta. O displayName e o valor não aparecem no cabeçalho porque já são linhas das seções, e uma linha sem rótulo ali só confundia. Duas versões anteriores foram descartadas: um resumo que repetia o nome 4 vezes e o valor 2 vezes, e um cabeçalho compacto em que caminho, título e displayName ficavam colados, sem hierarquia. | `Detail tab > Element header` |
| 3.2 | **Atributos em seções recolhíveis:** Value, Identification e Semantics, nessa ordem, porque o valor é o que se lê numa Property. No Edit mode há também Advanced. | `Section` |
| 3.3 | **Vazios recolhidos no Read mode.** Uma linha "Empty attributes 4" lista os nomes e se expande se a pessoa quiser. | `Section/Collapsed` |
| 3.4 | **Textos multilíngues legíveis.** No lugar de `en="Time that one cyc..."` vem o texto no idioma preferido, com uma etiqueta logo depois dele: o ícone `language` do Tabler e `en +2` (o idioma mostrado e quantos outros existem), dentro da mesma etiqueta cinza. O ícone ainda não está em `icons/tabler`: é do mesmo conjunto (MIT, `@tabler/icons` 3.19.0) e está na página Icons do mockup, ao lado das alternativas `message-language` e `world`. | `Property row`, camada `lang` |
| 3.5 | **semanticId mostra o nome do conceito como link** ("Target cycle time"), com a IRI em segundo plano. A barra solta "Concept description…" no rodapé deixa de existir. | `Property row`, camada `sub` |
| 3.6 | **Coluna de tipo só no Edit mode**, em `type/caption` e `fg/muted`. | `Property row`, camada `type` |
| 3.7 | **Dado de outra origem aparece como etiqueta, com link para a origem.** A unidade de uma Property não é dela: vem da concept description apontada pelo semanticId (IEC 61360, campo `unit`). Por isso ela não fica colada ao valor (`2.0 s`). O valor `2.0` mantém o texto do corpo, e a unidade vira uma etiqueta menor e mais clara (`unit s`), seguida do link "from concept CycleTimeTarget", que abre a concept description. O mesmo vale para qualquer dado herdado do conceito. | `Property row`, camada `unit` |

### 4. Navegação

| # | Proposta | No mockup |
|---|---|---|
| 4.1 | **Busca sempre visível na barra de comandos** ("Search or go to… Ctrl+K"), que abre a paleta de comandos. | `Search box` |
| 4.2 | **Caminho completo e clicável na barra de caminho do detalhe**, sem `...`, com separadores `›`. | `Element header > Path bar` |
| 4.3 | **Referências clicáveis.** semanticId e valores do tipo Reference levam ao destino, e o voltar/avançar da barra completa o caminho. | Link no `Property row` |
| 4.4 | **Read/Edit como controle segmentado** na barra de comandos, no lugar de um texto na barra de status. | `Mode switch` |
| 4.5 | **No Read mode, adicionar, editar e excluir somem**, em vez de ficarem desabilitados. | `toolbar(read_mode=True)` |

### 5. Validação e barra de status

| # | Proposta | No mockup |
|---|---|---|
| 5.1 | **Problemas e hints como botões na barra de status** ("No problems", "523 hints"), que abrem o dock. | `Status bar` |
| 5.2 | **O dock de Validation só abre quando há algo a ver.** Sem findings, ele fica recolhido em vez de ocupar um quarto da tela para dizer "No findings". | Read mode sem dock |
| 5.3 | **Hints agrupados por regra, com contagem e "Show N more".** | `Validation (hints)` |
| 5.4 | **A explicação "Hints are advice, not rules…" vira uma linha curta** ao lado dos filtros. | idem |

Os números do 5.3 são os reais de `example/robot_arm_pick_and_place.aasx`.
São 523 hints: 178 de `EDT-HINT-DESCRIPTION-MISSING`, 143 de `EDT-HINT-DISPLAY-NAME-MISSING`, 135 de `EDT-HINT-DESCRIPTION-ONE-LANGUAGE` e 67 de `EDT-HINT-DISPLAY-NAME-ONE-LANGUAGE`.

## Ordem sugerida para implementar

1. **Mudanças rápidas e de baixo risco:** 1.1, 1.2, 1.3, 1.5, 2.1, 2.3, 2.5 e 4.5. Mexem quase só em stylesheet, colunas e visibilidade.
2. **Painel de detalhe:** 3.1 a 3.6. É a maior mudança, porque hoje o detalhe é gerado por introspecção dos tipos da BaSyx (`utils/util_type.py`).
   O agrupamento precisa de um mapa atributo → seção em `domain/`, ao lado de `attribute_vocabulary.py`, e um teste que falhe se um atributo novo não tiver seção.
3. **Navegação:** 4.1 a 4.4, 2.2 e 2.4.
4. **Validação:** 5.1 a 5.4.
5. **Cores das famílias (1.4):** só depois de medir o contraste, e registrando a decisão como ADR porque muda o ADR 0027.

## Perguntas em aberto

- **2.2:** a árvore deve continuar mostrando o pacote como raiz quando houver vários pacotes abertos? No mockup há um só.
- **3.1:** qual idioma é o preferido: o da interface, ou um configurável em *Settings*?
- **3.3:** os vazios ficam recolhidos também no Edit mode? No mockup, o Edit mode os mostra dentro de "Advanced", recolhido.
- **5.2:** o dock deve abrir sozinho quando aparece o primeiro erro, ou só quando a pessoa clica no status?

## Conteúdo do mockup

- **Dados reais do pacote de exemplo:** o idShort, o displayName e a description em 3 idiomas, o valor 2.0 com unidade `s`, a IRI do semanticId, a lista dos 14 submodelos, a contagem de filhos e os hints.
- **Dados de exemplo, que não existem no pacote:** o valor editado "Target time of one cycle" e os findings AASd-002 e AASd-131 do painel de erros na página *Shell*.
