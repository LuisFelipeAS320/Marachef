import hashlib
import json
import math
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pypdf import PdfReader
from pypdf.errors import PyPdfError

import store

PDF_LIMIT = 25 * 1024**2
VIDEO_LIMIT = 200 * 1024**2
PHOTO_LIMIT = 5 * 1024**2
DEMO_DIGEST = "4cff66ad5099eb596e2d1f47b926dad9e7ff126705e56619c01d4fdbfa202cc5"
CASE_DIGEST = "a544e5bc29d2f5208de85dd3ad7b5c90016abd639608d893989983a1e968c193"
DEMO_TITLE = "Receitas para Iniciantes: Virada Paulista, Costela e Buxada"
DEMO_DETAILS = {
    "category": "Receita de teste",
    "restaurant": "Marambaia (ambiente de demonstração)",
    "authority": "Documento de demonstração",
    "approval": "Aprovado para testes técnicos",
}
DEMO_DISHES = [
    ("Virada Paulista", ["virado à paulista", "virado paulista"]),
    ("Costela", ["costela bovina"]),
    ("Buxada (buchada)", ["buxada", "buchada", "buchada nordestina", "bucho"]),
]
VIDEO_TYPES = {
    ".mp4": ("video/mp4", "mov"),
    ".mov": ("video/quicktime", "mov"),
    ".webm": ("video/webm", "matroska"),
    ".mkv": ("video/x-matroska", "matroska"),
}


def media_tool(name):
    directory = os.getenv("FFMPEG_BIN_DIR")
    if directory:
        return str(Path(directory) / (name + (".exe" if os.name == "nt" else "")))
    return name


def normalized(text):
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKD", text.casefold())
                               .encode("ascii", "ignore").decode()))


def documented_ingredients(items):
    unique = {}
    for item in items:
        unique.setdefault(normalized(item), item)
    return list(unique.values())


def filename(value):
    return Path((value or "").replace("\\", "/")).name[:240]


def save_file(stream, suffix, limit):
    store.UPLOADS.mkdir(parents=True, exist_ok=True)
    path = store.UPLOADS / (uuid4().hex + suffix)
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("xb") as output:
            while block := stream.read(1024 * 1024):
                size += len(block)
                if size > limit:
                    raise HTTPException(413, "Arquivo acima do limite permitido.")
                digest.update(block)
                output.write(block)
        if not size:
            raise HTTPException(422, "Arquivo vazio.")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, digest.hexdigest()


def prepare_cover_photo(stream):
    data = stream.read(PHOTO_LIMIT + 1)
    if len(data) > PHOTO_LIMIT:
        raise HTTPException(413, "Envie uma foto de até 5 MB.")
    if data.startswith(b"\xff\xd8\xff"):
        demuxer = "jpeg_pipe"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        demuxer = "png_pipe"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        demuxer = "webp_pipe"
    else:
        raise HTTPException(422, "Envie uma foto em JPG, PNG ou WebP.")

    try:
        result = subprocess.run(
            [media_tool("ffmpeg"), "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "pipe",
             "-max_pixels", "50000000", "-f", demuxer, "-i", "pipe:0", "-frames:v", "1",
             "-vf", "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease",
             "-c:v", "mjpeg", "-q:v", "4", "-f", "image2pipe", "pipe:1"],
            input=data, capture_output=True, check=True, timeout=15,
        )
    except FileNotFoundError as exc:
        raise HTTPException(503, "Instale o FFmpeg no servidor para receber fotos.") from exc
    except subprocess.SubprocessError as exc:
        raise HTTPException(422, "Não foi possível abrir a foto. Confira se o arquivo é válido.") from exc
    if not result.stdout:
        raise HTTPException(422, "Não foi possível abrir a foto. Confira se o arquivo é válido.")
    return result.stdout


def video_duration(path, demuxer):
    try:
        result = subprocess.run(
            [media_tool("ffprobe"), "-v", "error", "-protocol_whitelist", "file", "-f", demuxer,
             "-select_streams", "V:0", "-show_entries", "stream=duration:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=25,
        )
        probe = json.loads(result.stdout)
        streams = probe.get("streams", [])
        if not streams:
            raise ValueError
        container_duration = float(probe["format"]["duration"])
        stream_duration = streams[0].get("duration")
        duration = float(stream_duration) if stream_duration not in (None, "N/A") else container_duration
        if not all(math.isfinite(value) and 0 < value <= 3600
                   for value in (duration, container_duration)):
            raise ValueError
    except FileNotFoundError as exc:
        raise HTTPException(503, "Instale o FFprobe no servidor para receber vídeos.") from exc
    except (ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise HTTPException(422, "Envie um vídeo válido de até 60 minutos.") from exc
    return duration


def normalize_mkv(path, duration):
    converted = path.with_suffix(".mp4")
    try:
        subprocess.run(
            [media_tool("ffmpeg"), "-nostdin", "-v", "error", "-protocol_whitelist", "file",
             "-f", "matroska", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0?",
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-movflags", "+faststart", "-fs", str(VIDEO_LIMIT + 1), str(converted)],
            capture_output=True, check=True, timeout=300,
        )
        if converted.stat().st_size > VIDEO_LIMIT or abs(video_duration(converted, "mov") - duration) > 0.5:
            raise HTTPException(422, "O MKV ultrapassou o limite após a conversão. Envie um MP4 menor.")
        path.unlink()
    except Exception as exc:
        converted.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, FileNotFoundError):
            raise HTTPException(503, "Instale o FFmpeg no servidor ou envie um MP4.") from exc
        raise HTTPException(422, "Não foi possível converter o vídeo MKV para MP4.") from exc
    return converted


def cut_for_analysis(path, target, start, duration):
    try:
        subprocess.run(
            [media_tool("ffmpeg"), "-nostdin", "-v", "error", "-protocol_whitelist", "file",
             "-ss", str(start), "-i", str(path), "-t", str(duration), "-map", "0:V:0", "-map", "0:a:0?",
             "-vf", "fps=12,scale='min(960,iw)':-2", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "80k",
             "-movflags", "+faststart", str(target)],
            capture_output=True, check=True, timeout=180,
        )
        if abs(video_duration(target, "mov") - duration) > 0.5:
            raise HTTPException(422, "Um trecho do vídeo não preservou a duração original.")
    except FileNotFoundError as exc:
        raise HTTPException(503, "Instale o FFmpeg no servidor para analisar vídeos longos.") from exc
    except subprocess.SubprocessError as exc:
        raise HTTPException(422, "Não foi possível preparar um trecho do vídeo para análise.") from exc


def extract_pages(path):
    try:
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError
            stream.seek(0)
            reader = PdfReader(stream)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 200:
                raise ValueError
            pages = [page.extract_text(extraction_mode="layout") for page in reader.pages]
    except (PyPdfError, ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
        raise HTTPException(422, "Envie um PDF legível, sem senha e com até 200 páginas.") from exc
    if not any(page.strip() for page in pages):
        raise HTTPException(422, "O PDF não contém texto extraível. Use OCR antes de enviar.")
    if any(len(page) > 45_000 for page in pages):
        raise HTTPException(422, "Há páginas com texto demais. Divida o documento em arquivos menores.")
    return pages


def chunks_for_page(body, page):
    paragraphs = re.split(r"\n[ \t]*\n+", body.strip())
    pending = ""
    for paragraph in paragraphs:
        paragraph = paragraph.rstrip()
        if not paragraph.strip():
            continue
        if pending and len(pending) + len(paragraph) > 1250:
            yield {"body": pending, "page": page}
            pending = ""
        while len(paragraph) > 1450:
            boundary = max(paragraph.rfind("\n", 950, 1450), paragraph.rfind(" ", 950, 1450))
            boundary = boundary if boundary > 0 else 1450
            yield {"body": paragraph[:boundary].rstrip(), "page": page}
            paragraph = paragraph[boundary:].strip()
        pending = "\n\n".join(filter(None, (pending, paragraph)))
    if pending:
        yield {"body": pending, "page": page}


def linearize_recipe_tables(lines):
    """Leia as células por coluna antes de transformar cada linha em um trecho."""
    header = re.compile(r"^\s*Item\s{2,}Ponto certo\s{2,}Como conferir\s{2,}Se errar\s*$")
    columns = None
    row = None
    output = []
    for line in lines:
        if header.fullmatch(line):
            columns = [line.index(label) for label in ("Item", "Ponto certo", "Como conferir", "Se errar")]
            row = None
            continue
        if line.strip() and not line.startswith(" "):
            columns = None
        if columns is None or not line.strip():
            row = None
            output.append(line)
            continue
        cells = ["" for _ in columns]
        for match in re.finditer(r"\S.*?(?=\s{2,}\S|\s*$)", line):
            column = min(range(len(columns)), key=lambda index: abs(columns[index] - match.start()))
            cells[column] = match.group()
        if row is None:
            row = cells
            output.extend((row, ""))
        else:
            for index, cell in enumerate(cells):
                if cell:
                    separator = "" if row[index].endswith("-") else " "
                    row[index] = (row[index] + separator + cell).strip()
    return [
        f"{line[0]}\nPonto certo: {line[1]}\nComo conferir: {line[2]}\nSe errar: {line[3]}"
        if isinstance(line, list) else line for line in output
    ]


def demo_chunks(pages):
    # Os títulos caem no meio das páginas 2, 4 e 6. Separar só por página
    # atribuiria a tabela de um prato à receita seguinte.
    groups = [[] for _ in DEMO_DISHES]
    current = -1
    headings = {name.casefold(): index for index, (name, _) in enumerate(DEMO_DISHES)}
    for page_number, page in enumerate(pages, 1):
        lines = [line for line in page.splitlines()
                 if line.strip() != DEMO_TITLE and not re.fullmatch(r"Page \d+ of \d+", line.strip())]
        if page_number == 9:
            error_rows = [
                (0, "Feijão ou tutu muito ralo"), (0, "Arroz grudado ou duro"),
                (0, "Couve amarga ou escura"), (2, "Cheiro forte no bucho"),
            ]
            for target, heading in error_rows:
                position = next((i for i, line in enumerate(lines) if line.strip().startswith(heading)), None)
                if position is None:
                    raise HTTPException(422, "Tabela de erros da base de teste não reconhecida.")
                item, remedy = re.split(r"\s{2,}", lines[position].strip(), maxsplit=1)
                remedy += " " + lines[position + 1].strip()
                groups[target].append({"body": f"Erro comum: {item}\nComo evitar: {remedy}", "page": page_number})
            continue
        block = []
        for line in lines:
            key = line.strip().casefold()
            if key in headings:
                if headings[key] != current + 1:
                    raise HTTPException(422, "Ordem das receitas de demonstração não reconhecida.")
                if current >= 0:
                    groups[current].extend(chunks_for_page("\n".join(linearize_recipe_tables(block)), page_number))
                current = headings[key]
                block = []
            if key == "erros comuns e dicas finais":
                break
            block.append(line)
        if current >= 0:
            groups[current].extend(chunks_for_page("\n".join(linearize_recipe_tables(block)), page_number))
    if len(pages) != 9 or not all(groups):
        raise HTTPException(422, "A estrutura do PDF de receitas de demonstração não foi reconhecida.")
    return groups


def video_chunks(analysis):
    chunks = []
    for index, stage in enumerate(analysis["stages"]):
        evidence = [
            stage["title"], f"Ação observada: {stage['action']}", f"Visual observado: {stage['visual']}",
            f"Ponto de referência observado: {stage['landmark']}", f"Tempo e origem: {stage['time']}",
            f"Temperatura e origem: {stage['temperature']}", f"Erros demonstrados: {stage['errors']}",
        ]
        location = {"step": stage["title"], "step_index": index,
                    "start": stage["start"], "end": stage["end"]}
        for chunk in chunks_for_page("\n\n".join(evidence), None):
            chunks.append(chunk | location)
        for comment in stage["comments"]:
            chunks.append({
                **location,
                "body": f"Declarado pelo chef ({comment['origin']}): {comment['text']}",
                "start": comment["timestamp"] if comment["timestamp"] is not None else stage["start"],
            })
    return chunks
