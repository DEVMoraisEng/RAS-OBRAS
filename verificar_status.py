# -*- coding: utf-8 -*-
"""
verificar_status.py  (RAS OBRAS)
----------------------------------
Compara as opções de Status (e Prioridade) que o SITE oferece com as que
existem no NOTION. NÃO altera nada — só lê e aponta divergências.

Por que isso importa:
  - Se a coluna Status for do tipo "status" (kanban) no Notion, a API NÃO cria
    opções novas: mandar um nome que não existe lá dá erro 400. Então os nomes
    do site precisam existir no Notion, escritos EXATAMENTE igual (acentos etc).
  - Se for "select", o Notion cria a opção sozinho — mas ainda assim é bom
    manter os nomes iguais para não virar bagunça.

USO:
    export NOTION_TOKEN="ntn_xxx"
    python3 verificar_status.py
"""

import os, json, urllib.request, urllib.error

TOKEN   = os.environ.get("NOTION_TOKEN", "").strip()
DB_ATIV = (os.environ.get("RAS_OBRAS_ATIV_DB_ID") or "3d0c5ab532d3803aa86ff57d293f6a14").strip()
NOTION_VERSION = "2022-06-28"

# o que o index.html oferece hoje
#
# Setor NÃO entra aqui: o site lê as opções de Setor direto do schema do Notion
# (setorOptions, gerado pelo fetch_ras.py), então elas nunca divergem — o que
# estiver no Notion é o que aparece no site. Status e Prioridade, sim: esses o
# site oferece a partir de listas fixas e precisam existir lá igualzinho.
SITE = {
    "atividades": {
        "Status":     ["A Fazer", "Em Andamento", "Pendente", "Concluído",
                       "Continuidade da Semana Anterior"],
        "Prioridade": ["Alta", "Média", "Baixa"],
    },
}
NOME_ALT = {"Status": ["Status"], "Prioridade": ["Prioridade"]}

def api(path):
    req = urllib.request.Request("https://api.notion.com/v1" + path)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Notion-Version", NOTION_VERSION)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Erro Notion {e.code}: {e.read().decode('utf-8')[:300]}")

def opcoes_da_coluna(prop):
    t = prop.get("type")
    if t in ("select", "status", "multi_select"):
        return t, [o["name"] for o in prop[t]["options"]]
    return t, None

def comparar(nome_banco, db):
    print(f"\n===== {nome_banco.upper()} =====")
    schema = api(f"/databases/{db}").get("properties", {})
    for coluna, esperado in SITE[nome_banco].items():
        real = next((n for n in NOME_ALT[coluna] if n in schema), None)
        if not real:
            print(f"  [X] Coluna '{coluna}' NÃO existe no Notion.")
            continue
        tipo, opcoes = opcoes_da_coluna(schema[real])
        if opcoes is None:
            print(f"  [X] Coluna '{real}' é do tipo '{tipo}', sem lista de opções.")
            continue
        faltam  = [o for o in esperado if o not in opcoes]  # site manda, Notion não tem
        sobram  = [o for o in opcoes if o not in esperado]  # Notion tem, site não usa
        print(f"  {real} (tipo {tipo}):")
        print(f"    Notion : {opcoes}")
        print(f"    Site   : {esperado}")
        if faltam:
            print(f"    [!] FALTAM no Notion (o site manda, mas não existe lá): {faltam}")
            if tipo == "status":
                print(f"        -> tipo 'status': crie essas opções no Notion à mão (a API não cria).")
        if sobram:
            print(f"    (i) existem no Notion mas o site não usa: {sobram}")
        if not faltam and not sobram:
            print(f"    OK — batem certinho.")

def main():
    if not TOKEN:
        raise SystemExit("Defina NOTION_TOKEN.")
    comparar("atividades", DB_ATIV)

    # Informativo: mostra as opções de Setor e Responsável só para conferência.
    schema = api(f"/databases/{DB_ATIV}").get("properties", {})
    setor = schema.get("Setor")
    if setor:
        tipo, opcoes = opcoes_da_coluna(setor)
        print(f"\n===== SETOR (informativo) =====\n  tipo {tipo}: {opcoes}")
        print("  O site usa exatamente essas opções — nada a sincronizar à mão.")
    resp = schema.get("Responsável") or schema.get("Responsavel")
    if resp:
        print(f"\n===== RESPONSÁVEL (informativo) =====\n  tipo: {resp.get('type')}")
        if resp.get("type") != "people":
            print("  [!] Esperado tipo 'people'. O Apps Script grava {people:[{id}]}.")

    print("\nDica: rode isto sempre que mudar as opções no site ou no Notion.")

if __name__ == "__main__":
    main()
