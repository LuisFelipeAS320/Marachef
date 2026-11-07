import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

import knowledge
import store
import workflow
from gemini import DIMENSIONS, EMBEDDING_MODEL, VideoAnalysis, validate_timeline

BUNDLE = store.ROOT / "demo"
PDF_NAME = "receitas-para-iniciantes.pdf"
VIDEO_NAME = "ovos-mexidos-com-cogumelos.webm"
VIDEO_DIGEST = "bdf75917fac15d62c2c2734f2d39d2a450131d63a8c262c077a87fb425c09010"
VIDEO_DISH = "Ovos mexidos com cogumelos e queijo"
VIDEO_SOURCE = "https://commons.wikimedia.org/wiki/File:Scrambled_eggs_with_mushrooms_and_cheese.webm"
ACTOR = "Pacote de demonstração"


@dataclass(frozen=True)
class DemoEntry:
    name: str
    aliases: list[str]
    title: str
    kind: str
    file: Path
    digest: str
    mime: str
    details: dict
    data: dict
    chunks: list[dict]
    vectors: list[list[float]]


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def chunk_digest(chunks):
    bodies = [chunk["body"] for chunk in chunks]
    return hashlib.sha256("\0".join(bodies).encode("utf-8")).hexdigest()


def bundled_vectors(group, chunks):
    vectors = group["vectors"]
    if group["chunk_sha256"] != chunk_digest(chunks) or len(vectors) != len(chunks):
        raise ValueError("Os trechos e os vetores do catálogo não correspondem.")
    if any(len(vector) != DIMENSIONS or not all(map(math.isfinite, vector)) or not any(vector)
           for vector in vectors):
        raise ValueError("O catálogo contém vetores inválidos.")
    return vectors


def read_bundle(directory):
    manifest = json.loads((directory / "catalogo.json").read_text(encoding="utf-8"))
    if (manifest["format"], manifest["model"], manifest["dimensions"]) != (1, EMBEDDING_MODEL, DIMENSIONS):
        raise ValueError("O catálogo da demo usa outro formato ou modelo de embeddings.")

    pdf = directory / PDF_NAME
    video = directory / VIDEO_NAME
    if file_digest(pdf) != knowledge.DEMO_DIGEST or file_digest(video) != VIDEO_DIGEST:
        raise ValueError("O PDF ou o vídeo está diferente do arquivo de referência.")

    entries = []
    groups = knowledge.demo_chunks(knowledge.extract_pages(pdf))
    for (name, aliases), chunks in zip(knowledge.DEMO_DISHES, groups, strict=True):
        entries.append(DemoEntry(
            name, aliases, knowledge.DEMO_TITLE, "documento", pdf, knowledge.DEMO_DIGEST, "application/pdf",
            knowledge.DEMO_DETAILS, {"chunks": chunks}, chunks, bundled_vectors(manifest["pdf"][name], chunks),
        ))

    duration = knowledge.video_duration(video, "matroska")
    analysis = validate_timeline(VideoAnalysis.model_validate(manifest["video"]["analysis"]), duration).model_dump()
    chunks = knowledge.video_chunks(analysis)
    entries.append(DemoEntry(
        VIDEO_DISH, ["ovos mexidos"], VIDEO_DISH, "video", video, VIDEO_DIGEST, "video/webm",
        knowledge.DEMO_DETAILS | {"cook": "Laila Alsabah", "duration": duration, "source_url": VIDEO_SOURCE},
        analysis, chunks, bundled_vectors(manifest["video"], chunks),
    ))
    return entries


def seed(directory=BUNDLE):
    try:
        entries = read_bundle(directory)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, f"Pacote de demonstração inválido. Confira os arquivos em demo/. ({type(exc).__name__})") from exc
    saved = {}
    count = 0
    try:
        with store.connect() as db:
            # Mesmo bloqueio usado pela importação manual do PDF.
            db.execute("SELECT pg_advisory_xact_lock(76298143)")
            for entry in entries:
                dish = db.execute("SELECT id FROM dishes WHERE key = %s",
                                  (knowledge.normalized(entry.name),)).fetchone()
                if not dish:
                    dish = workflow.create_dish(db, entry.name, entry.aliases)
                if db.execute("""
                    SELECT 1 FROM sources WHERE scope = 'demo' AND dish_id = %s
                        AND active_revision IS NOT NULL AND details->>'sha256' = %s
                """, (dish["id"], entry.digest)).fetchone():
                    continue
                if entry.file not in saved:
                    with entry.file.open("rb") as stream:
                        path, digest = knowledge.save_file(stream, entry.file.suffix, knowledge.VIDEO_LIMIT)
                    saved[entry.file] = path
                    if digest != entry.digest:
                        raise HTTPException(422, "Um arquivo da demo mudou durante a importação.")
                source_id = store.create_source(
                    db, dish_id=dish["id"], title=entry.title, kind=entry.kind, scope="demo", actor=ACTOR,
                    blob=saved[entry.file].name, mime=entry.mime, details=entry.details | {"sha256": entry.digest},
                )
                store.publish(db, source_id, 1, entry.data, ACTOR, entry.chunks, entry.vectors)
                count += 1
    except Exception:
        for path in saved.values():
            path.unlink(missing_ok=True)
        raise
    return count
