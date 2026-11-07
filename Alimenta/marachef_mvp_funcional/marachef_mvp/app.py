import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

import auth
import knowledge
import rag
import store
import workflow
from gemini import Gemini, Text, VideoAnalysis

app = FastAPI(title="MaraChef", version="1.0.0")
app.mount("/assets", StaticFiles(directory=store.ROOT / "assets"), name="assets")
SCREENS = ("inicio", "registro", "etapas", "revisao", "biblioteca", "consulta", "receita")
User = Annotated[auth.User, Depends(auth.current_user)]
AI = Annotated[Gemini, Depends(Gemini)]
Scope = Literal["oficial", "demo", "institucional"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class Credentials(BaseModel):
    name: ShortText
    password: str = Field(min_length=1, max_length=256)


class DishInput(BaseModel):
    name: ShortText
    aliases: list[ShortText] = Field(default_factory=list, max_length=15)


class AnalyzeInput(BaseModel):
    id: UUID
    version: int = Field(ge=0)


class ReviewInput(BaseModel):
    version: int = Field(ge=1)
    decision: Literal["salvar", "aprovar", "rejeitar"]
    analysis: VideoAnalysis | None = None
    comment: Text | None = None
    note: Text | None = None


class CommentInput(BaseModel):
    version: int = Field(ge=1)
    stage: int | None = Field(default=None, ge=0)
    text: Text


class ChatInput(BaseModel):
    question: Text
    scope: Scope = "oficial"
    dish_id: UUID | None = None


class RecipeQuestion(BaseModel):
    question: Text


@app.middleware("http")
async def protect_browser(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if (origin and origin != expected) or request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
            return JSONResponse({"detail": "Origem da solicitação inválida."}, status_code=403)
    if request.url.path in ("/api/upload", "/api/documents"):
        length = request.headers.get("content-length")
        limit = knowledge.PDF_LIMIT if request.url.path == "/api/documents" else knowledge.VIDEO_LIMIT
        if length is None or not length.isdecimal():
            return JSONResponse({"detail": "Informe o tamanho do arquivo."}, status_code=411)
        if int(length) > limit + 64 * 1024:
            return JSONResponse({"detail": "Arquivo acima do limite permitido."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    if request.url.path.startswith(("/api/", "/midia/")):
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(_request, _exception):
    return JSONResponse({"detail": "Banco indisponível. Confira a configuração do PostgreSQL."}, status_code=503)


@app.post("/api/login")
def login(payload: Credentials, response: Response):
    user = auth.login(payload.name, payload.password)
    response.set_cookie(
        auth.COOKIE, auth.session_token(user), max_age=auth.SESSION_TTL, httponly=True,
        samesite="strict", secure=os.getenv("MARACHEF_HTTPS_ONLY", "").lower() == "true",
    )
    return user


@app.post("/api/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(auth.COOKIE)


@app.get("/api/me")
def me(user: User):
    return user


@app.get("/api/dishes")
def dishes(user: User, scope: Scope | None = None):
    with store.connect() as db:
        if scope:
            return store.catalog(db, scope)
        return db.execute("SELECT id, name, aliases FROM dishes ORDER BY name").fetchall()


@app.post("/api/dishes", status_code=201)
def new_dish(payload: DishInput, user: User):
    auth.require(user, auth.REVIEWERS)
    with store.connect() as db:
        return workflow.create_dish(db, payload.name, payload.aliases)


@app.get("/api/receitas")
def recipes(user: User):
    with store.connect() as db:
        return store.recipe_catalog(db)


def published_recipe(db, dish_id):
    recipes = store.recipe_catalog(db, dish_id)
    if not recipes:
        raise HTTPException(404, "Ainda não há material publicado para este prato.")
    return recipes[0]


@app.get("/api/receitas/{dish_id}")
def recipe_detail(dish_id: UUID, user: User):
    with store.connect() as db:
        recipe = published_recipe(db, dish_id)
        materials = store.recipe_materials(db, dish_id, recipe["scope"])
    videos, documents = [], []
    for material in materials:
        data = material.pop("data")
        material["url"] = f"/midia/{material['id']}"
        if material["kind"] == "video":
            material["ingredients"] = data["ingredients"]
            material["stages"] = [
                {key: stage[key] for key in ("title", "start", "end", "action", "visual", "landmark")}
                for stage in data["stages"]
            ]
            videos.append(material)
        else:
            material["chunks"] = data["chunks"]
            documents.append(material)
    return {"recipe": recipe, "videos": videos, "documents": documents}


@app.post("/api/receitas/{dish_id}/perguntar")
def recipe_chat(dish_id: UUID, payload: RecipeQuestion, user: User, ai: AI):
    with store.connect() as db:
        recipe = published_recipe(db, dish_id)
    return rag.respond(ai, payload.question, recipe["scope"], dish_id, fixed_dish=True)


@app.get("/api/status")
@app.get("/api/sources")
def sources(user: User):
    reviewer = user.role in auth.REVIEWERS
    with store.connect() as db:
        return db.execute("""
            SELECT s.id, s.title, s.kind, s.scope, s.actor, s.created_at, d.name AS dish,
                   s.active_revision IS NOT NULL AS published, r.status, r.version
            FROM sources s LEFT JOIN dishes d ON s.dish_id = d.id
            LEFT JOIN LATERAL (
                SELECT version, status FROM revisions WHERE source_id = s.id
                  AND (%s OR s.actor = %s OR id = s.active_revision)
                ORDER BY version DESC LIMIT 1
            ) r ON true
            WHERE %s OR s.actor = %s OR s.active_revision IS NOT NULL
            ORDER BY s.created_at DESC
        """, (reviewer, user.name, reviewer, user.name)).fetchall()


@app.get("/api/sources/{source_id}")
def source_detail(source_id: UUID, user: User):
    with store.connect() as db:
        source = store.get_source(db, source_id)
        workflow.require_view(source, user)
        editor = user.role in auth.REVIEWERS or user.name == source["actor"]
        history = db.execute("""
            SELECT id, version, status, actor, created_at,
                   data->>'review_note' AS note
            FROM revisions WHERE source_id = %s AND (%s OR id = %s)
            ORDER BY version DESC
        """, (source_id, editor, source["active_revision"])).fetchall()
        revision = store.latest(db, source_id) if editor else None
        active = db.execute("SELECT * FROM revisions WHERE id = %s",
                            (source["active_revision"],)).fetchone()
        if source["parent_revision"]:
            parent = db.execute("""
                SELECT s.id, s.title, r.version FROM revisions r
                JOIN sources s ON s.id = r.source_id WHERE r.id = %s
            """, (source["parent_revision"],)).fetchone()
        else:
            parent = None
    media = f"/midia/{source_id}" if source.pop("blob") else None
    return {
        "source": source, "draft": workflow.view_revision(revision or active, user, source["kind"]),
        "active": workflow.view_revision(active, user, source["kind"]), "history": history,
        "media": media, "parent": parent, "can_analyze": editor and source["kind"] == "video",
    }


@app.get("/api/sources/{source_id}/versions/{version}")
def source_version(source_id: UUID, version: int, user: User):
    with store.connect() as db:
        source = store.get_source(db, source_id)
        workflow.require_view(source, user)
        revision = db.execute("""
            SELECT * FROM revisions WHERE source_id = %s AND version = %s AND (%s OR id = %s)
        """, (source_id, version, user.role in auth.REVIEWERS or user.name == source["actor"],
              source["active_revision"])).fetchone()
    if not revision:
        raise HTTPException(404, "Versão não encontrada.")
    return workflow.view_revision(revision, user, source["kind"])


@app.get("/midia/{source_id}")
def media(source_id: UUID, user: User):
    with store.connect() as db:
        source = store.get_source(db, source_id)
        workflow.require_view(source, user)
    if not source["blob"]:
        raise HTTPException(404, "Arquivo não encontrado.")
    path = store.UPLOADS / source["blob"]
    if not path.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(
        path, media_type=source["mime"], headers={"Content-Security-Policy": "sandbox"},
    )


@app.post("/api/documents", status_code=201)
def upload_document(document: UploadFile, dish_id: Annotated[UUID, Form()], user: User):
    auth.require(user, {"administrador"})
    title = knowledge.filename(document.filename)
    if Path(title).suffix.lower() != ".pdf":
        raise HTTPException(422, "Envie um documento PDF.")
    path, digest = knowledge.save_file(document.file, ".pdf", knowledge.PDF_LIMIT)
    try:
        if digest in (knowledge.DEMO_DIGEST, knowledge.CASE_DIGEST):
            raise HTTPException(422, "Use a importação da base de demonstração ou institucional para este PDF.")
        pages = knowledge.extract_pages(path)
        with store.connect() as db:
            workflow.dish(db, dish_id)
            source_id = workflow.document_draft(db, dish_id=dish_id, title=title,
                                               blob=path.name, pages=pages, user=user)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"id": source_id, "version": 1}


@app.post("/api/upload", status_code=201)
def upload_video(
    video: UploadFile, dish_id: Annotated[UUID, Form()], cook: Annotated[ShortText, Form()], user: User,
    observations: Annotated[str, Form(max_length=6000)] = "",
    subtitles: Annotated[str, Form(max_length=30_000)] = "",
):
    title = knowledge.filename(video.filename)
    suffix = Path(title).suffix.lower()
    if suffix not in knowledge.VIDEO_TYPES:
        raise HTTPException(422, "Envie vídeo MP4, MOV, WebM ou MKV.")
    mime, demuxer = knowledge.VIDEO_TYPES[suffix]
    path, _ = knowledge.save_file(video.file, suffix, knowledge.VIDEO_LIMIT)
    try:
        duration = knowledge.video_duration(path, demuxer)
        if suffix == ".mkv":
            path = knowledge.normalize_mkv(path, duration)
            mime = "video/mp4"
        with store.connect() as db:
            workflow.dish(db, dish_id)
            source_id = store.create_source(
                db, dish_id=dish_id, title=title, kind="video", scope="oficial",
                actor=user.name, blob=path.name, mime=mime,
                details={"cook": cook, "observations": observations, "subtitles": subtitles,
                         "duration": duration, "category": "Preparo registrado"},
            )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"id": source_id, "version": 0}


@app.post("/api/analyze")
def analyze(payload: AnalyzeInput, user: User, ai: AI):
    return workflow.view_revision(workflow.analyze_video(ai, payload.id, payload.version, user), user, "video")


@app.post("/api/sources/{source_id}/review")
def review(source_id: UUID, payload: ReviewInput, user: User, ai: AI):
    auth.require(user, auth.REVIEWERS)
    return workflow.review(ai, source_id, payload, user)


@app.post("/api/sources/{source_id}/comments", status_code=201)
def add_comment(source_id: UUID, payload: CommentInput, user: User):
    with store.connect() as db:
        source = store.get_source(db, source_id, lock=True)
        workflow.require_view(source, user)
        if source["kind"] != "video" or not source["active_revision"]:
            raise HTTPException(409, "Selecione um vídeo aprovado para adicionar uma observação.")
        version = db.execute("SELECT * FROM revisions WHERE id = %s",
                             (source["active_revision"],)).fetchone()
        if version["version"] != payload.version:
            raise HTTPException(409, "A versão aprovada mudou. Reabra o vídeo.")
        stage = None
        if payload.stage is not None:
            stages = version["data"]["stages"]
            if payload.stage >= len(stages):
                raise HTTPException(422, "Etapa não encontrada.")
            stage = stages[payload.stage]
        comment_id = store.create_source(
            db, dish_id=source["dish_id"], title=f"Observação em {source['title']}",
            kind="comentario", scope=source["scope"], actor=user.name,
            details={"category": "Orientação do chef após validação"},
            parent_revision=version["id"],
        )
        data = {"text": payload.text, "step": stage["title"] if stage else None,
                "stage": payload.stage, "start": stage["start"] if stage else None,
                "end": stage["end"] if stage else None}
        return store.append_revision(db, comment_id, 1, "pendente", data, user.name)


@app.post("/api/chat")
def chat(payload: ChatInput, user: User, ai: AI):
    return rag.respond(ai, payload.question, payload.scope, payload.dish_id)


@app.get("/")
def root():
    return RedirectResponse("/inicio")


@app.get("/{screen}", include_in_schema=False)
def page(screen: str):
    if screen not in SCREENS:
        raise HTTPException(404)
    return FileResponse(store.ROOT / "assets" / "index.html")
