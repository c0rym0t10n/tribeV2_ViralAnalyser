from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from analysis_settings import ANALYSIS_MODE_PROFILES, DEFAULT_ANALYSIS_MODE
from brain_visualization import build_brain_simulation
from ollama_runtime import simplify_review_copy
from official_report import generate_official_report
from pdf_report import render_html_pdf, render_pdf_report
from report_localization import (
    get_ui_texts,
    localize_report,
    normalize_report_language,
)
from tribe_review import generate_comparison_report, generate_review
from tribe_review.curve_alignment import (
    _build_curve_drop_moments,
    _build_curve_focus_windows,
    _build_editorial_seek_targets,
    _extract_official_curve_points,
    _rebase_action_items_to_curve,
    _rebuild_editorial_lists,
)
from speech_runtime import SpeechTranscriber
from tribe_runtime import TribeVideoBackend


APP_DIR = Path(__file__).resolve().parent
MEDIA_DIR = APP_DIR / "runtime_media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app = FastAPI(title="TRIBE Review MVP")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
backend = TribeVideoBackend()
speech_backend = SpeechTranscriber()
REPORTS: OrderedDict[str, dict] = OrderedDict()
REPORTS_LOCK = threading.Lock()
MAX_REPORTS = 24
REPORT_JSON_NAME = "report.json"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, lang: str | None = None) -> HTMLResponse:
    language = normalize_report_language(lang)
    return _render_page(
        request,
        result=None,
        error=None,
        language=language,
    )


@app.get("/reports/{report_id}.json")
async def get_report(report_id: str, lang: str | None = None) -> JSONResponse:
    report = _get_stored_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    localized_report = _get_localized_report(report, normalize_report_language(lang))
    return JSONResponse(_public_report(localized_report))


@app.get("/reports/{report_id}.pdf")
async def get_report_pdf(report_id: str, lang: str | None = None) -> StreamingResponse:
    report = _get_stored_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    language = normalize_report_language(lang)
    localized_report = _get_localized_report(report, language)
    renderer = "chrome"
    try:
        pdf_bytes = render_html_pdf(_render_pdf_html(localized_report, language))
    except RuntimeError as exc:
        # Phase 4.1: when Chrome/Edge isn't installed (or can't render), fall
        # back to the matplotlib PDF builder so users on macOS/Linux without a
        # browser still get a downloadable report. The fallback path is also
        # exercised by the `_find_chrome_executable` regression tests.
        message = str(exc).lower()
        if "chrome" in message:
            try:
                pdf_bytes = render_pdf_report(localized_report)
                renderer = "matplotlib"
            except Exception as fallback_exc:  # pragma: no cover - defensive
                raise HTTPException(status_code=500, detail=str(fallback_exc)) from fallback_exc
        else:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    filename = f"tribe-report-{report_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-PDF-Renderer": renderer,
        },
    )


@app.get("/media/{report_id}/{variant_key}")
async def get_media(report_id: str, variant_key: str) -> FileResponse:
    report = _get_stored_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    media_path = report.get("_media_path") if variant_key == "v1" else None
    media_path = media_path or _find_media_file(report_id, variant_key)
    if media_path:
        return FileResponse(media_path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")


@app.get("/reports/{report_id}", response_class=HTMLResponse)
async def view_report(request: Request, report_id: str, lang: str | None = None) -> HTMLResponse:
    report = _get_stored_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    language = normalize_report_language(lang)
    return _render_page(
        request,
        result=_get_localized_report(report, language),
        error=None,
        language=language,
    )


@app.post("/review", response_class=HTMLResponse)
async def review_video(
    request: Request,
    videos: list[UploadFile] = File(...),
    analysis_mode: str = Form(DEFAULT_ANALYSIS_MODE),
    lang: str | None = None,
) -> HTMLResponse:
    report_id = uuid4().hex[:12]
    report_media_dir = MEDIA_DIR / report_id
    language = normalize_report_language(lang)
    selected_analysis_mode = _normalize_analysis_mode(analysis_mode)

    try:
        valid_uploads = [video for video in videos if video.filename]
        if not valid_uploads:
            raise ValueError("Upload one to four video files to run the TRIBE v2 workflow.")
        if len(valid_uploads) > 4:
            raise ValueError("Comparison mode supports up to 4 videos at once.")

        analyzed_variants: list[dict[str, Any]] = []
        editorial_variants: list[dict[str, Any]] = []
        for index, upload in enumerate(valid_uploads, start=1):
            variant_key = f"v{index}"
            result, editorial = await _analyze_upload(
                upload=upload,
                report_id=report_id,
                report_media_dir=report_media_dir,
                variant_key=variant_key,
                analysis_mode=selected_analysis_mode,
            )
            analyzed_variants.append(result)
            if editorial:
                editorial_variant = deepcopy(editorial)
                editorial_variant["variant_key"] = variant_key
                editorial_variant["title"] = result.get("title") or result.get("variant_name") or variant_key
                editorial_variant["variant_name"] = result.get("variant_name") or editorial_variant["title"]
                editorial_variant["media_url"] = result.get("media_url")
                editorial_variant["video"] = deepcopy(result.get("video"))
                editorial_variant["timeline"] = deepcopy(result.get("timeline"))
                editorial_variant["predictions"] = deepcopy(result.get("predictions"))
                editorial_variant["brain_simulation"] = deepcopy(result.get("brain_simulation"))
                editorial_variants.append(editorial_variant)

        if len(analyzed_variants) == 1:
            result = analyzed_variants[0]
        else:
            if len(editorial_variants) != len(analyzed_variants):
                raise ValueError("Comparison needs the local recommendation layer for every uploaded video.")
            result = generate_comparison_report(editorial_variants, analysis_mode=selected_analysis_mode)
            result["report_id"] = report_id
            result["created_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            result["timeline_overlay"] = _build_timeline_overlay(result.get("variants", []))
            result["official_sources"] = analyzed_variants[0].get("official_sources", {})

        _store_report(report_id, result)
        return _render_page(
            request,
            result=_get_localized_report(result, language),
            error=None,
            language=language,
        )
    except Exception as exc:
        return _render_page(
            request,
            result=None,
            error=_format_error(exc, language),
            language=language,
            status_code=500,
        )


def _render_page(
    request: Request,
    result: dict | None,
    error: str | None,
    language: str,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "TRIBE Review MVP",
            "result": result,
            "error": error,
            "language": language,
            "page_base_url": (result or {}).get("report_page_url", "/"),
            "ui": get_ui_texts(language),
        },
        status_code=status_code,
    )


def _render_pdf_html(report: dict, language: str) -> str:
    template = templates.env.get_template("index.html")
    return template.render(
        {
            "title": "TRIBE Review MVP",
            "result": report,
            "error": None,
            "language": language,
            "page_base_url": report.get("report_page_url", "/"),
            "ui": get_ui_texts(language),
            "pdf_mode": True,
        }
    )


async def _analyze_upload(
    upload: UploadFile,
    report_id: str,
    report_media_dir: Path,
    variant_key: str,
    analysis_mode: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    suffix = Path(upload.filename or "input.mp4").suffix or ".mp4"
    target_path = report_media_dir / f"{variant_key}{suffix}"
    report_media_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(await upload.read())

    variant_name = Path(upload.filename or target_path.name).stem
    run = backend.predict_video(target_path)
    result = generate_official_report(
        target_path,
        run,
        variant_name=variant_name,
    )
    result["variant_key"] = variant_key
    result["media_url"] = f"/media/{report_id}/{variant_key}"
    result["_media_path"] = str(target_path)
    result["brain_simulation"] = build_brain_simulation(run.preds, run.timestamps)
    result["report_id"] = report_id
    result["created_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    editorial = _build_editorial_layer(
        target_path,
        run,
        variant_name=variant_name,
        official_result=result,
        analysis_mode=analysis_mode,
    )
    if editorial:
        result["editorial"] = editorial
        result["analysis_mode"] = deepcopy(editorial.get("analysis_mode"))
    else:
        result["analysis_mode"] = {
            "key": analysis_mode,
            "label": analysis_mode,
        }
    return result, editorial


def _get_localized_report(report: dict, language: str) -> dict:
    lang = normalize_report_language(language)
    if report.get("mode") == "compare":
        return localize_report(_refresh_comparison_report(report), lang)
    localized = deepcopy(report)
    editorial = localized.get("editorial")
    if isinstance(editorial, dict):
        _sync_editorial_to_official_curve(editorial, localized)
        localized["editorial"] = localize_report(editorial, lang)
    report_id = localized.get("report_id")
    if report_id:
        localized["report_page_url"] = f"/reports/{report_id}"
        localized["report_url"] = f"/reports/{report_id}.json?lang={lang}"
        localized["report_pdf_url"] = f"/reports/{report_id}.pdf?lang={lang}"
    localized["report_language"] = lang
    return localized


def _refresh_comparison_report(report: dict) -> dict:
    variants = [item for item in report.get("variants", []) if isinstance(item, dict)]
    if len(variants) < 2:
        return deepcopy(report)
    analysis_mode = report.get("analysis_mode") if isinstance(report.get("analysis_mode"), dict) else {}
    refreshed = generate_comparison_report(
        deepcopy(variants),
        analysis_mode=analysis_mode.get("key") or DEFAULT_ANALYSIS_MODE,
    )
    for key in ("report_id", "created_at", "official_sources"):
        if key in report:
            refreshed[key] = deepcopy(report[key])
    refreshed["timeline_overlay"] = _build_timeline_overlay(refreshed.get("variants", []))
    return refreshed


def _build_timeline_overlay(variants: list[dict[str, Any]]) -> dict[str, Any]:
    palette = ["#5db0ff", "#75e08c", "#f6b55a", "#df7cff"]
    max_seconds = 0.0
    for variant in variants:
        points = ((variant.get("timeline") or {}).get("points") or []) if isinstance(variant, dict) else []
        for point in points:
            if isinstance(point, dict):
                max_seconds = max(max_seconds, float(point.get("seconds") or 0.0))
    max_seconds = max(max_seconds, 1.0)

    series: list[dict[str, Any]] = []
    for index, variant in enumerate(variants):
        if not isinstance(variant, dict):
            continue
        points = (variant.get("timeline") or {}).get("points") or []
        svg_points: list[str] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            seconds = float(point.get("seconds") or 0.0)
            score = max(0.0, min(100.0, float(point.get("signal_score") or 0.0)))
            x = 18 + (seconds / max_seconds) * 824
            y = 192 - (score / 100.0) * 174
            svg_points.append(f"{x:.2f},{y:.2f}")
        series.append(
            {
                "variant_key": variant.get("variant_key") or f"v{index + 1}",
                "name": variant.get("title") or variant.get("variant_name") or f"Version {index + 1}",
                "color": palette[index % len(palette)],
                "points": " ".join(svg_points),
                "avg_score": (variant.get("timeline") or {}).get("avg_score"),
                "max_score": (variant.get("timeline") or {}).get("max_score"),
            }
        )
    return {
        "duration_seconds": round(max_seconds, 2),
        "series": series,
    }


def _store_report(report_id: str, report: dict) -> None:
    with REPORTS_LOCK:
        REPORTS[report_id] = report
        REPORTS.move_to_end(report_id)
        while len(REPORTS) > MAX_REPORTS:
            REPORTS.popitem(last=False)
    _write_report_file(report_id, report)


def _get_stored_report(report_id: str) -> dict | None:
    with REPORTS_LOCK:
        report = REPORTS.get(report_id)
        if report is not None:
            return report

    report_path = _report_json_path(report_id)
    if not report_path.exists():
        return None
    try:
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(loaded, dict):
        media_path = _find_media_file(report_id, "v1")
        if media_path:
            loaded["_media_path"] = media_path
        with REPORTS_LOCK:
            REPORTS[report_id] = loaded
            REPORTS.move_to_end(report_id)
            while len(REPORTS) > MAX_REPORTS:
                REPORTS.popitem(last=False)
        return loaded
    return None


def _write_report_file(report_id: str, report: dict) -> None:
    report_path = _report_json_path(report_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(_public_report(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _report_json_path(report_id: str) -> Path:
    return MEDIA_DIR / report_id / REPORT_JSON_NAME


def _find_media_file(report_id: str, variant_key: str) -> str | None:
    media_dir = MEDIA_DIR / report_id
    if not media_dir.exists():
        return None
    matches = sorted(media_dir.glob(f"{variant_key}.*"))
    for path in matches:
        if path.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}:
            return str(path)
    return None


def _public_report(value):
    if isinstance(value, dict):
        return {key: _public_report(item) for key, item in value.items() if not key.startswith("_")}
    if isinstance(value, list):
        return [_public_report(item) for item in value]
    return value


def _build_editorial_layer(
    video_path: Path,
    run,
    variant_name: str,
    official_result: dict[str, Any] | None = None,
    analysis_mode: str = DEFAULT_ANALYSIS_MODE,
) -> dict | None:
    speech = None
    speech_error = None
    try:
        speech = speech_backend.transcribe(video_path, analysis_mode=analysis_mode)
    except Exception as exc:
        speech_error = str(exc).strip()

    try:
        review = generate_review(
            video_path,
            run,
            speech=speech,
            speech_error=speech_error,
            analysis_mode=analysis_mode,
            variant_name=variant_name,
        )
    except Exception:
        return None

    if official_result:
        _seed_editorial_curve_points(review, official_result)

    try:
        review = simplify_review_copy(review)
    except Exception:
        pass

    if official_result:
        _sync_editorial_to_official_curve(review, official_result)
    return review


def _normalize_analysis_mode(value: str | None) -> str:
    if value is None:
        return DEFAULT_ANALYSIS_MODE
    candidate = value.strip().lower()
    if candidate in ANALYSIS_MODE_PROFILES:
        return candidate
    return DEFAULT_ANALYSIS_MODE

def _seed_editorial_curve_points(review: dict[str, Any], official_result: dict[str, Any]) -> None:
    reference_point, dip_points = _extract_official_curve_points(official_result)
    if not reference_point and not dip_points:
        return
    review["focus_windows"] = _build_curve_focus_windows(
        reference_point,
        dip_points,
        [item for item in review.get("focus_windows", []) if isinstance(item, dict)],
    )
    review["drop_moments"] = _build_curve_drop_moments(
        dip_points,
        [item for item in review.get("drop_moments", []) if isinstance(item, dict)],
    )


def _sync_editorial_to_official_curve(review: dict[str, Any], official_result: dict[str, Any]) -> None:
    reference_point, dip_points = _extract_official_curve_points(official_result)
    if not reference_point and not dip_points:
        return

    review["focus_windows"] = _build_curve_focus_windows(
        reference_point,
        dip_points,
        [item for item in review.get("focus_windows", []) if isinstance(item, dict)],
    )
    review["drop_moments"] = _build_curve_drop_moments(
        dip_points,
        [item for item in review.get("drop_moments", []) if isinstance(item, dict)],
    )
    _rebase_action_items_to_curve(review, reference_point, dip_points)
    _rebuild_editorial_lists(review)
    review["seek_targets"] = _build_editorial_seek_targets(review)


def _format_error(exc: Exception, language: str) -> str:
    message = str(exc).strip()
    lowered = message.lower()
    is_llama_gate_error = (
        "meta-llama/llama-3.2-3b" in lowered
        or "trying to access a gated repo" in lowered
        or "access to model meta-llama/llama-3.2-3b is restricted" in lowered
        or "401 client error" in lowered
    )
    is_chrome_missing = "chrome" in lowered and ("not found" in lowered or "required" in lowered)
    is_whisper_download = (
        "whisper" in lowered and ("download" in lowered or "connection" in lowered)
    ) or "no module named 'whisperx'" in lowered or "uvx" in lowered
    is_cuda_error = (
        "cuda" in lowered
        and ("out of memory" in lowered or "no kernel" in lowered or "not available" in lowered)
    )

    if is_chrome_missing:
        if language == "ru":
            return (
                "PDF-отчет не может быть собран: Chrome / Edge / Chromium не найден.\n\n"
                "Что сделать:\n"
                "1. Установить любой из них (Chrome, Edge или Chromium).\n"
                "2. Если установлен в нестандартное место — задать переменную окружения "
                "TRIBE_CHROME_PATH с полным путем к исполняемому файлу.\n\n"
                "Альтернатива: PDF можно скачать в режиме совместимости (matplotlib) — "
                "ответ будет иметь header X-PDF-Renderer: matplotlib."
            )
        return (
            "PDF report can't be built: Chrome / Edge / Chromium not found.\n\n"
            "What to do:\n"
            "1. Install any of them (Chrome, Edge, or Chromium).\n"
            "2. If installed in a non-standard location, set the environment "
            "variable TRIBE_CHROME_PATH to the full path of the executable.\n\n"
            "Alternative: the PDF can still be downloaded in compatibility mode "
            "(matplotlib) — the response will carry header X-PDF-Renderer: matplotlib."
        )

    if is_whisper_download:
        if language == "ru":
            return (
                "Не удалось получить speech transcript.\n\n"
                "Проверь:\n"
                "1. Соединение с интернетом — модель WhisperX скачивается на лету.\n"
                "2. Что установлен uvx (часть uv): pipx install uv или brew install uv.\n"
                "3. Что папка TRIBE_CACHE_DIR доступна для записи.\n"
                "4. Достаточно свободного места на диске для модели Whisper (~5 ГБ).\n\n"
                "Если uvx установлен в нестандартное место — задай TRIBE_UVX_PATH."
            )
        return (
            "Could not fetch the speech transcript.\n\n"
            "Check:\n"
            "1. Internet connectivity — WhisperX is downloaded on demand.\n"
            "2. That uvx (part of uv) is installed: pipx install uv or brew install uv.\n"
            "3. That TRIBE_CACHE_DIR is writable.\n"
            "4. That you have ~5 GB of free disk space for the Whisper model.\n\n"
            "If uvx lives in a non-standard location, set TRIBE_UVX_PATH."
        )

    if is_cuda_error:
        if language == "ru":
            return (
                "GPU/CUDA не может выполнить инференс.\n\n"
                "Возможные причины:\n"
                "- Нехватка VRAM (TRIBE требует >= 6 ГБ).\n"
                "- Драйвер NVIDIA устарел или PyTorch собран без поддержки твоей CUDA.\n"
                "- Видеокарта не NVIDIA.\n\n"
                "Решение: обнови драйвер NVIDIA до последнего, либо запусти приложение "
                "без GPU — TRIBE автоматически переключится на CPU (медленнее, но работает)."
            )
        return (
            "GPU/CUDA can't run inference.\n\n"
            "Possible causes:\n"
            "- Not enough VRAM (TRIBE needs >= 6 GB).\n"
            "- NVIDIA driver is outdated, or PyTorch was built without your CUDA version.\n"
            "- The GPU isn't NVIDIA.\n\n"
            "Fix: update the NVIDIA driver to the latest, or run the app without GPU — "
            "TRIBE will automatically fall back to CPU (slower, still works)."
        )

    if not is_llama_gate_error:
        return message

    if language == "ru":
        return (
            "Официальный TRIBE v2 уперся в gated text encoder из Hugging Face: "
            "meta-llama/Llama-3.2-3B.\n\n"
            "Что нужно сделать:\n"
            "1. Открыть https://huggingface.co/meta-llama/Llama-3.2-3B и запросить доступ.\n"
            "2. Создать read token в Hugging Face.\n"
            "3. Выполнить в PowerShell: huggingface-cli login\n"
            "4. Вставить token и перезапустить приложение.\n\n"
            "Это соответствует официальному workflow TRIBE v2: в опубликованном конфиге "
            "text encoder использует gated LLaMA 3.2-3B."
        )

    return (
        "Official TRIBE v2 hit a gated Hugging Face text encoder: "
        "meta-llama/Llama-3.2-3B.\n\n"
        "What you need to do:\n"
        "1. Open https://huggingface.co/meta-llama/Llama-3.2-3B and request access.\n"
        "2. Create a read token in Hugging Face.\n"
        "3. Run in PowerShell: huggingface-cli login\n"
        "4. Paste the token and restart the app.\n\n"
        "This matches the official TRIBE v2 workflow: the published config uses gated "
        "LLaMA 3.2-3B as the text encoder."
    )
