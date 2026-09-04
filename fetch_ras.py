# -*- coding: utf-8 -*-
"""
fetch_ras.py  (RAS OBRAS)
-------------------------
Lê os bancos da RAS Obras no Notion e gera os JSON que o site consome:
  dist/data_atividades.json
  dist/data_obras.json

O site lê apenas esse JSON (nada de token no navegador -> sem CORS).

Diferenças em relação ao fetch_ras.py da RAS geral:
  - a aba Obras lê o MESMO banco de Obras da RAS de Líderes: a obra é uma só,
    aparece nas duas reuniões (se um dia a RAS Obras tiver banco próprio,
    basta trocar RAS_OBRAS_DB_ID abaixo);
  - além de statusOptions, publica também setorOptions, lido do schema do
    Notion. É isso que faz a lista de pessoas do site espelhar o Notion:
    criar/renomear/remover uma opção na coluna Setor aparece no site sozinho,
    com a acentuação exata do Notion (então site e Notion nunca divergem).

USO LOCAL (teste):
    export NOTION_TOKEN="ntn_xxx"
    python3 fetch_ras.py                   # gera o JSON em ./dist

NO GITHUB ACTIONS:
    o token vem do secret NOTION_TOKEN; o DB ID já está abaixo.
    (ID de banco não é credencial — pode ficar no código.)
"""

import os, json, time, datetime, unicodedata, urllib.request, urllib.error

TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
# ATIVIDADES RAS OBRAS
DB_ATIV  = (os.environ.get("RAS_OBRAS_ATIV_DB_ID") or "3d0c5ab532d3803aa86ff57d293f6a14").strip()
# OBRAS RAS — banco compartilhado com a RAS de Líderes
DB_OBRAS = (os.environ.get("RAS_OBRAS_DB_ID") or "3b4c5ab532d3806ba64bcf67f2dd4d6b").strip()
NOTION_VERSION = "2022-06-28"


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
        raise SystemExit("Erro Notion %s em %s %s: %s"
                         % (e.code, method, path, e.read().decode("utf-8")[:400]))


def query(db):
    """Retorna todas as linhas do banco (com paginação)."""
    results, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = api("POST", "/databases/%s/query" % db, body)
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        time.sleep(0.2)
    return results


def pval(prop):
    """Lê o valor de uma propriedade seja qual for o tipo (tolerante a mudanças)."""
    if prop is None:
        return ""
    t = prop.get("type")
    if t == "title":        return "".join(x["plain_text"] for x in prop["title"])
    if t == "rich_text":    return "".join(x["plain_text"] for x in prop["rich_text"])
    if t == "select":       return (prop.get("select") or {}).get("name", "")
    if t == "status":       return (prop.get("status") or {}).get("name", "")
    if t == "multi_select": return ", ".join(o["name"] for o in prop.get("multi_select", []))
    if t == "date":         return (prop.get("date") or {}).get("start", "")
    if t == "checkbox":     return "Sim" if prop.get("checkbox") else "Não"
    if t == "number":       return prop.get("number")
    if t == "people":       return ", ".join(p.get("name", "") for p in prop.get("people", []))
    return ""


def g(props, *names):
    """Pega a 1ª propriedade existente entre os nomes dados (tolera renome/maiúsculas)."""
    for n in names:
        if n in props:
            return pval(props[n])
    return ""


def _sa(s):
    """minúsculo e sem acento, para comparar nomes com tolerância."""
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower().strip()


def opcoes(schema, *col_names):
    """Opções de uma coluna select/status, na ORDEM definida no Notion."""
    for n in col_names:
        prop = schema.get(n)
        if not prop:
            continue
        t = prop.get("type")
        if t in ("status", "select"):
            return [o["name"] for o in (prop.get(t) or {}).get("options", [])]
    return []


def fazer_curto(setores):
    """Devolve uma função que converte o nome de conta do Notion (vem completo,
    ex.: 'Paula Morais') no nome curto que o site usa — que aqui é o próprio
    nome da opção de Setor ('Paula').

    É isso que faz o responsável casar com o setor: sem essa conversão o nome
    completo não bate com a opção do quadro e a coluna Responsável fica
    inconsistente com o Setor.

    A comparação é feita contra a lista de setores lida do Notion (prefixo,
    sem acento, case-insensitive), então não há nome hardcoded aqui: mexer nas
    opções de Setor no Notion já ajusta o casamento automaticamente.

    Exemplos com os setores atuais:
        'Paula Morais'     -> 'Paula'
        'Guilherme Santos' -> 'Guilherme'

    Se não reconhecer ninguém devolve '' e o chamador mantém o nome do Notion.
    """
    # do mais longo para o mais curto: evita que 'Ana' casasse antes de 'Ana Paula'
    pares = sorted(((_sa(s), s) for s in setores if s), key=lambda p: -len(p[0]))

    def curto(nome_conta):
        k = _sa(nome_conta)
        if not k:
            return ""
        for chave, original in pares:
            if chave and k.startswith(chave):
                return original
        return ""

    return curto


def build_atividades(curto):
    out = []
    for pg in query(DB_ATIV):
        P = pg["properties"]
        resp_raw = g(P, "Responsável", "Responsavel")
        out.append({
            "id":          pg["id"],
            "nome":        g(P, "Nome", "Atividade"),
            "setor":       g(P, "Setor"),
            "responsavel": curto(resp_raw) or resp_raw,   # nome curto p/ casar no site
            "prioridade":  g(P, "Prioridade"),
            "status":      g(P, "Status"),
            "semana":      g(P, "Semana"),
            "obs":         g(P, "Observações", "Observacoes"),
            # ITEM 2 (03/09/2026) — de onde a atividade veio. A coluna Origem é
            # gravada pelo Code.gs quando a atividade nasce por coparticipação
            # ou vem replicada de outra RAS. Banco sem a coluna devolve "" e o
            # site simplesmente não mostra o selo.
            "origem":      g(P, "Origem"),
        })
    return out


def build_obras():
    """Aba Obras (item 5 do pedido de 03/09/2026).

    As colunas foram renomeadas no Notion:
        "Entrega prevista" -> "Previsão de início"    (campo interno: previsao)
        "Prioritária"      -> "LIBERADA PARA INICIAR" (campo interno: liberada)
    Os nomes antigos continuam na lista por segurança.
    """
    out = []
    for pg in query(DB_OBRAS):
        P = pg["properties"]
        out.append({
            "id":       pg["id"],
            "nome":     g(P, "Nome", "Obra"),
            "cidade":   g(P, "CIDADE", "Cidade"),
            "setor":    g(P, "SETOR", "Setor"),
            "mes":      g(P, "Mês", "Mes"),
            "status":   g(P, "Status"),
            "previsao": g(P, "Previsão de início", "Previsao de inicio",
                           "PREVISÃO DE INÍCIO", "Entrega prevista", "Entrega"),
            "liberada": g(P, "LIBERADA PARA INICIAR", "Liberada para iniciar",
                           "Liberada", "Prioritária", "Prioritaria"),
            "obs":      g(P, "Observações", "Observacoes"),
        })
    return out


def main():
    if not TOKEN:
        raise SystemExit("Defina NOTION_TOKEN (o seu token do Notion).")
    os.makedirs("dist", exist_ok=True)
    now = datetime.datetime.now().isoformat(timespec="seconds")

    schema = api("GET", "/databases/%s" % DB_ATIV).get("properties", {})
    status_opts = opcoes(schema, "Status")
    setor_opts  = opcoes(schema, "Setor")

    ativ = build_atividades(fazer_curto(setor_opts))

    with open("dist/data_atividades.json", "w", encoding="utf-8") as f:
        json.dump({"geradoEm": now,
                   "statusOptions": status_opts,
                   "setorOptions": setor_opts,
                   "atividades": ativ},
                  f, ensure_ascii=False, indent=2)

    print("data_atividades.json -> %d atividades" % len(ativ))
    print("  status: %s" % status_opts)
    print("  setores: %s" % setor_opts)

    # ---------------- aba Obras ----------------
    schema_obras   = api("GET", "/databases/%s" % DB_OBRAS).get("properties", {})
    obras_status   = opcoes(schema_obras, "Status")
    liberada_opts  = opcoes(schema_obras, "LIBERADA PARA INICIAR",
                            "Liberada para iniciar", "Liberada",
                            "Prioritária", "Prioritaria")
    obras = build_obras()

    with open("dist/data_obras.json", "w", encoding="utf-8") as f:
        json.dump({"geradoEm": now,
                   "statusOptions": obras_status,
                   "liberadaOptions": liberada_opts,
                   "obras": obras},
                  f, ensure_ascii=False, indent=2)

    print("data_obras.json      -> %d obras" % len(obras))
    print("  status: %s" % obras_status)
    print("  liberada: %s" % liberada_opts)


if __name__ == "__main__":
    main()
