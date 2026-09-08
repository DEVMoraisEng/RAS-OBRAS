# -*- coding: utf-8 -*-
"""
rollover_semana.py  (RAS OBRAS)
-------------------------------
Roda automaticamente toda QUARTA à noite (via GitHub Actions): a semana da
RAS Obras vira na quinta, então a rotina prepara o novo ciclo na véspera.

Para toda atividade que NÃO foi concluída e cuja Semana pertence a uma semana
já encerrada, o script:
  - muda a Semana para a quinta-feira do ciclo ALVO (ver inicio_alvo:
    quarta à noite = o ciclo que começa amanhã; nos demais dias = o ciclo
    vigente, para que uma execução manual no meio da semana não pule tudo para
    a semana seguinte);
  - muda o Status para "Continuidade da Semana Anterior" — EXCETO quem já
    está "Em Andamento": esse só muda de semana, o status continua "Em
    Andamento" (item de 07/09/2026 — não faz sentido rotular de "pendência
    arrastada" algo que já está sendo feito).

Assim, o que ficou em aberto reaparece sozinho no quadro da nova semana, já
sinalizado como pendência arrastada (ou, se já estava em andamento, sem
mudar essa sinalização). O que foi concluído fica no histórico.

Tolerância: a coluna Status pode ser do tipo "select" OU "status" no Notion;
os nomes das colunas podem variar (Nome/Atividade, etc.). O script lê o schema
antes de agir — mesma lógica do fetch_ras.py.

USO LOCAL (teste):
    export NOTION_TOKEN="ntn_xxx"
    python3 rollover_semana.py            # aplica de verdade
    python3 rollover_semana.py --dry-run  # só mostra o que faria, sem alterar
"""

import os, sys, json, time, datetime, urllib.request, urllib.error
from zoneinfo import ZoneInfo

TOKEN   = os.environ.get("NOTION_TOKEN", "").strip()
DB_ATIV = (os.environ.get("RAS_OBRAS_ATIV_DB_ID") or "3d0c5ab532d3803aa86ff57d293f6a14").strip()
NOTION_VERSION = "2022-06-28"
TZ = ZoneInfo("America/Sao_Paulo")
DRY_RUN = "--dry-run" in sys.argv

STATUS_CONCLUIDO    = "Concluído"
STATUS_CONTINUIDADE = "Continuidade da Semana Anterior"
# ITEM 3 (07/09/2026): quem esta "Em Andamento" continua "Em Andamento" no
# rollover — so muda de semana, o status nao vira Continuidade.
STATUS_EM_ANDAMENTO = "Em Andamento"

# nomes possíveis de cada coluna (tolera renome/acentos)
NOMES = {
    "status": ["Status"],
    "semana": ["Semana"],
    "nome":   ["Nome", "Atividade"],
}

def api(method, path, body=None):
    req = urllib.request.Request(
        "https://api.notion.com/v1" + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Erro Notion {e.code} em {method} {path}: {e.read().decode('utf-8')[:400]}")

def get_schema(db):
    return api("GET", f"/databases/{db}").get("properties", {})

def achar(schema, candidatos):
    for n in candidatos:
        if n in schema:
            return n
    return None

def ler_status(prop):
    if not prop: return ""
    t = prop.get("type")
    if t == "status": return (prop.get("status") or {}).get("name", "")
    if t == "select": return (prop.get("select") or {}).get("name", "")
    return ""

def ler_semana(prop):
    if not prop: return ""
    return (prop.get("date") or {}).get("start", "")

def ler_nome(prop):
    if not prop or prop.get("type") != "title": return ""
    return "".join(t["plain_text"] for t in prop.get("title", []))

def valor_status(tipo, nome):
    # monta o valor de Status conforme o tipo real da coluna
    if tipo == "status":
        return {"status": {"name": nome}}
    return {"select": {"name": nome}}

def query_all(db):
    results, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor: body["start_cursor"] = cursor
        data = api("POST", f"/databases/{db}/query", body)
        results.extend(data.get("results", []))
        if not data.get("has_more"): break
        cursor = data.get("next_cursor")
        time.sleep(0.15)
    return results

# A semana da RAS Obras vai de QUINTA a QUINTA (as outras cinco RAS continuam
# em segunda — por isso este número só existe aqui). Contagem do
# datetime.weekday(): segunda=0, terça=1, quarta=2, QUINTA=3.
DIA_ANCORA = 3

def inicio_alvo(d):
    """Quinta-feira para onde as pendências devem ir.

    - Quarta à noite (cron ~23h Brasília, que é o horário oficial da rotina):
      prepara o ciclo que COMEÇA amanhã -> retorna a quinta de amanhã.
    - Qualquer outro dia (execução manual no meio da semana): retorna a quinta
      que abriu o ciclo VIGENTE, para NÃO empurrar tudo uma semana à frente
      por engano.

    Assim o resultado é correto independentemente do dia em que roda:
    quarta -> próxima quinta; quinta a terça -> quinta deste ciclo.
    """
    dow = d.weekday()                                  # segunda=0 ... domingo=6
    if dow == (DIA_ANCORA - 1) % 7:                    # véspera (quarta)
        return d + datetime.timedelta(days=1)
    return d - datetime.timedelta(days=(dow - DIA_ANCORA) % 7)

def main():
    if not TOKEN:
        raise SystemExit("Defina NOTION_TOKEN antes de rodar.")

    schema = get_schema(DB_ATIV)
    p_status = achar(schema, NOMES["status"])
    p_semana = achar(schema, NOMES["semana"])
    p_nome   = achar(schema, NOMES["nome"])
    if not p_status or not p_semana:
        raise SystemExit(f"Não encontrei as colunas Status/Semana. Colunas do banco: {list(schema)}")

    tipo_status = schema[p_status]["type"]
    if tipo_status not in ("status", "select"):
        raise SystemExit(f'A coluna "{p_status}" é do tipo {tipo_status}; esperado status ou select.')

    # Se for tipo "status", a opção precisa existir no Notion — a API NÃO cria
    # opção de status sozinha (diferente de select).
    if tipo_status == "status":
        opcoes = [o["name"] for o in schema[p_status].get("status", {}).get("options", [])]
        if STATUS_CONTINUIDADE not in opcoes:
            raise SystemExit(
                f'A opção "{STATUS_CONTINUIDADE}" não existe na coluna Status (tipo status).\n'
                f'Opções atuais no Notion: {opcoes}\n'
                f'Crie essa opção no Notion antes de rodar (a API não cria opção de status automaticamente).')

    hoje = datetime.datetime.now(TZ).date()
    alvo = inicio_alvo(hoje).isoformat()
    print(f"Hoje: {hoje} | Movendo pendências para a semana de: {alvo}")

    rows = query_all(DB_ATIV)
    movidas = 0
    for pg in rows:
        P = pg["properties"]
        status = ler_status(P.get(p_status))
        semana = ler_semana(P.get(p_semana))
        nome   = ler_nome(P.get(p_nome)) if p_nome else ""
        if not semana or status == STATUS_CONCLUIDO:
            continue
        if semana >= alvo:
            continue  # já está na próxima semana (ou em semana futura) — não mexe
        movidas += 1
        # Em Andamento fica Em Andamento (so muda de semana); os demais
        # status em aberto (A Fazer, Pendente...) viram Continuidade.
        novo_status = status if status == STATUS_EM_ANDAMENTO else STATUS_CONTINUIDADE
        print(f"  -> {nome[:60]!r}: semana {semana} => {alvo} | status {status!r} => {novo_status!r}")
        if not DRY_RUN:
            api("PATCH", f"/pages/{pg['id']}", {"properties": {
                p_semana: {"date": {"start": alvo}},
                p_status: valor_status(tipo_status, novo_status),
            }})
            time.sleep(0.2)

    print(f"\n{'(dry-run) ' if DRY_RUN else ''}{movidas} atividade(s) movida(s) para {alvo}.")

if __name__ == "__main__":
    main()
