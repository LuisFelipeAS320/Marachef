import os
import re
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
UPLOADS = ROOT / "data" / "uploads"


def connect():
    url = os.getenv("DATABASE_URL", "")
    if not url and not os.getenv("PGHOST"):
        raise HTTPException(503, "Configure DATABASE_URL no servidor.")
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=5)


def initialize():
    with connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(76298141)")
        db.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))


def get_source(db, source_id, *, lock=False):
    sql = """
        SELECT s.*, d.name AS dish FROM sources s LEFT JOIN dishes d ON d.id = s.dish_id
        WHERE s.id = %s
    """
    row = db.execute(sql + (" FOR UPDATE OF s" if lock else ""), (source_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Fonte não encontrada.")
    return row


def create_source(db, *, dish_id, title, kind, scope, actor, blob=None, mime=None,
                  details=None, parent_revision=None):
    return db.execute("""
        INSERT INTO sources (id, dish_id, title, kind, scope, actor, blob, mime, details, parent_revision)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (uuid4(), dish_id, title, kind, scope, actor, blob, mime,
          Jsonb(details or {}), parent_revision)).fetchone()["id"]


def latest(db, source_id):
    return db.execute("""
        SELECT * FROM revisions WHERE source_id = %s ORDER BY version DESC LIMIT 1
    """, (source_id,)).fetchone()


def check_version(db, source_id, expected):
    revision = latest(db, source_id)
    if (revision["version"] if revision else 0) != expected:
        raise HTTPException(409, "O conteúdo mudou. Reabra a fonte para continuar.")
    return revision


def append_revision(db, source_id, version, status, data, actor):
    # O chamador bloqueia a fonte existente antes de conferir e gravar a versão.
    return db.execute("""
        INSERT INTO revisions (source_id, version, status, data, actor)
        VALUES (%s, %s, %s, %s, %s) RETURNING *
    """, (source_id, version, status, Jsonb(data), actor)).fetchone()


def publish(db, source_id, version, data, actor, chunks, vectors):
    revision = append_revision(db, source_id, version, "aprovado", data, actor)
    with db.cursor() as cursor:
        cursor.executemany("""
            INSERT INTO chunks (revision_id, body, page, step, step_index, start_seconds, end_seconds, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
        """, [
            (revision["id"], chunk["body"], chunk.get("page"), chunk.get("step"), chunk.get("step_index"),
             chunk.get("start"), chunk.get("end"), str(vector))
            for chunk, vector in zip(chunks, vectors, strict=True)
        ])
    db.execute("UPDATE sources SET active_revision = %s WHERE id = %s", (revision["id"], source_id))
    return revision


# Comentários antigos continuam no histórico, mas só a versão ativa do vídeo
# pode fundamentar uma consulta junto com seus comentários.
ACTIVE = """
    JOIN revisions r ON r.id = s.active_revision AND r.status = 'aprovado'
    LEFT JOIN revisions parent ON parent.id = s.parent_revision
    LEFT JOIN sources video ON video.id = parent.source_id
    JOIN chunks c ON c.revision_id = r.id
    WHERE (s.parent_revision IS NULL OR video.active_revision = parent.id)
"""


def catalog(db, scope):
    return db.execute(f"""
        SELECT DISTINCT ON (d.id) d.id, d.name, d.key, d.aliases,
            s.id AS source_id, s.title, s.kind, c.page, c.start_seconds, c.end_seconds, r.version
        FROM dishes d JOIN sources s ON s.dish_id = d.id
        {ACTIVE}
        AND s.scope = %s ORDER BY d.id, s.created_at, c.id
    """, (scope,)).fetchall()


RECIPE_SOURCES = """
    JOIN revisions r ON r.id = s.active_revision AND r.status = 'aprovado'
    WHERE s.kind IN ('video', 'documento') AND s.scope IN ('oficial', 'demo')
"""


def recipe_catalog(db, dish_id=None):
    return db.execute(f"""
        SELECT * FROM (
            SELECT DISTINCT ON (d.id) d.id, d.name, d.aliases, s.scope, s.kind, s.id AS source_id,
                   r.data->>'summary' AS summary,
                   jsonb_array_length(r.data->'stages') AS stage_count,
                   s.details->'duration' AS duration
            FROM dishes d JOIN sources s ON s.dish_id = d.id
            {RECIPE_SOURCES}
            AND (%(id)s::uuid IS NULL OR d.id = %(id)s::uuid)
            ORDER BY d.id, (s.scope = 'oficial') DESC, (s.kind = 'video') DESC, r.created_at DESC, s.id
        ) recipes ORDER BY name
    """, {"id": dish_id}).fetchall()


def recipe_materials(db, dish_id, scope):
    return db.execute(f"""
        SELECT s.id, s.title, s.kind, s.details->>'cook' AS cook,
               s.details->'duration' AS duration, r.version, r.data
        FROM sources s
        {RECIPE_SOURCES}
        AND s.dish_id = %s AND s.scope = %s
        ORDER BY r.created_at DESC, s.id
    """, (dish_id, scope)).fetchall()


def retrieve(db, *, scope, dish_id, query, vector):
    return db.execute(f"""
        WITH ranked AS (
            SELECT c.id, c.body, c.page, c.step, c.step_index, c.start_seconds, c.end_seconds,
                   s.id AS source_id, s.title, s.kind, s.scope, r.id AS revision_id,
                   r.version, r.actor AS approved_by,
                   r.created_at AS approved_at, video.id AS video_id,
                   1 - (c.embedding <=> %(vector)s::vector) AS similarity,
                   ts_rank_cd(c.keywords, plainto_tsquery('portuguese', %(query)s)) AS lexical,
                   ts_rank_cd(c.keywords, to_tsquery('portuguese', %(keywords)s)) AS partial
            FROM sources s
            {ACTIVE}
            AND s.scope = %(scope)s AND s.dish_id IS NOT DISTINCT FROM %(dish_id)s::uuid
        )
        SELECT * FROM ranked WHERE similarity >= 0.35 OR partial > 0
        ORDER BY similarity + LEAST(lexical, 0.3) + LEAST(partial, 0.15) DESC, id
        LIMIT 14
    """, {"scope": scope, "dish_id": dish_id, "query": query, "vector": str(vector),
          "keywords": " | ".join(re.findall(r"[^\W_]+", query.lower())[:45])}).fetchall()


def previous_evidence(db, revision_ids, vector):
    return db.execute("""
        SELECT c.id, c.body, c.page, c.step, c.step_index, c.start_seconds, c.end_seconds,
               s.id AS source_id, s.title, s.kind, s.scope, previous.version,
               previous.actor AS approved_by, previous.created_at AS approved_at, true AS historical
        FROM sources s
        JOIN revisions active ON active.source_id = s.id AND active.id = ANY(%s::bigint[])
        JOIN LATERAL (
            SELECT * FROM revisions
            WHERE source_id = s.id AND status = 'aprovado' AND version < active.version
            ORDER BY version DESC LIMIT 1
        ) previous ON true
        JOIN chunks c ON c.revision_id = previous.id
        WHERE s.kind IN ('documento', 'video')
          AND (c.embedding <=> %s::vector) <= 0.60
        ORDER BY c.embedding <=> %s::vector, c.id LIMIT 4
    """, (list(revision_ids), str(vector), str(vector))).fetchall()
