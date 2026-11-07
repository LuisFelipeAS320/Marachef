import re

import store
from knowledge import normalized

NO_EVIDENCE = "Não encontrei uma orientação documentada para esta pergunta. Consulte o chef responsável."
NO_OFFICIAL = "Não encontrei orientação oficial para esta pergunta na base do Marambaia."
SCOPE_LABELS = {
    "oficial": "Orientação oficial",
    "demo": "Receitas de demonstração · aprovadas para testes técnicos",
    "institucional": "Estudo de caso institucional",
}


def reference(row, scope):
    media_id = row.get("video_id") or row["source_id"]
    url = f"/midia/{media_id}" if row["kind"] != "comentario" or row.get("video_id") else None
    if url and row.get("page"):
        url += f"#page={row['page']}"
    if url and row.get("start_seconds") is not None:
        url += f"#t={row['start_seconds']},{row['end_seconds']}"
    return {
        "title": row["title"], "kind": row["kind"], "scope": scope, "url": url,
        "page": row.get("page"), "step": row.get("step"), "step_index": row.get("step_index"),
        "start": row.get("start_seconds"),
        "end": row.get("end_seconds"), "version": row["version"], "approved_by": row.get("approved_by"),
        "historical": row.get("historical", False),
        "quote": row.get("quote"),
    }


def verify_citations(citations, by_id, scope):
    refs = []
    for citation in citations:
        row = by_id.get(citation.id)
        quote = " ".join(citation.quote.split()).strip('“”"')
        if not row or len(quote) < 8:
            return []
        exact = re.search(re.escape(quote), " ".join(row["body"].split()), re.IGNORECASE)
        if not exact:
            return []
        refs.append(reference(row | {"quote": exact.group()}, scope))
    return refs if any(not ref["historical"] for ref in refs) else []


def respond(ai, question, scope, selected_dish=None, *, fixed_dish=False):
    key = normalized(question)
    if not fixed_dish and re.search(r"\boficia(?:l|is)\b", key):
        if scope != "oficial":
            selected_dish = None
        scope = "oficial"

    def result(answer, *, sources=None, dish_id=None, sufficient=False):
        return {
            "answer": answer, "scope": scope, "scope_label": SCOPE_LABELS[scope],
            "sources": sources or [], "dish_id": dish_id, "sufficient": sufficient,
        }

    dish = None
    if scope != "institucional":
        with store.connect() as db:
            catalog = store.catalog(db, scope)
        if not catalog:
            return result(NO_OFFICIAL if scope == "oficial" else NO_EVIDENCE)
        if not fixed_dish and re.search(r"\b(?:quais|quantos|liste|listar|lista)\b.*\bpratos\b", key):
            dishes = sorted(catalog, key=lambda item: item["name"])
            return result(
                "Pratos registrados nesta base\n" + "\n".join(f"• {item['name']}" for item in dishes),
                sources=[reference(item, scope) for item in dishes], sufficient=True,
            )
        matches = [] if fixed_dish else [
            item for item in catalog
            if any(f" {alias} " in f" {key} " for alias in [item["key"], *item["aliases"]])
        ]
        if len(matches) > 1:
            return result("Qual prato você quer consultar? Selecione um por vez.")
        dish = matches[0] if matches else next((item for item in catalog if item["id"] == selected_dish), None)
        if not dish:
            if re.search(r"\breceita (?:oficial )?d[aeo] \S+", key):
                return result(NO_OFFICIAL if scope == "oficial" else NO_EVIDENCE)
            return result("Qual prato você quer consultar? Informe o nome ou selecione na lista.")

    dish_id = dish["id"] if dish else None
    vector = ai.embed([question], query=True)[0]
    with store.connect() as db:
        rows = store.retrieve(db, scope=scope, dish_id=dish_id, query=question, vector=vector)
        previous = store.previous_evidence(db, {row["revision_id"] for row in rows}, vector) if rows else []
    if not rows:
        return result(NO_EVIDENCE, dish_id=dish_id)
    payload = {
        "pergunta": question, "prato": dish["name"] if dish else None, "base": SCOPE_LABELS[scope],
        "trechos": [
            {field: row[field] for field in ("id", "title", "body", "page", "step", "version", "approved_at", "kind")}
            | {
                "vigente": not row.get("historical", False),
                "inicio_segundos": row["start_seconds"],
                "fim_segundos": row["end_seconds"],
                "ordem_etapa": row["step_index"] + 1 if row["step_index"] is not None else None,
            }
            for row in [*rows, *previous]
        ],
    }
    by_id = {row["id"]: row for row in [*rows, *previous]}
    for _ in range(2):
        answer = ai.answer(payload)
        if not answer.sufficient:
            break
        refs = verify_citations(answer.citations, by_id, scope)
        if refs and answer.answer.strip():
            return result(answer.answer.strip(), sources=refs, dish_id=dish_id, sufficient=True)
        payload["validacao"] = (
            "A primeira resposta não apresentou referências verificáveis. Copie excertos "
            "contínuos dos trechos fornecidos e inclua pelo menos uma fonte vigente."
        )
    return result(NO_EVIDENCE, dish_id=dish_id)
