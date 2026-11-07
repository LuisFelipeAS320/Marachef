import io
import json
import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from fastapi import HTTPException
from google.genai.errors import ServerError
from pypdf import PdfWriter

import auth
import demo_bundle
import knowledge
import manage
import store
from app import app
from gemini import (
    Citation, Gemini, GroundedAnswer, VideoAnalysis, VideoSegmentAnalysis, api_schema, normalize_model_timeline,
    validate_timeline,
)


def analysis():
    return VideoAnalysis.model_validate({
        "summary": "O cozinheiro mostra uma etapa.",
        "ingredients": ["feijão"], "utensils": ["panela"], "unknowns": [],
        "cuts": [{"start": 1, "end": 6, "reason": "Trecho do ponto observado"}],
        "stages": [{
            "title": "Textura", "start": 1, "end": 8, "action": "O cozinheiro mexe o feijão.",
            "visual": "O creme está grosso.", "landmark": "A colher deixa um rastro.",
            "time": "7 segundos de vídeo", "temperature": "não identificada",
            "errors": "não identificada", "comments": [
                {"origin": "áudio", "text": "Já está no ponto.", "timestamp": 3},
            ],
            "inferences": ["Temperatura fictícia de 333 °C"], "unknowns": [],
        }],
    })


class LocalChecks(unittest.TestCase):
    def test_invalid_pdf(self):
        with tempfile.TemporaryDirectory(dir=store.ROOT) as directory:
            path = Path(directory) / "invalid.pdf"
            path.write_bytes(b"not pdf")
            with self.assertRaisesRegex(Exception, "PDF legível"):
                knowledge.extract_pages(path)

    def test_page_number_and_chunk_bounds(self):
        chunks = list(knowledge.chunks_for_page("Primeiro parágrafo.\n\n" + "Tutu grosso. " * 300, 7))
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(chunk["page"] == 7 and len(chunk["body"]) <= 1450 for chunk in chunks))

    def test_video_analysis_rejects_invalid_timeline(self):
        draft = analysis()
        self.assertIs(validate_timeline(draft, 10), draft)
        draft.stages[0].comments[0].timestamp = 9
        with self.assertRaisesRegex(ValueError, "Comentário fora"):
            validate_timeline(draft, 10)
        with self.assertRaisesRegex(ValueError, "Etapa fora"):
            validate_timeline(analysis(), 5)

    def test_model_timeline_sorts_and_limits_rounded_end(self):
        draft = analysis()
        late = draft.stages[0]
        late.end = 8
        late.comments[0].timestamp = 8
        early = late.model_copy(update={"start": 0, "end": 1, "comments": []})
        draft.stages.append(early)
        draft.cuts[0].end = 8
        result = normalize_model_timeline(draft, 7.25)
        self.assertEqual([(stage.start, stage.end) for stage in result.stages], [(0, 1), (1, 7.25)])
        self.assertEqual(result.cuts[0].end, 7.25)
        self.assertIsNone(result.stages[1].comments[0].timestamp)

    def test_video_analysis_retries_invalid_output_using_same_video(self):
        ai = Gemini()
        invalid = analysis()
        invalid.stages[0].end = 99
        with (
            patch.object(ai, "client", return_value=nullcontext(object())),
            patch.object(ai, "video_part", return_value=nullcontext(object())) as video,
            patch.object(ai, "generate", side_effect=[invalid, analysis()]) as generate,
        ):
            result = ai.analyze(Path("example.webm"), "video/webm", {}, 10)
        self.assertEqual(result.stages[0].end, 8)
        video.assert_called_once()
        initial, retry = (json.loads(call.args[1][1].text) for call in generate.call_args_list)
        self.assertEqual(initial["duracao_real_segundos"], 10)
        self.assertEqual(initial["duracao_real_no_relogio"], "00:00:10.000")
        self.assertIn("validacao", retry)

    def test_long_video_resumes_after_transient_failure_and_offsets_timestamps(self):
        ai = Gemini()
        piece = VideoSegmentAnalysis.model_validate(analysis().model_dump())
        with tempfile.TemporaryDirectory(dir=store.ROOT) as directory:
            path = Path(directory) / "uploads" / "original.mp4"
            path.parent.mkdir()
            path.write_bytes(b"fixture")
            with (
                patch.object(ai, "client", return_value=nullcontext(object())),
                patch("gemini.cut_for_analysis", side_effect=lambda _source, target, *_: target.touch()) as cut,
                patch.object(ai, "analyze_clip", side_effect=[
                    piece, ServerError(503, {"error": {"message": "temporariamente indisponível"}}), piece,
                ]) as analyze_clip,
            ):
                with self.assertRaises(HTTPException) as error:
                    ai.analyze(path, "video/mp4", {}, 600)
                self.assertEqual(error.exception.status_code, 503)
                self.assertIn("já foi salvo", error.exception.detail)
                result = ai.analyze(path, "video/mp4", {}, 600)
            self.assertEqual([call.args[2] for call in cut.call_args_list], [0, 300, 300])
            self.assertEqual(analyze_clip.call_count, 3)
            self.assertEqual([stage.start for stage in result.stages], [1, 301])
            self.assertEqual([stage.comments[0].timestamp for stage in result.stages], [3, 303])
            self.assertEqual([item.start for item in result.cuts], [1, 301])
            self.assertEqual(result.ingredients, ["feijão"])

    def test_chat_reports_gemini_unavailable(self):
        ai = Gemini()
        with (
            patch.object(ai, "client", return_value=nullcontext(object())),
            patch.object(ai, "generate", side_effect=ServerError(503, {"error": {"message": "unavailable"}})),
            self.assertRaises(HTTPException) as error,
        ):
            ai.answer({})
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("temporariamente indisponível", error.exception.detail)

    def test_gemini_video_clock_converts_minutes_to_seconds(self):
        data = analysis().model_dump()
        stage = data["stages"][0]
        stage["start"] = "00:01:03"
        stage["end"] = "00:01:36.250"
        stage["comments"][0]["timestamp"] = "00:01:04"
        data["cuts"][0].update(start="00:01:10", end="00:01:20")
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(data)
        ai = Gemini()
        result = ai.generate(client, [], "", VideoAnalysis)
        schema = client.models.generate_content.call_args.kwargs["config"].response_json_schema
        self.assertEqual(schema["$defs"]["Stage"]["properties"]["start"]["type"], "string")
        self.assertEqual(result.stages[0].start, 63)
        self.assertEqual(result.stages[0].end, 96.25)
        self.assertEqual(result.stages[0].comments[0].timestamp, 64)
        self.assertEqual(result.cuts[0].start, 70)
        stage["start"] = 103
        client.models.generate_content.return_value.text = json.dumps(data)
        with self.assertRaisesRegex(ValueError, "HH:MM:SS"):
            ai.generate(client, [], "", VideoAnalysis)

    def test_gemini_schema_preserves_stage_title(self):
        schema = api_schema(VideoAnalysis.model_json_schema())
        self.assertIn("title", schema["$defs"]["Stage"]["properties"])
        self.assertIn("title", schema["$defs"]["Stage"]["required"])
        self.assertNotIn("maxItems", schema["properties"]["stages"])
        self.assertEqual(schema["properties"]["stages"]["items"]["$ref"], "#/$defs/Stage")

    def test_inferences_are_excluded_from_index(self):
        chunks = knowledge.video_chunks(analysis().model_dump())
        self.assertFalse(any("333" in chunk["body"] for chunk in chunks))
        self.assertEqual(next(chunk["start"] for chunk in chunks if "Declarado pelo chef" in chunk["body"]), 3)

    @unittest.skipUnless(os.getenv("MARACHEF_TEST_DEMO_PDF"), "PDF de demonstração não configurado")
    def test_actual_recipe_sections_and_pages(self):
        pages = knowledge.extract_pages(Path(os.environ["MARACHEF_TEST_DEMO_PDF"]))
        virada, costela, buxada = knowledge.demo_chunks(pages)
        for group, locations, words in [
            (virada, {2, 3, 4, 9}, ["4 porções", "creme grosso", "Feijão ou tutu muito ralo"]),
            (costela, {4, 5, 6}, ["4 horas", "Atalho na panela de pressão"]),
            (buxada, {6, 7, 8, 9}, ["Bucho cozido", "elasticidade"]),
        ]:
            self.assertEqual({chunk["page"] for chunk in group}, locations)
            text = " ".join(" ".join(chunk["body"].split()) for chunk in group)
            for phrase in words:
                self.assertIn(phrase, text)
        self.assertFalse(any("Couve amarga" in chunk["body"] for chunk in buxada))
        self.assertFalse(any("Bisteca" in chunk["body"] for chunk in costela))


class GeminiDouble:
    def embed(self, texts, *, query=False):
        return [[1.0] + [0.0] * 767 for _ in texts]

    def analyze(self, *_args, **_kwargs):
        return analysis()

    def answer(self, payload):
        for row in payload["trechos"]:
            if "creme" in row["body"] and "creme" in payload["pergunta"].lower():
                line = next(line for line in row["body"].splitlines() if "creme" in line)
                return GroundedAnswer(sufficient=True, answer=line, citations=[Citation(id=row["id"], quote=line)])
        return GroundedAnswer(sufficient=False, answer="", citations=[])


def test_pdf_bytes():
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    # Conteúdo mínimo gerado para testar ingestão, sem inventar receitas para a base.
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 10 170 Td (O creme esta grosso.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@unittest.skipUnless(os.getenv("MARACHEF_TEST_DATABASE_URL"), "PostgreSQL de testes não configurado")
class ApiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.accounts = json.dumps({
            name: {"role": role, "hash": auth.password_hash("senha-de-teste")}
            for name, role in [("admin", "administrador"), ("chef", "chef"), ("equipe", "funcionario")]
        })

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(patch.stopall)
        patch.object(store, "UPLOADS", Path(self.tmp.name)).start()
        patch.dict(os.environ, {
            "DATABASE_URL": os.environ["MARACHEF_TEST_DATABASE_URL"],
            "MARACHEF_SESSION_SECRET": "segredo-temporario-exclusivo-dos-testes",
            "MARACHEF_HTTPS_ONLY": "false",
            "MARACHEF_USERS": self.accounts,
        }).start()
        self.schema = "teste_" + os.urandom(8).hex()
        with store.connect() as db:
            db.execute("CREATE EXTENSION IF NOT EXISTS vector")
            db.execute(f'CREATE SCHEMA "{self.schema}"')
        connect = store.connect

        def connect_test():
            db = connect()
            db.execute(f'SET search_path TO "{self.schema}", public')
            return db

        def drop_schema():
            with connect() as db:
                db.execute(f'DROP SCHEMA "{self.schema}" CASCADE')

        self.addCleanup(drop_schema)
        patch.object(store, "connect", connect_test).start()
        # Criar as tabelas no esquema isolado, preservando o tipo vector de public.
        with store.connect() as db:
            db.execute((store.ROOT / "schema.sql").read_text().split(";", 1)[1])
        self.ai = GeminiDouble()
        app.dependency_overrides[Gemini] = lambda: self.ai
        self.addCleanup(app.dependency_overrides.clear)
        self.admin = self.client("admin")
        self.chef = self.client("chef")
        self.employee = self.client("equipe")
        dish = self.admin.post("/api/dishes", json={"name": "Feijão de teste"})
        self.assertEqual(dish.status_code, 201, dish.text)
        self.dish = dish.json()["id"]

    def client(self, name):
        client = self.enterContext(TestClient(app))
        result = client.post("/api/login", json={"name": name, "password": "senha-de-teste"})
        self.assertEqual(result.status_code, 200, result.text)
        return client

    def ask(self, question, scope="oficial", dish_id=None):
        result = self.employee.post("/api/chat", json={
            "question": question, "scope": scope, "dish_id": dish_id,
        })
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_document_ingestion_permissions_approval_and_citation(self):
        file = {"document": ("ficha.pdf", test_pdf_bytes(), "application/pdf")}
        denied = self.employee.post("/api/documents", files=file, data={"dish_id": self.dish})
        self.assertEqual(denied.status_code, 403)
        uploaded = self.admin.post("/api/documents", files=file, data={"dish_id": self.dish})
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        source_id = uploaded.json()["id"]
        self.assertEqual(self.chef.get("/api/receitas").json(), [])
        self.assertEqual(self.chef.get(f"/api/receitas/{self.dish}").status_code, 404)
        self.assertEqual(self.employee.get(f"/midia/{source_id}").status_code, 404)
        self.assertFalse(self.ask("Como é o creme do Feijão de teste?")["sufficient"])
        path = f"/api/sources/{source_id}/review"
        payload = {"decision": "aprovar", "version": 1}
        self.assertEqual(self.employee.post(path, json=payload).status_code, 403)
        with patch.object(self.ai, "embed", side_effect=RuntimeError("falha antes da transação")):
            with self.assertRaisesRegex(RuntimeError, "falha antes"):
                self.chef.post(path, json=payload)
        self.assertFalse(self.ask("Como é o creme do Feijão de teste?")["sufficient"])
        approved = self.chef.post(path, json=payload)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(self.chef.post(path, json=payload).status_code, 409)
        self.assertEqual(self.employee.get(f"/midia/{source_id}").status_code, 200)
        recipes = self.employee.get("/api/receitas").json()
        self.assertEqual([(recipe["id"], recipe["kind"]) for recipe in recipes], [(self.dish, "documento")])
        recipe = self.employee.get(f"/api/receitas/{self.dish}").json()
        self.assertEqual(recipe["documents"][0]["chunks"][0]["page"], 1)
        self.assertEqual(recipe["videos"], [])
        answer = self.ask("Como é o creme do Feijão de teste?")
        self.assertTrue(answer["sufficient"])
        self.assertEqual(answer["sources"][0]["page"], 1)
        self.assertEqual(answer["sources"][0]["approved_by"], "chef")
        self.assertFalse(self.ask("Qual é a receita oficial da rabada do Marambaia?", "demo")["sufficient"])
        self.assertFalse(self.ask("Qual a altura da Lua?", dish_id=self.dish)["sufficient"])
        with patch.object(self.ai, "answer", return_value=GroundedAnswer(
            sufficient=True, answer="Invenção", citations=[Citation(id=1, quote="Uma citação fabricada")],
        )):
            self.assertFalse(self.ask("Como é o creme do Feijão de teste?")["sufficient"])

    def test_packaged_demo_seeds_media_without_gemini_and_is_idempotent(self):
        with patch.object(Gemini, "embed", side_effect=AssertionError("A carga local não consulta o Gemini.")):
            self.assertEqual(demo_bundle.seed(), 4)
            self.assertEqual(demo_bundle.seed(), 0)
        self.assertEqual(len(list(store.UPLOADS.iterdir())), 2)
        recipes = self.employee.get("/api/receitas").json()
        self.assertEqual(len(recipes), 4)
        self.assertTrue(all(recipe["scope"] == "demo" for recipe in recipes))
        video_recipe = next(recipe for recipe in recipes if recipe["name"] == demo_bundle.VIDEO_DISH)
        video = self.employee.get(f"/api/receitas/{video_recipe['id']}").json()["videos"][0]
        self.assertEqual(len(video["stages"]), 5)
        self.assertEqual(video["stages"][4]["start"], 63)
        clip = self.employee.get(video["url"], headers={"Range": "bytes=0-7"})
        self.assertEqual(clip.status_code, 206)
        self.assertEqual(clip.content[:4], bytes.fromhex("1a45dfa3"))

    def test_video_draft_comment_and_reanalysis_keep_published_version(self):
        with patch.object(knowledge, "video_duration", return_value=10):
            upload = self.employee.post("/api/upload", data={"dish_id": self.dish, "cook": "Ana"},
                                        files={"video": ("preparo.mp4", b"fixture", "video/mp4")})
        self.assertEqual(upload.status_code, 201, upload.text)
        source = upload.json()["id"]
        path = f"/api/sources/{source}"
        with store.connect() as db:
            db.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (f"marachef:video:{source}",))
            duplicate = self.employee.post("/api/analyze", json={"id": source, "version": 0})
            self.assertEqual(duplicate.status_code, 409)
        draft = self.employee.post("/api/analyze", json={"id": source, "version": 0})
        self.assertEqual(draft.status_code, 200, draft.text)
        self.assertEqual(draft.json()["status"], "pendente")
        self.assertEqual(draft.json()["data"]["stages"][0]["inferences"], [])
        self.assertTrue(self.chef.get(path).json()["draft"]["data"]["stages"][0]["inferences"])
        self.assertFalse(self.ask("Como é o creme do Feijão de teste?")["sufficient"])
        result = self.chef.post(path + "/review", json={"version": 1, "decision": "aprovar"})
        self.assertEqual(result.status_code, 200, result.text)
        with patch.object(self.ai, "embed", side_effect=AssertionError("A lista aprovada não depende do Gemini.")):
            ingredients = self.employee.post(f"/api/receitas/{self.dish}/perguntar", json={
                "question": "Quais são os ingredientes?",
            })
        self.assertEqual(ingredients.status_code, 200, ingredients.text)
        reply = ingredients.json()
        self.assertIn("• feijão", reply["answer"])
        self.assertEqual(reply["sources"][0]["url"], f"/midia/{source}")
        self.assertEqual(reply["sources"][0]["version"], 2)
        self.assertEqual(self.ask("Como é o creme do Feijão de teste?")["sources"][0]["start"], 1)
        clip = self.employee.get(f"/midia/{source}", headers={"Range": "bytes=0-2"})
        self.assertEqual(clip.status_code, 206)
        self.assertEqual(clip.content, b"fix")
        comment = self.employee.post(path + "/comments", json={"version": 2, "stage": 0, "text": "Checar o ponto."})
        self.assertEqual(comment.status_code, 201, comment.text)
        comment_path = f"/api/sources/{comment.json()['source_id']}/review"
        reviewed = self.chef.post(comment_path, json={"version": 1, "decision": "aprovar", "comment": "Conferir o rastro."})
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        again = self.chef.post("/api/analyze", json={"id": source, "version": 2})
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(self.ask("Como é o creme do Feijão de teste?")["sources"][0]["version"], 2)
        rejected = self.chef.post(path + "/review", json={"version": 3, "decision": "rejeitar"})
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(self.chef.get(path).json()["active"]["version"], 2)
        recipe = self.chef.get(f"/api/receitas/{self.dish}").json()
        self.assertEqual(len(self.chef.get("/api/receitas").json()), 1)
        self.assertEqual(recipe["videos"][0]["version"], 2)
        self.assertNotIn("inferences", recipe["videos"][0]["stages"][0])
        self.assertEqual(recipe["documents"], [])
        self.assertEqual(self.employee.get(path + "/versions/4").status_code, 200)  # autor do vídeo
        self.assertEqual(self.chef.post("/api/analyze", json={"id": source, "version": 4}).status_code, 200)
        self.assertEqual(self.chef.post(path + "/review", json={"version": 5, "decision": "aprovar"}).status_code, 200)
        with patch.object(self.ai, "answer", wraps=self.ai.answer) as answer_call:
            response = self.ask("Como é o creme do Feijão de teste?")
        self.assertEqual(response["sources"][0]["version"], 6)
        evidence = answer_call.call_args.args[0]["trechos"]
        self.assertTrue(any(row["version"] == 2 and not row["vigente"] for row in evidence))
        self.assertFalse(any(row["kind"] == "comentario" for row in evidence))

    @unittest.skipUnless(os.getenv("MARACHEF_TEST_DEMO_PDF"), "PDF de demonstração não configurado")
    def test_demo_seed_retrieves_only_correct_recipe(self):
        with patch.object(manage, "Gemini", return_value=self.ai):
            path = Path(os.environ["MARACHEF_TEST_DEMO_PDF"])
            manage.ingest(path, "demo")
            manage.ingest(path, "demo")
        result = self.ask("Quais são os três pratos registrados?", "demo")
        self.assertTrue(result["sufficient"])
        self.assertEqual({source["page"] for source in result["sources"]}, {2, 4, 6})
        self.assertFalse(self.ask("Qual é a receita oficial da Costela?", "demo")["sufficient"])
        with store.connect() as db:
            catalog = store.catalog(db, "demo")
            costela = next(item for item in catalog if item["name"] == "Costela")
            rows = store.retrieve(db, scope="demo", dish_id=costela["id"], query="costela forno",
                                  vector=self.ai.embed(["costela forno"])[0])
        self.assertTrue(any("Atalho na panela de pressão" in row["body"] for row in rows))
        self.assertTrue(all(row["page"] in {4, 5, 6} for row in rows))
        self.assertTrue(all("Tutu de feijão" not in row["body"] for row in rows))
        with patch.object(self.ai, "answer", wraps=self.ai.answer) as answer_call:
            response = self.employee.post(f"/api/receitas/{costela['id']}/perguntar", json={
                "question": "O que a receita oficial da Virada Paulista diz sobre creme?",
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["scope"], "demo")
        self.assertEqual(response.json()["dish_id"], str(costela["id"]))
        self.assertEqual(answer_call.call_args.args[0]["prato"], "Costela")
        official = self.admin.post("/api/documents", files={
            "document": ("ficha.pdf", test_pdf_bytes(), "application/pdf"),
        }, data={"dish_id": str(costela["id"])})
        self.assertEqual(official.status_code, 201, official.text)
        source_id = official.json()["id"]
        approved = self.chef.post(f"/api/sources/{source_id}/review", json={"decision": "aprovar", "version": 1})
        self.assertEqual(approved.status_code, 200, approved.text)
        recipes = self.employee.get("/api/receitas").json()
        self.assertEqual(len(recipes), 3)
        recipe = self.employee.get(f"/api/receitas/{costela['id']}").json()
        self.assertEqual(recipe["recipe"]["scope"], "oficial")
        self.assertEqual([item["id"] for item in recipe["documents"]], [source_id])
