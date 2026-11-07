import argparse
import getpass
import json
import re
import secrets
from pathlib import Path

from dotenv import set_key
from fastapi import HTTPException
from psycopg import Error

import auth
import demo_bundle
import knowledge
import rag
import store
import workflow
from gemini import Gemini


def ingest(path, scope):
    if path.suffix.lower() != ".pdf":
        raise HTTPException(422, "Selecione um PDF.")
    demo = scope == "demo"
    with path.open("rb") as stream:
        saved, digest = knowledge.save_file(stream, ".pdf", knowledge.PDF_LIMIT)
    keep = False
    try:
        if demo and digest != knowledge.DEMO_DIGEST:
            raise HTTPException(422, "Selecione o PDF de receitas indicado para esta demonstração.")
        pages = knowledge.extract_pages(saved)
        if demo:
            groups = knowledge.demo_chunks(pages)
        else:
            groups = [[chunk for page, body in enumerate(pages, 1)
                       for chunk in knowledge.chunks_for_page(body, page)]]

        def imported(db):
            return db.execute(
                "SELECT count(*) AS count FROM sources WHERE scope = %s AND details->>'sha256' = %s",
                (scope, digest),
            ).fetchone()["count"]

        with store.connect() as db:
            if imported(db):
                print("Documento já importado.")
                return
        ai = Gemini()
        vectors = [ai.embed([chunk["body"] for chunk in chunks]) for chunks in groups]
        with store.connect() as db:
            db.execute("SELECT pg_advisory_xact_lock(76298143)")
            if imported(db):
                print("Documento já importado.")
                return
            for index, chunks in enumerate(groups):
                dish_id = None
                details = {"category": "Contexto institucional", "authority": "Estudo de caso do Marambaia"}
                if demo:
                    name, aliases = knowledge.DEMO_DISHES[index]
                    existing = db.execute("SELECT id FROM dishes WHERE key = %s",
                                          (knowledge.normalized(name),)).fetchone()
                    dish_id = (existing or workflow.create_dish(db, name, aliases))["id"]
                    details = knowledge.DEMO_DETAILS
                source_id = store.create_source(
                    db, dish_id=dish_id, title=knowledge.DEMO_TITLE if demo else path.name,
                    kind="documento", scope=scope, actor="importação local",
                    blob=saved.name, mime="application/pdf", details=details | {"sha256": digest},
                )
                store.publish(db, source_id, 1, {"chunks": chunks}, "importação local", chunks, vectors[index])
        keep = True
        print(f"Importados {sum(map(len, groups))} trechos na base {scope}.")
    finally:
        if not keep:
            saved.unlink(missing_ok=True)


DEMO_QUESTIONS = [
    ("Quais são os pratos registrados?", {2, 4, 6}, ("virada paulista", "costela", "buxada")),
    ("Quantas porções rende a Virada Paulista?", {2}, ("4",)),
    ("Quais são os componentes da Virada Paulista?", {2}, ("tutu", "arroz", "bisteca", "linguica", "couve", "ovo")),
    ("Qual é o tempo total informado para a Costela?", {4}, ("4", "horas")),
    ("Quais são os dois métodos de preparo da Costela?", {4, 5}, ("forno", "pressao")),
    ("Qual é o ponto correto do tutu da Virada Paulista?", {3}, ("creme", "grosso")),
    ("Como o documento descreve o ponto correto do bucho cozido?", {7, 8}, ("macio", "elasti")),
    ("Quais são os erros comuns registrados para a Virada Paulista?", {3, 4, 9}, ("ralo",)),
]


def verify_demo():
    ai = Gemini()
    failures = 0
    for index, (question, pages, terms) in enumerate(DEMO_QUESTIONS):
        result = rag.respond(ai, question, "demo")
        cited = {source["page"] for source in result["sources"] if source["page"] is not None}
        answer = knowledge.normalized(result["answer"])
        valid_pages = pages <= cited if index == 0 else bool(pages & cited)
        valid = result["sufficient"] and valid_pages and all(term in answer for term in terms)
        print(f"{'OK' if valid else 'FALHOU'} — {question} [páginas {sorted(cited)}]")
        print(result["answer"], flush=True)
        failures += not valid
    missing = rag.respond(ai, "Qual é a receita oficial da rabada do Marambaia?", "demo")
    valid = not missing["sufficient"] and missing["scope"] == "oficial" and not missing["sources"]
    print(f"{'OK' if valid else 'FALHOU'} — Rabada oficial sem fonte")
    print(missing["answer"])
    return int(bool(failures or not valid))


def read_password(parser):
    password = getpass.getpass("Senha (mínimo de 12 caracteres): ")
    if not 12 <= len(password) <= 256:
        parser.error("Use uma senha com 12 a 256 caracteres.")
    if password != getpass.getpass("Confirme a senha: "):
        parser.error("As senhas não coincidem.")
    return auth.password_hash(password)


def save_account(name, role, password_hash):
    record = {"role": role, "hash": password_hash}
    path = auth.users_file()
    if path:
        with store.connect() as db:
            db.execute("SELECT pg_advisory_xact_lock(76298144)")
            accounts = auth.users()
            accounts[name] = record
            auth.save_users(path, accounts)
    else:
        accounts = auth.users()
        accounts[name] = record
        set_key(store.ROOT / ".env", "MARACHEF_USERS", json.dumps(accounts))


def main():
    parser = argparse.ArgumentParser(description="Administração local da MaraChef")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("senha", help="Gerar hash scrypt de uma senha")
    account = commands.add_parser("criar-usuario", help="Criar ou atualizar uma conta local")
    account.add_argument("nome")
    account.add_argument("perfil", choices=sorted(auth.ROLES))
    commands.add_parser("segredo", help="Gerar segredo de sessão")
    commands.add_parser("init-db", help="Criar as tabelas no PostgreSQL")
    commands.add_parser("carregar-demo", help="Carregar os pratos e o vídeo do pacote local")
    commands.add_parser("servir-demo", help="Inicializar a demonstração e servir no contêiner")
    commands.add_parser("verificar-demo", help="Executar as perguntas de aceitação usando o Gemini")
    for name in ("importar-demo", "importar-contexto"):
        commands.add_parser(name).add_argument("pdf", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "senha":
            print(read_password(parser))
        elif args.command == "criar-usuario":
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", args.nome):
                parser.error("Use até 64 letras sem acento, números, pontos, hífens ou sublinhados.")
            save_account(args.nome, args.perfil, read_password(parser))
            print("Conta configurada.")
            if not auth.users_file():
                print("Reinicie o servidor se estiver em execução.")
        elif args.command == "segredo":
            print(secrets.token_urlsafe(40))
        elif args.command == "init-db":
            store.initialize()
            print("Banco inicializado.")
        elif args.command in ("carregar-demo", "servir-demo"):
            if args.command == "servir-demo":
                auth.signer()
            store.initialize()
            count = demo_bundle.seed()
            print(f"Pacote de demonstração pronto. {count} fontes adicionadas.")
            if args.command == "servir-demo":
                import uvicorn

                uvicorn.run("app:app", host="0.0.0.0", port=8000)
        elif args.command == "verificar-demo":
            return verify_demo()
        else:
            ingest(args.pdf, "demo" if args.command == "importar-demo" else "institucional")
    except HTTPException as exc:
        parser.exit(1, f"{exc.detail}\n")
    except (OSError, Error) as exc:
        parser.exit(1, f"Operação indisponível ({type(exc).__name__}). Confira o arquivo e a configuração do banco.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
