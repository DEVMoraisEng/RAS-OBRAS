# RAS-OBRAS

Site da **Reunião de Alinhamento Semanal — Obras** (criada em 03/09/2026).
Mesma arquitetura das outras RAS: página estática no GitHub Pages lendo JSON
gerados por GitHub Actions, e Apps Script como único ponto de escrita no Notion.

## Bancos no Notion

| Banco | ID |
|---|---|
| ATIVIDADES RAS OBRAS | `3d0c5ab532d3803aa86ff57d293f6a14` |
| OBRAS RAS (compartilhado com a RAS de Líderes) | `3b4c5ab532d3806ba64bcf67f2dd4d6b` |

> A aba **Obras** lê o mesmo banco da RAS de Líderes — a obra é uma só e
> aparece nas duas reuniões. Se um dia a RAS Obras precisar de banco próprio,
> troque `RAS_OBRAS_DB_ID` no `fetch_ras.py` e na propriedade do Apps Script.

Os quadros da aba **Atividades** são as opções da coluna **Setor** do banco de
atividades (hoje: Guilherme, Isaac, João Vitor, João Marcos). Criar, renomear
ou remover uma opção lá reflete no site sozinho — não há nome fixo no código.

## Subir o repositório

1. Crie o repositório `DEVMoraisEng/RAS-OBRAS` (branch `main`) e suba estes arquivos.
   Confirme que os workflows ficaram em `.github/workflows/`.
2. **Settings > Pages**: Source = *Deploy from a branch*, branch `main`, pasta `/ (root)`.
3. **Settings > Secrets and variables > Actions > New repository secret**:
   `NOTION_TOKEN` = token da integração do Notion (o mesmo das outras RAS).
4. Rode o workflow *RAS Obras - atualizar dados (leitura)* pelo botão
   **Run workflow** para gerar os JSON pela primeira vez.

## Apps Script (escrita)

1. Crie um projeto novo no Apps Script e cole o `Code.gs` entregue junto.
2. **Configurações do projeto > Propriedades do script**:

| Propriedade | Valor |
|---|---|
| `NOTION_TOKEN` | token da integração |
| `RAS_OBRAS_ATIV_DB_ID` | `3d0c5ab532d3803aa86ff57d293f6a14` |
| `RAS_OBRAS_DB_ID` | `3b4c5ab532d3806ba64bcf67f2dd4d6b` |
| `GITHUB_REPO` | `DEVMoraisEng/RAS-OBRAS` |
| `GITHUB_TOKEN` | PAT com escopo `repo` |

3. **Implantar > Nova implantação > App da Web**: executar como *eu*, acesso
   **Qualquer pessoa**.
4. Copie a URL `/exec` e cole em `WRITE_ENDPOINT`, no topo do `<script>` do
   `index.html`. **Sem isso o site abre em modo teste e não grava nada.**
5. No editor, rode `testeConexao` e `testeAcessoAsOutrasRAS` — todas as linhas
   devem dizer `ok`. Se alguma disser `SEM ACESSO`, abra aquele banco no Notion
   e conecte a integração (••• > Conexões).

> Ao alterar o `Code.gs` depois, salvar **não** publica: é preciso
> *Implantar > Gerenciar implantações > lápis > Versão: Nova versão*.

## Semana de quinta a quinta

Diferente das outras cinco RAS (segunda a segunda), o ciclo da RAS Obras vai de
**quinta a quinta**: toda data gravada na coluna Semana cai numa quinta-feira.

O rollover roda **na noite de quarta** (`17 2 * * 4` = 23:17 de Brasília) e
joga o que não foi concluído para a quinta do dia seguinte, com o status
"Continuidade da Semana Anterior" — assim a reunião de quinta já abre com a
lista pronta.

Para mudar o dia da reunião no futuro, são três lugares: `DIA_ANCORA` no
`index.html` (0=domingo … 4=quinta), `DIA_ANCORA` no `rollover_semana.py`
(0=segunda … 3=quinta) e o `cron` do `rollover_semana.yml`.

## Coluna Origem (item 2)

Atividade criada por coparticipação ou vinda de outra RAS carrega um carimbo
como `Coparticipação › RAS Líderes › Diretoria › Júlio`. Crie no banco de
atividades uma coluna de **texto** chamada `Origem` para guardar isso. Enquanto
ela não existir, o carimbo é anexado no fim das **Observações** — a informação
não se perde, mas fica misturada.

## Portal

O botão da RAS Obras já está no PORTAL-MORAIS com a chave de acesso
`RAS OBRAS` — quem precisar ver o botão tem que ter essa opção marcada na
coluna ACESSOS do banco LOGINS.
