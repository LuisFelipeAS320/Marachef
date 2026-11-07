from uuid import uuid4

from fastapi import HTTPException

import store
from auth import REVIEWERS
from gemini import validate_timeline
from knowledge import chunks_for_page, normalized, video_chunks


def can_view(source, user):
    return bool(source["active_revision"] or source["actor"] == user.name or user.role in REVIEWERS)


def view_revision(revision, user, kind):
    if not revision or kind != "video" or user.role in REVIEWERS:
        return revision
    return revision | {
        "data": revision["data"] | {
            "stages": [stage | {"inferences": []} for stage in revision["data"]["stages"]],
        },
    }


def require_view(source, user):
    if not can_view(source, user):
        raise HTTPException(404, "Fonte não encontrada.")


def dish(db, dish_id):
    if not db.execute("SELECT id FROM dishes WHERE id = %s", (dish_id,)).fetchone():
        raise HTTPException(404, "Prato não encontrado.")


def create_dish(db, name, aliases):
    key = normalized(name)
    if not key:
        raise HTTPException(422, "Informe um nome de prato válido.")
    keys = sorted({normalized(alias) for alias in aliases} - {"", key})
    db.execute("SELECT pg_advisory_xact_lock(76298142)")
    existing = db.execute("""
        SELECT id, name, key, aliases FROM dishes
        WHERE key = ANY(%s::text[]) OR aliases && %s::text[]
    """, ([key, *keys], [key, *keys])).fetchall()
    if existing:
        raise HTTPException(409, "O nome ou um sinônimo já pertence a um prato.")
    return db.execute("""
        INSERT INTO dishes (id, name, key, aliases) VALUES (%s, %s, %s, %s) RETURNING id, name, aliases
    """, (uuid4(), name, key, keys)).fetchone()


def analyze_video(ai, source_id, version, user):
    with store.connect() as db:
        source = store.get_source(db, source_id)
        require_view(source, user)
        if source["kind"] != "video":
            raise HTTPException(422, "Selecione um vídeo para análise.")
        if source["actor"] != user.name and user.role not in REVIEWERS:
            raise HTTPException(403, "Somente o autor ou um revisor pode analisar este vídeo.")
        locked = db.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired",
                            (f"marachef:video:{source_id}",)).fetchone()["acquired"]
        if not locked:
            raise HTTPException(409, "Este vídeo já está sendo analisado. Aguarde alguns minutos.")
        store.check_version(db, source_id, version)
        # Mantém o bloqueio da sessão durante o Gemini, sem manter uma transação aberta.
        db.commit()
        details = source["details"]
        analysis = ai.analyze(
            store.UPLOADS / source["blob"], source["mime"], details | {"prato": source["dish"]},
            details["duration"], revision=version,
        )
        store.get_source(db, source_id, lock=True)
        store.check_version(db, source_id, version)
        return store.append_revision(db, source_id, version + 1, "pendente", analysis.model_dump(), user.name)


def review(ai, source_id, payload, user):
    with store.connect() as db:
        source = store.get_source(db, source_id)
        revision = store.check_version(db, source_id, payload.version)
    if not revision or revision["status"] != "pendente":
        raise HTTPException(409, "Esta versão não está pendente de revisão.")
    if (payload.analysis and source["kind"] != "video") or (payload.comment and source["kind"] != "comentario"):
        raise HTTPException(422, "A edição não corresponde ao tipo de fonte.")
    data = revision["data"]
    if payload.analysis:
        try:
            validate_timeline(payload.analysis, source["details"]["duration"])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        data = payload.analysis.model_dump()
    if payload.comment:
        data = data | {"text": payload.comment}
    if payload.note:
        data = data | {"review_note": payload.note}

    if payload.decision == "aprovar":
        if source["kind"] == "video":
            chunks = video_chunks(data)
        elif source["kind"] == "comentario":
            chunks = [{"body": data["text"], "step": data["step"], "step_index": data["stage"],
                       "start": data["start"], "end": data["end"]}]
        else:
            chunks = data["chunks"]
        vectors = ai.embed([chunk["body"] for chunk in chunks])
    with store.connect() as db:
        store.get_source(db, source_id, lock=True)
        store.check_version(db, source_id, payload.version)
        if payload.decision == "aprovar":
            if source["kind"] == "comentario":
                parent = db.execute("""
                    SELECT s.active_revision FROM sources s JOIN revisions r ON r.source_id = s.id
                    WHERE r.id = %s FOR UPDATE OF s
                """, (source["parent_revision"],)).fetchone()
                if not parent or parent["active_revision"] != source["parent_revision"]:
                    raise HTTPException(409, "Este comentário pertence a uma versão substituída do vídeo.")
            return store.publish(db, source_id, payload.version + 1, data, user.name, chunks, vectors)
        status = "rejeitado" if payload.decision == "rejeitar" else "pendente"
        return store.append_revision(db, source_id, payload.version + 1, status, data, user.name)


def document_draft(db, *, dish_id, title, blob, pages, user):
    chunks = [chunk for index, page in enumerate(pages, 1) for chunk in chunks_for_page(page, index)]
    source_id = store.create_source(
        db, dish_id=dish_id, title=title, kind="documento", scope="oficial", actor=user.name,
        blob=blob, mime="application/pdf", details={"category": "Ficha técnica"},
    )
    store.append_revision(db, source_id, 1, "pendente", {"chunks": chunks}, user.name)
    return source_id
