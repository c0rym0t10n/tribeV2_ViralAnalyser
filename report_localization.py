from __future__ import annotations

from copy import deepcopy
from typing import Any

from analysis_settings import ANALYSIS_MODE_PROFILES
SUPPORTED_REPORT_LANGUAGES = ("es", "en")
DEFAULT_REPORT_LANGUAGE = "es"


UI_TEXTS: dict[str, dict[str, str]] = {
    "es": {
        "language": "Idioma",
        "report_language": "Idioma del reporte",
        "language_ru": "Ruso",
        "language_en": "English",
        "open_json": "Abrir JSON",
        "download_pdf": "Descargar PDF",
        "overall_score": "Score total",
        "overall_score_note_single": "Score final del cut.",
        "overall_score_note_compare": "Score de la versión líder.",
        "mode": "Modo",
        "format": "Formato",
        "single_review": "Un solo cut",
        "versions_suffix": "versiones",
        "video_jump_simple": "Video y salto rápido",
        "video_jump": "Video y jump-to-time",
        "timeline_simple": "Curva creativa",
        "timeline_deep": "TRIBE Timeline",
        "timeline_hint": "Pasa el cursor para ver el tiempo. Click en la curva para saltar a ese punto del video.",
        "timeline_level": "Nivel",
        "timeline_signal": "Nivel",
        "avg": "Prom",
        "max": "Máx",
        "min": "Mín",
        "seconds": "s",
        "brain_title": "Simulación de actividad cortical",
        "brain_status": "Ventana actual",
        "frames": "Frames",
        "brain_activity": "Actividad",
        "brain_hotspots": "Hotspots",
        "brain_normal": "Normal",
        "brain_inflated": "Expandido",
        "brain_unavailable": "La vista 3D del cerebro no está disponible para esta corrida.",
        "what_to_do": "Qué cambiar en el video",
        "what_to_keep_change": "Qué dejar y qué cambiar",
        "strengths": "Lo que jala",
        "weaknesses": "Lo que no jala",
        "next_step": "Siguiente paso",
        "open_numbers": "Partes del timeline",
        "open_speech": "Abrir voz y texto",
        "good_bad": "Lo que jala / lo que estorba",
        "already_good": "Lo que jala",
        "gets_in_way": "Lo que estorba",
        "signal_metrics": "Métricas de la curva",
        "windows_phases": "Ventanas y fases clave",
        "speech_title": "Voz",
        "full_text": "Transcripción completa",
        "words": "palabras",
        "speech_chunks": "Segmentos de voz",
        "fix_first": "Qué arreglar primero",
        "footer_simple": "Modo simple: muestra qué dejar en el cut y qué arreglar primero.",
        "footer_deep": "Esta vista trae el reporte completo más una capa de voz/transcript aparte.",
        "compare_summary": "Resumen de la comparativa",
        "compare_axes": "Dónde gana cada versión",
        "compare_table": "Tabla comparativa",
        "variant_breakdown": "Desglose por versión",
        "winner": "Ganadora",
        "strong_block": "Área fuerte",
        "weak_block": "Área floja",
        "new_run": "Corrida nueva",
        "run_hint": "Sube un video para review completo o de 2 a 5 videos y la app compara los cuts.",
        "analysis_mode": "Modo de review",
        "run_analysis": "Correr análisis",
        "choose_files": "Elegir archivos",
        "no_files_selected": "Ningún archivo elegido",
    },
    "en": {
        "language": "Language",
        "report_language": "Report language",
        "language_ru": "Russian",
        "language_en": "English",
        "open_json": "Open JSON",
        "download_pdf": "Download PDF",
        "overall_score": "Overall score",
        "overall_score_note_single": "Final score for this cut.",
        "overall_score_note_compare": "Score of the leading version.",
        "mode": "Mode",
        "format": "Format",
        "single_review": "Single review",
        "versions_suffix": "versions",
        "video_jump_simple": "Video and quick jump",
        "video_jump": "Video and jump-to-time",
        "timeline_simple": "Creative curve",
        "timeline_deep": "TRIBE Timeline",
        "timeline_hint": "Hover to see the time. Click the curve to jump to that point in the video.",
        "timeline_level": "Level",
        "timeline_signal": "Level",
        "avg": "Avg",
        "max": "Max",
        "min": "Min",
        "seconds": "s",
        "brain_title": "Cortex activity simulation",
        "brain_status": "Current window",
        "frames": "Frames",
        "brain_activity": "Activity",
        "brain_hotspots": "Hotspots",
        "brain_normal": "Normal",
        "brain_inflated": "Inflated",
        "brain_unavailable": "The 3D brain view is unavailable for this run.",
        "what_to_do": "What to change in the video",
        "what_to_keep_change": "What to keep and what to change",
        "strengths": "What is working",
        "weaknesses": "What is weak",
        "next_step": "Next step",
        "open_numbers": "Timeline parts",
        "open_speech": "Open speech and text",
        "good_bad": "What is working / what is hurting",
        "already_good": "What is working",
        "gets_in_way": "What is hurting",
        "signal_metrics": "Curve metrics",
        "windows_phases": "Key windows and phases",
        "speech_title": "Speech",
        "full_text": "Full transcript",
        "words": "words",
        "speech_chunks": "Speech segments",
        "fix_first": "What to fix first",
        "footer_simple": "Simple mode shows what to keep in the cut and what to fix first.",
        "footer_deep": "This view shows the full review plus a separate speech/transcript layer.",
        "compare_summary": "Comparison summary",
        "compare_axes": "Where each version wins",
        "compare_table": "Compare table",
        "variant_breakdown": "Version breakdown",
        "winner": "Winner",
        "strong_block": "Strong area",
        "weak_block": "Weak area",
        "new_run": "New run",
        "run_hint": "Upload one video for a full review or 2-5 videos so the app can compare the cuts for you.",
        "analysis_mode": "Review mode",
        "run_analysis": "Run analysis",
        "choose_files": "Choose files",
        "no_files_selected": "No files selected",
    },
}


ANALYSIS_MODE_TEXTS: dict[str, dict[str, dict[str, str]]] = {
    "es": {
        "simplified": {
            "label": "Simplificado",
            "description": "Habla directo: qué dejar, qué arreglar y dónde hacerlo.",
            "note": "Útil cuando quieres un resultado corto sin análisis extra.",
            "comparison_note": "Solo saca las diferencias que se traducen fácil en el siguiente cambio.",
        },
        "deep": {
            "label": "Análisis a profundidad",
            "description": "Detalla todo: dónde aguanta el cut, dónde se cae y por qué.",
            "note": "Útil cuando quieres el desglose completo, no solo una lista de ajustes.",
            "comparison_note": "Muestra al líder y por qué métricas saca la diferencia.",
        },
    },
    "en": {
        "simplified": {
            "label": "Simplified",
            "description": "Uses plain language: what to keep, what to fix, and where to do it.",
            "note": "Best when you want a short working readout without extra analytics.",
            "comparison_note": "Shows only the differences that are easiest to turn into the next edit.",
        },
        "deep": {
            "label": "Deep analysis",
            "description": "Breaks down more detail: where the cut holds, where it drops, and why.",
            "note": "Best when you want a fuller breakdown instead of only a fix list.",
            "comparison_note": "Shows not only the leader, but also which areas create the gap.",
        },
    },
}


METRIC_LABELS = {
    "ru": {
        "Ранний отклик": "Старт графика",
        "Устойчивость отклика": "Как держится график",
        "Плотность переходов": "Темп событий",
        "Стабильность сигнала": "Резкие просадки",
        "Плотность активации": "Средний уровень",
        "Старт графика": "Старт графика",
        "Как держится график": "Как держится график",
        "Темп событий": "Темп событий",
        "Резкие просадки": "Резкие просадки",
        "Средний уровень": "Средний уровень",
        "Первый кадр": "Хук",
        "Интерес держится": "Удержание",
        "Смена кадров": "Темп",
        "Кадр без лишнего": "Чистота кадра",
        "Сила картинки": "Сила визуала",
        "Хук": "Хук",
        "Удержание": "Удержание",
        "Пейсинг": "Темп",
        "Чистота кадра": "Чистота кадра",
        "Сила визуала": "Сила визуала",
    },
    "en": {
        "Ранний отклик": "Curve start",
        "Устойчивость отклика": "How the curve holds",
        "Плотность переходов": "Pace of new events",
        "Стабильность сигнала": "Sharp drops",
        "Плотность активации": "Average level",
        "Старт графика": "Curve start",
        "Как держится график": "How the curve holds",
        "Темп событий": "Pace of new events",
        "Резкие просадки": "Sharp drops",
        "Средний уровень": "Average level",
        "Первый кадр": "Hook",
        "Интерес держится": "Retention",
        "Смена кадров": "Pacing",
        "Кадр без лишнего": "Visual Clarity",
        "Сила картинки": "Visual Punch",
        "Хук": "Hook",
        "Удержание": "Retention",
        "Пейсинг": "Pacing",
        "Чистота кадра": "Visual Clarity",
        "Сила визуала": "Visual Punch",
        "Ранний отклик": "Curve start",
        "Устойчивость отклика": "How the curve holds",
        "Плотность переходов": "Pace of new events",
        "Стабильность сигнала": "Sharp drops",
        "Плотность активации": "Average level",
        "Старт графика": "Curve start",
        "Как держится график": "How the curve holds",
        "Темп событий": "Pace of new events",
        "Резкие просадки": "Sharp drops",
        "Средний уровень": "Average level",
        "Первый кадр": "Hook",
        "Интерес держится": "Retention",
        "Смена кадров": "Pacing",
        "Кадр без лишнего": "Visual Clarity",
        "Сила картинки": "Visual Punch",
        "Хук": "Hook",
        "Удержание": "Retention",
        "Пейсинг": "Pacing",
        "Чистота кадра": "Visual Clarity",
        "Сила визуала": "Visual Punch",
        "Hook": "Hook",
        "Retention": "Retention",
        "Pacing": "Pacing",
        "Visual Clarity": "Visual Clarity",
        "Visual Punch": "Visual Punch",
    },
}


LABEL_MAP_EN = {
    "Лучший кусок": "Best section",
    "Где сократить": "Where to cut",
    "Где сменить кадр": "Where to change the shot",
    "Где усилить начало": "Where to strengthen the hook",
    "Где почистить кадр": "Where to clean up the frame",
    "Где усилить картинку": "Where to punch up the visual",
    "Где дать фразу раньше": "Where to bring the line earlier",
    "Где убрать паузу": "Where to cut the pause",
    "Оставить как есть": "Keep as is",
    "Подрежь затянутый отрезок": "Trim the dragged section",
    "Смени кадр раньше": "Change the shot earlier",
    "Покажи главное раньше": "Show the main thing earlier",
    "Убери лишнее из кадра": "Clean up the frame",
    "Покажи товар крупнее": "Show the product larger",
    "Скажи главное раньше": "Say the main point earlier",
    "Убери длинную паузу": "Cut the long pause",
    "Сделать первым": "Do first",
    "Сделать потом": "Do next",
    "Оставить": "Keep",
    "Сильные стороны": "What is working",
    "Слабые стороны": "What is weak",
    "Следующий шаг": "Next step",
    "Что уже хорошо": "What is working",
    "Что мешает": "What is hurting",
    "Подозрительный момент": "Weak spot",
    "Речь": "Speech",
    "Когда начинается речь": "Voice enters",
    "Темп речи": "Delivery speed",
    "Насколько плотно сказано": "Delivery density",
    "Сколько пауз": "Pauses",
    "Насколько хорошо разобралась речь": "Transcript confidence",
    "Лучший участок": "Best section",
    "Лучший кусок": "Best section",
    "Пик сигнала": "Peak",
    "Сильный момент": "Peak",
    "Слабое окно": "Weak window",
    "Слабое место": "Weak window",
    "Самый резкий переход": "Sharpest transition",
    "Резкая смена": "Sharpest transition",
    "Где чинить первым": "Weak window",
    "Где ускорить": "Where to change the shot",
    "Где ускорить подачу": "Where to tighten delivery",
    "Где сократить": "Where to cut",
    "Сделать первым": "Do first",
    "Сделать потом": "Do next",
    "Проверить после правок": "Check after edits",
    "Оставить": "Keep",
    "Оставить как есть": "Keep as is",
    "Сильные стороны": "What is working",
    "Слабые стороны": "What is weak",
    "Следующий шаг": "Next step",
    "Что уже хорошо": "What is working",
    "Что мешает": "What is hurting",
    "Подозрительный момент": "Weak spot",
    "Речь": "Speech",
    "Когда начинается речь": "Voice enters",
    "Темп речи": "Delivery speed",
    "Насколько плотно сказано": "Delivery density",
    "Сколько пауз": "Pauses",
    "Сказать главное раньше": "Say the main point earlier",
    "Подключить речь раньше": "Bring the speech in earlier",
    "Сожми речь": "Tighten the speech",
    "Подрежь затянутый отрезок": "Trim the dragged section",
    "Смени кадр раньше": "Change the shot earlier",
    "Покажи главное раньше": "Show the main thing earlier",
    "Убери лишнее из кадра": "Clean up the frame",
    "Покажи товар крупнее": "Show the product larger",
    "Убери длинную паузу": "Cut the long pause",
}


def normalize_report_language(language: str | None) -> str:
    value = (language or DEFAULT_REPORT_LANGUAGE).strip().lower()
    return value if value in SUPPORTED_REPORT_LANGUAGES else DEFAULT_REPORT_LANGUAGE


def get_ui_texts(language: str) -> dict[str, str]:
    return UI_TEXTS[normalize_report_language(language)]


def localize_analysis_mode_options(language: str) -> list[dict[str, str]]:
    lang = normalize_report_language(language)
    items: list[dict[str, str]] = []
    for key, profile in ANALYSIS_MODE_PROFILES.items():
        text = ANALYSIS_MODE_TEXTS[lang].get(key, {})
        items.append(
            {
                "key": profile.key,
                "label": text.get("label", profile.label),
                "short_label": profile.short_label if lang == "ru" else text.get("label", profile.short_label),
                "description": text.get("description", profile.description),
            }
        )
    return items


def localize_report(report: dict[str, Any], language: str) -> dict[str, Any]:
    lang = normalize_report_language(language)
    localized = deepcopy(report)
    _decorate_report_urls(localized, lang)
    _localize_analysis_mode(localized, lang)

    for variant in _iter_variants(localized):
        _apply_known_labels(variant, lang)

    if localized.get("mode") == "compare":
        _apply_known_labels(localized, lang)

    if lang == "en":
        _rewrite_english_report(localized)

    localized["report_language"] = lang
    return localized


def _decorate_report_urls(report: dict[str, Any], language: str) -> None:
    report_id = report.get("report_id")
    if not report_id:
        return
    report["report_page_url"] = f"/reports/{report_id}"
    report["report_url"] = f"/reports/{report_id}.json"
    report["report_pdf_url"] = f"/reports/{report_id}.pdf"


def _localize_analysis_mode(report: dict[str, Any], language: str) -> None:
    mode = report.get("analysis_mode")
    if not isinstance(mode, dict):
        return
    text = ANALYSIS_MODE_TEXTS[language].get(str(mode.get("key") or ""), {})
    if text:
        mode["label"] = text.get("label", mode.get("label"))
        mode["description"] = text.get("description", mode.get("description"))
        mode["note"] = text.get("note", mode.get("note"))
        if "comparison_note" in mode:
            mode["comparison_note"] = text.get("comparison_note", mode.get("comparison_note"))


def _iter_variants(report: dict[str, Any]) -> list[dict[str, Any]]:
    if report.get("mode") == "compare":
        return [item for item in report.get("variants", []) if isinstance(item, dict)]
    return [report]


def _apply_known_labels(report: dict[str, Any], language: str) -> None:
    metric_map = METRIC_LABELS["en" if language == "en" else "ru"]

    for metric in report.get("metrics", []):
        if isinstance(metric, dict):
            label = str(metric.get("label") or "")
            metric["label"] = metric_map.get(label, label)

    for row in report.get("comparison_rows", []):
        if isinstance(row, dict):
            label = str(row.get("label") or "")
            row["label"] = metric_map.get(label, label)

    for item in report.get("focus_windows", []):
        if isinstance(item, dict) and language == "en":
            label = str(item.get("label") or "")
            item["label"] = LABEL_MAP_EN.get(label, label)

    for item in report.get("action_items", []):
        if isinstance(item, dict) and language == "en":
            title = str(item.get("title") or "")
            item["title"] = LABEL_MAP_EN.get(title, title)

    for item in report.get("recommendation_plan", []):
        if isinstance(item, dict):
            title = str(item.get("title") or "")
            if language == "en":
                item["title"] = LABEL_MAP_EN.get(title, title)

    speech = report.get("speech")
    if isinstance(speech, dict):
        if language == "en" and speech.get("title"):
            speech["title"] = LABEL_MAP_EN.get(str(speech["title"]), str(speech["title"]))
        for metric in speech.get("metrics", []):
            if isinstance(metric, dict) and language == "en":
                label = str(metric.get("label") or "")
                metric["label"] = LABEL_MAP_EN.get(label, label)

    if language == "en":
        for item in report.get("seek_targets", []):
            if isinstance(item, dict):
                label = str(item.get("label") or "")
                item["label"] = LABEL_MAP_EN.get(label, label)
        for item in report.get("ranking", []):
            if isinstance(item, dict):
                for key in ("strongest", "weakest"):
                    label = str(item.get(key) or "")
                    item[key] = metric_map.get(label, label)
        for item in report.get("axis_winners", []):
            if isinstance(item, dict):
                label = str(item.get("label") or "")
                item["label"] = metric_map.get(label, label)


def _rewrite_english_report(report: dict[str, Any]) -> None:
    if report.get("mode") == "compare":
        for variant in report.get("variants", []):
            if isinstance(variant, dict):
                _rewrite_english_single_report(variant)
        _rewrite_english_compare_report(report)
        return
    _rewrite_english_single_report(report)


def _rewrite_english_single_report(report: dict[str, Any]) -> None:
    analysis_mode = str((report.get("analysis_mode") or {}).get("key") or "")
    metrics = _ordered_metrics(report)
    _rewrite_metric_summaries_en(report)
    _rewrite_drop_moments_en(report)
    _rewrite_speech_en(report)
    _rewrite_brain_simulation_en(report)

    if analysis_mode == "simplified":
        actions = _build_native_english_actions(report, metrics)
        report["action_items"] = actions
        _rewrite_focus_windows_en(report, metrics, simplified=True)
        report["seek_targets"] = _build_seek_targets_en(report)
        report["strengths"] = _build_strengths_en(report, metrics, actions, simplified=True)
        report["weaknesses"] = _build_weaknesses_en(report, metrics, actions, simplified=True)
        report["recommendation_plan"] = _build_plan_en(actions, simplified=True)
        report["recommendations"] = _build_recommendations_en(report, metrics, simplified=True)
        verdict, executive, banner = _build_single_header_en(report, metrics, actions, simplified=True)
        report["verdict"] = verdict
        report["executive_summary"] = executive
        report["product_summary"] = banner
        report["signal_note"] = "Below is a simple read of where the cut looks stronger and where it weakens."
        report["copy_rewrite"] = {"provider": "native_en"}
        return

    actions = _rewrite_action_items_en(report, metrics)
    if actions:
        report["action_items"] = actions
    _rewrite_focus_windows_en(report, metrics, simplified=False)
    report["seek_targets"] = _build_seek_targets_en(report)
    report["phase_notes"] = _build_phase_notes_en(report)
    report["strengths"] = _build_strengths_en(report, metrics, None, simplified=False)
    report["weaknesses"] = _build_weaknesses_en(report, metrics, None, simplified=False)
    report["recommendations"] = _build_recommendations_en(report, metrics, simplified=False)
    report["recommendation_plan"] = _build_plan_en(report.get("recommendations"), simplified=False)
    verdict, executive, banner = _build_single_header_en(report, metrics, actions, simplified=False)
    report["verdict"] = verdict
    report["executive_summary"] = executive
    report["product_summary"] = banner
    report["signal_note"] = "This is a practical read of the curve: where it rises, where it drops, and what to test next."


def _rewrite_english_compare_report(report: dict[str, Any]) -> None:
    ranking = [item for item in report.get("ranking", []) if isinstance(item, dict)]
    if not ranking:
        return

    best = ranking[0]
    runner_up = ranking[1] if len(ranking) > 1 else ranking[0]
    delta = int(best.get("overall_score") or 0) - int(runner_up.get("overall_score") or 0)
    top_axes = [str(item.get("label") or "") for item in report.get("axis_winners", []) if isinstance(item, dict)][:2]
    report["title"] = f"Comparison of {report.get('variant_count', len(ranking))} versions"
    report["verdict"] = _build_compare_verdict_en(best, runner_up, delta)
    report["executive_summary"] = _build_compare_executive_summary_en(best, runner_up, delta, top_axes)
    report["common_gaps"] = _build_common_gaps_en(report)
    report["product_summary"] = _build_compare_banner_en(best, report["common_gaps"])
    report["recommendations"] = _build_compare_recommendations_en(best, report["common_gaps"])
    report["signal_note"] = "Every version is judged on the same curve. The winner is the cut with the stronger start, higher average level, and fewer sharp drops."

    for item in ranking:
        strongest = str(item.get("strongest") or "")
        weakest = str(item.get("weakest") or "")
        item_delta = int(best.get("overall_score") or 0) - int(item.get("overall_score") or 0)
        if item_delta == 0:
            item["summary"] = f"Current leader. It wins mostly on {strongest} and avoids the largest drops seen in the other versions."
        elif item_delta <= 6:
            item["summary"] = f"Close to the leader. The main drag is {weakest}."
        else:
            item["summary"] = f"Noticeably behind the leader. Its best area is {strongest}, but {weakest} pulls the total down."

    for item in report.get("axis_winners", []):
        if isinstance(item, dict):
            item["summary"] = f"{item.get('winner_name', 'This cut')} has the clearest edge on {item.get('label', 'this area')}."


def _rewrite_metric_summaries_en(report: dict[str, Any]) -> None:
    for metric in report.get("metrics", []):
        if not isinstance(metric, dict):
            continue
        key = str(metric.get("key") or "")
        score = int(metric.get("score") or 0)
        metric["summary"] = _metric_summary_en(key, score)


def _rewrite_drop_moments_en(report: dict[str, Any]) -> None:
    for item in report.get("drop_moments", []):
        if isinstance(item, dict):
            item["reason"] = "This is where the cut loses energy."


def _rewrite_speech_en(report: dict[str, Any]) -> None:
    speech = report.get("speech")
    if not isinstance(speech, dict):
        return

    speech["title"] = "Speech"
    if speech.get("available"):
        speech["note"] = "This is the separate Whisper transcript layer. Use it to inspect timing, pauses, and wording next to the curve."
    else:
        original_message = str(speech.get("message") or "").strip()
        if ":" in original_message and ("Транскрипция" in original_message or "не поднялась" in original_message):
            reason = original_message.split(":", 1)[1].strip()
            speech["message"] = f"Transcript startup failed: {reason}"
        else:
            speech["message"] = "No reliable speech was detected for this run."
        speech["note"] = "This is the separate Whisper transcript layer. It helps inspect timing and delivery, but it is separate from the curve."

    for metric in speech.get("metrics", []):
        if not isinstance(metric, dict):
            continue
        key = str(metric.get("key") or "")
        metric["label"] = _speech_metric_label_en(key, str(metric.get("label") or ""))
        metric["summary"] = _speech_metric_summary_en(key, metric.get("value"))


def _rewrite_brain_simulation_en(report: dict[str, Any]) -> None:
    brain = report.get("brain_simulation")
    if not isinstance(brain, dict):
        return
    if brain.get("available"):
        brain["message"] = "Rotate the gray 3D model with the mouse. Bright hotspots show where the cut is landing stronger right now."


def _ordered_metrics(report: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = report.get("metrics")
    if not isinstance(metrics, list):
        return []
    collected: list[dict[str, Any]] = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        collected.append(
            {
                "key": key,
                "label": str(item.get("label") or "").strip(),
                "score": int(item.get("score") or 0),
            }
        )
    return sorted(collected, key=lambda metric: metric["score"], reverse=True)


def _metric_summary_en(metric_key: str, score: int) -> str:
    bucket = "high" if score >= 75 else "mid" if score >= 60 else "low"
    library = {
        "early_response": {
            "high": "The main thing is clear from the first shot.",
            "mid": "The opening is okay, but the main subject could appear earlier and bigger.",
            "low": "The hook is weak. The main thing shows up too late or is not clear enough right away.",
        },
        "sustain": {
            "high": "The cut keeps introducing enough change to hold attention.",
            "mid": "Retention is uneven. Some sections sit too long without anything new.",
            "low": "There are sections with no new action or no new visual, so the cut feels skippable.",
        },
        "transition": {
            "high": "The shots change at the right time.",
            "mid": "The pacing is workable, but some shots hang a little too long.",
            "low": "The shots change too late, so the cut starts to drag.",
        },
        "stability": {
            "high": "The frame is easy to read. One main subject wins the attention quickly.",
            "mid": "Some frames feel crowded with extra objects, small text, or a noisy background.",
            "low": "Too many elements compete inside the frame, so the main point gets lost.",
        },
        "density": {
            "high": "The visual is strong: the subject reads well, motion is visible, and contrast holds.",
            "mid": "The visual is fine, but the subject gets small, motion is limited, or contrast is weak.",
            "low": "The visual feels weak: not enough scale, motion, or contrast to really pull the eye.",
        },
    }
    return library.get(metric_key, {}).get(bucket, "")


def _native_action_library_en(metric_key: str) -> dict[str, str]:
    library = {
        "early_response": {
            "title": "Show the main thing earlier",
            "instruction": "Show the main thing in the first shot, cut the long setup, and land the key line earlier.",
            "keep": "Keep this opening as a reference. The main thing reads fast here.",
            "focus_label": "Where to strengthen the hook",
            "focus_summary": "Show the main thing earlier and cut the long setup.",
        },
        "sustain": {
            "title": "Cut this section",
            "instruction": "Cut this section, trim the pause, or change the shot earlier.",
            "keep": "Keep this section as a reference. The pace already holds here.",
            "focus_label": "Where to cut",
            "focus_summary": "Cut this section or change the shot earlier.",
        },
        "transition": {
            "title": "Change the shot earlier",
            "instruction": "Change the shot earlier, trim the hanging shot, or add another angle.",
            "keep": "Keep this shot pace as a reference. It already works.",
            "focus_label": "Where to change the shot",
            "focus_summary": "Change the shot earlier or trim part of the setup.",
        },
        "stability": {
            "title": "Clean up the frame",
            "instruction": "Remove extra text or background clutter and leave one main subject in the frame.",
            "keep": "Keep this frame as a reference. The main point is easy to read here.",
            "focus_label": "Where to clean up the frame",
            "focus_summary": "Remove the extra elements and leave one clear focus.",
        },
        "density": {
            "title": "Make the visual stronger",
            "instruction": "Show the subject bigger, add motion, or push the contrast.",
            "keep": "Keep this scale and contrast as a reference. This section looks stronger than the rest.",
            "focus_label": "Where to punch up the visual",
            "focus_summary": "Show the subject bigger or add more visible motion.",
        },
        "speech_start": {
            "title": "Say the main line earlier",
            "instruction": "Bring the main line earlier or cut the silent setup.",
            "keep": "",
            "focus_label": "Where to bring the line earlier",
            "focus_summary": "Bring the main line earlier and trim the silent setup.",
        },
        "pause": {
            "title": "Cut the long pause",
            "instruction": "Trim the pause between lines or tighten the delivery.",
            "keep": "",
            "focus_label": "Where to cut the pause",
            "focus_summary": "Trim the pause or tighten the delivery.",
        },
    }
    return library.get(metric_key, library["sustain"])


def _build_native_english_actions(report: dict[str, Any], metrics: list[dict[str, Any]]) -> list[dict[str, str]]:
    strongest = metrics[0] if metrics else {"key": "sustain"}
    weakest = metrics[-1] if metrics else {"key": "sustain"}
    runner = metrics[-2] if len(metrics) > 1 else weakest
    windows = [item for item in report.get("focus_windows", []) if isinstance(item, dict)]
    best_window = windows[0] if windows else None
    weak_window = windows[1] if len(windows) > 1 else None
    dynamic_window = windows[2] if len(windows) > 2 else None

    items: list[dict[str, str]] = []
    if weak_window and weak_window.get("timestamp"):
        items.append(_make_action_item_en(str(weak_window["timestamp"]), str(weakest["key"])))
    if best_window and best_window.get("timestamp"):
        items.append(_make_keep_item_en(str(best_window["timestamp"]), str(strongest["key"])))
    if dynamic_window and dynamic_window.get("timestamp"):
        items.append(_make_action_item_en(str(dynamic_window["timestamp"]), "transition"))

    for moment in report.get("drop_moments", []):
        if isinstance(moment, dict) and moment.get("timestamp"):
            items.append(_make_action_item_en(str(moment["timestamp"]), str(runner["key"])))

    speech = report.get("speech")
    if isinstance(speech, dict) and speech.get("available"):
        speech_start = speech.get("speech_start_seconds")
        if isinstance(speech_start, (int, float)) and float(speech_start) > 2.0:
            items.append(_make_action_item_en(_format_seconds_for_copy(float(speech_start)), "speech_start"))
        pause_ratio = speech.get("pause_ratio")
        if isinstance(pause_ratio, (int, float)) and float(pause_ratio) > 0.28:
            fallback_ts = _fallback_action_timestamp(report)
            if fallback_ts:
                items.append(_make_action_item_en(fallback_ts, "pause"))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item["timestamp"], item["title"])
        if key in seen or not item["timestamp"]:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:4]


def _make_action_item_en(timestamp: str, metric_key: str) -> dict[str, str]:
    action = _native_action_library_en(metric_key)
    return {"timestamp": timestamp, "title": action["title"], "instruction": action["instruction"], "why": ""}


def _make_keep_item_en(timestamp: str, metric_key: str) -> dict[str, str]:
    action = _native_action_library_en(metric_key)
    instruction = action["keep"] or "Keep this section as a reference. It already works."
    return {"timestamp": timestamp, "title": "Keep as is", "instruction": instruction, "why": ""}


def _rewrite_action_items_en(report: dict[str, Any], metrics: list[dict[str, Any]]) -> list[dict[str, str]]:
    source = report.get("action_items")
    if not isinstance(source, list):
        return []

    fallback_keys = [str(metric.get("key") or "sustain") for metric in reversed(metrics)] or ["sustain"]
    usage: dict[str, int] = {}
    rewritten: list[dict[str, str]] = []
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            continue
        timestamp = str(item.get("timestamp") or "").strip()
        if not timestamp:
            continue
        metric_key = _infer_action_metric_key_en(item) or fallback_keys[min(index, len(fallback_keys) - 1)]
        variant_index = usage.get(metric_key, 0)
        usage[metric_key] = variant_index + 1
        action = _native_action_variant_en(metric_key, variant_index)
        rewritten.append(
            {
                "timestamp": timestamp,
                "title": action["title"],
                "instruction": action["instruction"],
                "why": "",
            }
        )
    return rewritten[:6]


def _infer_action_metric_key_en(item: dict[str, Any]) -> str | None:
    text = " ".join(
        str(item.get(key) or "")
        for key in ("title", "instruction", "why")
    ).lower()
    checks = [
        ("early_response", ("main thing earlier", "show the main", "hook", "главное раньше", "подводк", "заход", "первый кадр", "усиль старт", "старт", "результат раньше")),
        ("sustain", ("dragged", "cut this section", "trim this section", "затянут", "не провисал", "темп плотнее", "провис", "середин", "повтор", "payoff")),
        ("transition", ("change the shot", "shot earlier", "visual accent", "кадр раньше", "визуальный акцент", "план", "ракурс", "событие", "смен")),
        ("stability", ("clean up the frame", "frame clearer", "clutter", "лишнее", "фокус", "композици", "просадк", "объект от фона", "центр внимания")),
        ("density", ("product larger", "visual stronger", "visual punch", "крупнее", "контраст", "товар", "картин", "средний уровень", "визуальный", "пользу видимой")),
        ("speech_start", ("main line", "say the main", "фраз", "речь раньше")),
        ("pause", ("pause", "пауза", "промежуток")),
    ]
    for key, needles in checks:
        if any(needle in text for needle in needles):
            return key
    return None


def _native_action_variant_en(metric_key: str, variant_index: int) -> dict[str, str]:
    variants = {
        "early_response": [
            {"title": "Show the main thing earlier", "instruction": "Move the main shot or offer closer to this point. Remove the long setup before it."},
            {"title": "Start with the result", "instruction": "Put a frame before this point where the viewer immediately understands the payoff."},
            {"title": "Cut the setup", "instruction": "If this section has an intro before the action, remove it and start closer to the useful moment."},
            {"title": "Strengthen the first shot", "instruction": "Open with the subject, result, or conflict instead of a neutral lead-in."},
            {"title": "Bring the subject forward", "instruction": "Make the main subject larger or closer to center before the weak point."},
            {"title": "Start with action", "instruction": "Replace a calm entry with motion, a gesture, or a visible change."},
            {"title": "Move a stronger frame up", "instruction": "Take the nearest stronger frame after the dip and test it earlier."},
            {"title": "Shorten the empty start", "instruction": "Remove frames where the viewer still does not know what to watch."},
            {"title": "Make the context immediate", "instruction": "Add a short visual cue so the point is clear before the weak section."},
            {"title": "Make the entry sharper", "instruction": "Use less pause, a larger subject, and a clearer action in the first seconds."},
        ],
        "sustain": [
            {"title": "Trim the slow section", "instruction": "Remove 1-2 seconds before this point or move to the next action faster."},
            {"title": "Add a new beat", "instruction": "Before this point, add a new detail, movement, or shot change so the cut does not sag."},
            {"title": "Tighten the pace", "instruction": "Compress the pause and keep only frames that move the scene forward."},
            {"title": "Refresh the middle", "instruction": "Add a new piece of information here: reaction, detail, result, or changed action."},
            {"title": "Cut the repeat", "instruction": "If the shot repeats an idea that is already clear, keep only the strongest part."},
            {"title": "Change shot size", "instruction": "Before the dip, switch scale: close-up, wide shot, or detail."},
            {"title": "Add a small payoff", "instruction": "Show a quick mini-result before the curve starts to fall."},
            {"title": "Move the event closer", "instruction": "If the important action happens later, test it 1-2 seconds earlier."},
            {"title": "Remove the neutral shot", "instruction": "Replace a frame with no new information with movement or reaction."},
            {"title": "Break the long shot", "instruction": "Split a static section with a quick angle change or detail insert."},
        ],
        "transition": [
            {"title": "Change the shot earlier", "instruction": "Change the shot, angle, or action earlier so this section does not drag."},
            {"title": "Add a visual accent", "instruction": "Before this point, add movement, a gesture, a push-in, or a change in shot size."},
            {"title": "Remove the hanging shot", "instruction": "If the frame sits without new action, cut it down to the first clear movement."},
            {"title": "Insert a detail", "instruction": "Add a short close-up that gives the viewer something new to read."},
            {"title": "Change the angle", "instruction": "Keep the same action but show it from another angle before the dip."},
            {"title": "Add a reaction", "instruction": "Insert a reaction or consequence if the scene has a person, animal, or active object."},
            {"title": "Speed up the edit", "instruction": "Test a shorter version of this shot without changing the meaning."},
            {"title": "Make the transition clearer", "instruction": "Use motion or action matching so the change feels intentional, not random."},
            {"title": "Split the repetitive section", "instruction": "Turn a long fragment into two visual phases: before and after, setup and result."},
            {"title": "Add a text cue", "instruction": "If the image repeats itself, add a short caption with new information."},
        ],
        "stability": [
            {"title": "Clean up the frame", "instruction": "Keep one main subject and remove extra details or text around it."},
            {"title": "Make the focus clearer", "instruction": "Make the main subject easier to read through size, position, or a cleaner background."},
            {"title": "Reduce visual clutter", "instruction": "Remove competing elements so the viewer's eye does not split between details."},
            {"title": "Hide extra text", "instruction": "If there are too many words near the subject, keep one short caption or remove it."},
            {"title": "Enlarge the subject", "instruction": "Make the important object bigger so it does not compete with the background."},
            {"title": "Clean the background", "instruction": "Test the frame without distracting objects, glare, or busy details behind the action."},
            {"title": "Clarify the motion", "instruction": "If the action is too small, show it closer or from a more readable angle."},
            {"title": "Remove the second focal point", "instruction": "Keep one main focus and darken, crop, or delay the secondary object."},
            {"title": "Calm the camera", "instruction": "If the dip sits near shake or a sudden move, test a steadier fragment."},
            {"title": "Separate subject and background", "instruction": "Use light, color, or framing so the main thing does not blend in."},
        ],
        "density": [
            {"title": "Show the product larger", "instruction": "Make the object bigger, strengthen the motion in frame, or add contrast."},
            {"title": "Increase the visual punch", "instruction": "Before this point, add a brighter frame, a close-up, or a more visible action."},
            {"title": "Make the frame more contrasty", "instruction": "Separate the main subject from the background with light, color, or cleaner composition."},
            {"title": "Raise the average level", "instruction": "Improve the ordinary frames around this point, not only the best peak."},
            {"title": "Add motion", "instruction": "If the frame is static, test hand, camera, object, or position movement."},
            {"title": "Show a closer detail", "instruction": "Insert a close-up of the detail the viewer should notice."},
            {"title": "Replace the flat frame", "instruction": "Swap a neutral fragment for a shot with clearer action or emotion."},
            {"title": "Make the benefit visible", "instruction": "If the product or result is hard to read, show its effect directly in frame."},
            {"title": "Add visual contrast", "instruction": "Try a brighter subject on a darker background, color accent, or cleaner composition."},
            {"title": "Tighten the scene", "instruction": "Remove weak in-between frames and keep the shots where subject, action, and point are clear."},
        ],
        "speech_start": [
            {"title": "Say the main line earlier", "instruction": "Move the key line before this point or cut the silent lead-in."},
            {"title": "Move the line forward", "instruction": "Place the key spoken line closer to the start of the weak section."},
            {"title": "Open with a short line", "instruction": "Add one clear sentence before the dip, without a long explanation."},
            {"title": "Cut the silent lead-in", "instruction": "If silent first seconds do not work, shorten them or place the key thought over them."},
            {"title": "Match line and frame", "instruction": "Let the important phrase happen when the main subject is already visible."},
        ],
        "pause": [
            {"title": "Cut the pause", "instruction": "Trim the empty gap or deliver the phrase more tightly so the section does not dip."},
            {"title": "Tighten the speech", "instruction": "Shorten the pause between words and keep only the needed phrase."},
            {"title": "Tighten the delivery", "instruction": "Make the line shorter and closer to the action in frame."},
            {"title": "Cover the empty gap", "instruction": "If the pause must stay, cover it with action, reaction, or a close-up."},
            {"title": "Split the long line", "instruction": "Break the speech into shorter chunks and place each one near the matching shot."},
        ],
    }
    options = variants.get(metric_key) or variants["sustain"]
    return options[variant_index % len(options)]


def _rewrite_focus_windows_en(report: dict[str, Any], metrics: list[dict[str, Any]], simplified: bool) -> None:
    windows = report.get("focus_windows")
    if not isinstance(windows, list):
        return

    if simplified:
        strongest = metrics[0]["key"] if metrics else "sustain"
        weakest = metrics[-1]["key"] if metrics else "sustain"
        if len(windows) >= 1 and isinstance(windows[0], dict):
            windows[0]["label"] = "Best section"
            windows[0]["summary"] = _native_action_library_en(strongest)["keep"] or "Keep this section as a reference."
        if len(windows) >= 2 and isinstance(windows[1], dict):
            weak_action = _native_action_library_en(weakest)
            windows[1]["label"] = weak_action["focus_label"]
            windows[1]["summary"] = weak_action["focus_summary"]
        if len(windows) >= 3 and isinstance(windows[2], dict):
            transition_action = _native_action_library_en("transition")
            windows[2]["label"] = transition_action["focus_label"]
            windows[2]["summary"] = transition_action["focus_summary"]
        return

    label_map = {
        "Пик сигнала": "Peak",
        "Сильный момент": "Peak",
        "Слабое окно": "Weak window",
        "Слабое место": "Weak window",
        "Самый резкий переход": "Sharpest transition",
        "Резкая смена": "Sharpest transition",
        "Лучший участок": "Best section",
        "Лучший участок": "Best section",
        "Лучший кусок": "Best section",
        "Где чинить первым": "Weak window",
        "Где сменить кадр": "Where to change the shot",
    }
    summary_map = {
        "Peak": "This is where the curve is strongest.",
        "Best section": "This is the section the curve likes most.",
        "Weak window": "This is where the curve drops the most.",
        "Sharpest transition": "This is where the cut changes state most sharply.",
        "Where to change the shot": "This is where an earlier shot change may help.",
    }
    for item in windows:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        item["label"] = label_map.get(label, label)
        item["summary"] = summary_map.get(str(item.get("label") or ""), "Marked section on the curve.")


def _build_seek_targets_en(report: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for item in report.get("focus_windows", []):
        if isinstance(item, dict):
            targets.append(
                {
                    "label": str(item.get("label") or ""),
                    "timestamp": str(item.get("timestamp") or ""),
                    "seconds": item.get("seconds"),
                    "kind": "focus",
                    "summary": str(item.get("summary") or ""),
                }
            )
    for item in report.get("drop_moments", []):
        if isinstance(item, dict):
            targets.append(
                {
                    "label": "Weak spot",
                    "timestamp": str(item.get("timestamp") or ""),
                    "seconds": item.get("seconds"),
                    "kind": "drop",
                    "summary": str(item.get("reason") or ""),
                }
            )
    speech = report.get("speech")
    if isinstance(speech, dict):
        for segment in speech.get("segments", [])[:6]:
            if isinstance(segment, dict):
                targets.append(
                    {
                        "label": "Speech segment",
                        "timestamp": _format_seconds_for_copy(float(segment.get("start") or 0)),
                        "seconds": segment.get("start"),
                        "kind": "speech",
                        "summary": str(segment.get("text") or ""),
                    }
                )
    return targets


def _build_strengths_en(
    report: dict[str, Any],
    metrics: list[dict[str, Any]],
    actions: list[dict[str, str]] | None,
    simplified: bool,
) -> list[str]:
    if simplified:
        keep_item = next((item for item in actions or [] if item.get("title") == "Keep as is"), None)
        strongest = metrics[0]["key"] if metrics else "sustain"
        items: list[str] = []
        if keep_item and keep_item.get("timestamp"):
            items.append(f"{keep_item['timestamp']}: {keep_item['instruction']}")
        if strongest == "early_response":
            items.append("Keep the fast opening. Do not slow it down with extra setup.")
        elif strongest == "transition":
            items.append("Keep the shot rhythm in the strong sections. It already helps the cut move.")
        else:
            items.append("Do not over-fix the strong sections. Use their pace and presentation as the reference.")
        return items[:2]

    speech = report.get("speech") if isinstance(report.get("speech"), dict) else {}
    items = []
    if metrics:
        items.append(f"The strongest area right now is {metrics[0]['label']}: {_metric_summary_en(str(metrics[0]['key']), int(metrics[0]['score']))}")
    if len(metrics) > 1:
        items.append(f"Second strongest is {metrics[1]['label']}: {_metric_summary_en(str(metrics[1]['key']), int(metrics[1]['score']))}")
    if speech.get("available"):
        items.append("The transcript is stable enough to inspect wording, pauses, and timing next to the curve.")
    return items[:3]


def _build_weaknesses_en(
    report: dict[str, Any],
    metrics: list[dict[str, Any]],
    actions: list[dict[str, str]] | None,
    simplified: bool,
) -> list[str]:
    if simplified:
        edit_items = [item for item in actions or [] if item.get("title") != "Keep as is"]
        return [f"{item['timestamp']}: {item['instruction']}" for item in edit_items[:2] if item.get("timestamp")]

    speech = report.get("speech") if isinstance(report.get("speech"), dict) else {}
    items = []
    if metrics:
        weakest = metrics[-1]
        items.append(f"The main gap right now is {weakest['label']}: {_metric_summary_en(str(weakest['key']), int(weakest['score']))}")
    if len(metrics) > 1:
        second = metrics[-2]
        items.append(f"Check {second['label']} next. That is the next clean place to improve the cut.")
    speech_start = speech.get("speech_start_seconds")
    if speech.get("available") and isinstance(speech_start, (int, float)) and float(speech_start) > 2.0:
        items.append("The spoken line enters late, so the opening has to carry the message without verbal support.")
    return items[:3]


def _build_plan_en(source: Any, simplified: bool) -> list[dict[str, str]]:
    if simplified:
        actions = [item for item in source or [] if isinstance(item, dict)]
        keep_item = next((item for item in actions if item.get("title") == "Keep as is"), None)
        edit_items = [item for item in actions if item.get("title") != "Keep as is"]
        plan: list[dict[str, str]] = []
        if keep_item:
            plan.append({"title": "Keep", "detail": f"{keep_item['timestamp']}: {keep_item['instruction']}"})
        if edit_items:
            plan.append({"title": "Do first", "detail": f"{edit_items[0]['timestamp']}: {edit_items[0]['instruction']}"})
        if len(edit_items) > 1:
            plan.append({"title": "Do next", "detail": f"{edit_items[1]['timestamp']}: {edit_items[1]['instruction']}"})
        return plan[:3]

    recommendations = [item for item in source or [] if isinstance(item, str) and item.strip()]
    plan: list[dict[str, str]] = []
    if recommendations:
        plan.append({"title": "Keep", "detail": "Protect the strongest parts of the current cut while you test the weak spots."})
        plan.append({"title": "Test first", "detail": recommendations[0]})
    if len(recommendations) > 1:
        plan.append({"title": "Check next", "detail": recommendations[1]})
    return plan[:3]


def _build_recommendations_en(report: dict[str, Any], metrics: list[dict[str, Any]], simplified: bool) -> list[str]:
    scores = {str(item["key"]): int(item["score"]) for item in metrics}
    drop_moments = [item for item in report.get("drop_moments", []) if isinstance(item, dict)]
    speech = report.get("speech") if isinstance(report.get("speech"), dict) else {}
    duration_seconds = float((report.get("video") or {}).get("duration_seconds") or 0.0)
    cutoff = 60 if simplified else ANALYSIS_MODE_PROFILES.get("deep", ANALYSIS_MODE_PROFILES["simplified"]).recommendation_cutoff

    recs: list[str] = []
    if scores.get("early_response", 0) < cutoff:
        recs.append("Strengthen the hook: show the main thing earlier, cut the long setup, and make the first shot easier to read.")
    if scores.get("sustain", 0) < cutoff:
        recs.append("Find the weak section and cut it, or change the shot, angle, or action earlier.")
    if scores.get("transition", 0) < cutoff:
        recs.append("Change the picture more often: new shot, new angle, new action, or short on-screen text.")
    if scores.get("stability", 0) < cutoff:
        recs.append("Simplify the frame: keep one main subject and remove extra text or clutter.")
    if scores.get("density", 0) < cutoff:
        recs.append("Punch up the visual: bigger subject, cleaner background, more motion, or stronger contrast.")
    if drop_moments:
        timestamps = ", ".join(str(item.get("timestamp") or "") for item in drop_moments[:3] if item.get("timestamp"))
        if timestamps:
            recs.append(f"Start with {timestamps} and check the shot, on-screen text, and pace there.")
    if speech.get("available"):
        speech_start = speech.get("speech_start_seconds")
        if isinstance(speech_start, (int, float)) and float(speech_start) > 2.0:
            recs.append("Bring the main line in earlier if the words carry the key message.")
        pause_ratio = speech.get("pause_ratio")
        if isinstance(pause_ratio, (int, float)) and float(pause_ratio) > 0.28:
            recs.append("Trim the pauses between lines or tighten the delivery.")
    else:
        recs.append("If the spoken line matters, recheck voice level, noise, and clarity.")
    if duration_seconds > 30:
        recs.append("After the main fixes, test a shorter cut too.")
    return recs[:6]


def _build_single_header_en(
    report: dict[str, Any],
    metrics: list[dict[str, Any]],
    actions: list[dict[str, str]] | None,
    simplified: bool,
) -> tuple[str, str, str]:
    score = int(report.get("overall_score") or 0)
    scores = {str(item["key"]): int(item["score"]) for item in metrics}

    if simplified:
        keep_item = next((item for item in actions or [] if item.get("title") == "Keep as is"), None)
        edit_items = [item for item in actions or [] if item.get("title") != "Keep as is"]
        verdict = _overall_status_en(score)
        executive = _simple_overview_text_en(scores, len(edit_items))
        banner = _simple_banner_text_en(scores, keep_item is not None, len(edit_items))
        return verdict, executive, banner

    strongest = metrics[0]["label"] if metrics else "Hook"
    weakest = metrics[-1]["label"] if metrics else "Retention"
    if score >= 75:
        verdict = "The cut is strong on the curve."
    elif score >= 60:
        verdict = "The cut is workable, but uneven."
    else:
        verdict = "The cut is still weak."
    executive = f"The clearest strength right now is {strongest}. The main gap is {weakest}."
    banner = "Use the strongest sections as the reference and fix the weakest area first. The detailed notes below show where the curve holds and where it slips."
    return verdict, executive, banner


def _overall_status_en(score: int) -> str:
    if score >= 75:
        return "The cut is strong."
    if score >= 60:
        return "The cut is okay, but it needs edits."
    return "The cut is weak."


def _simple_overview_text_en(metric_scores: dict[str, int], edit_count: int) -> str:
    early = metric_scores.get("early_response", 0)
    sustain = metric_scores.get("sustain", 0)
    transition = metric_scores.get("transition", 0)
    stability = metric_scores.get("stability", 0)
    density = metric_scores.get("density", 0)

    if early >= 75:
        start_phrase = "The opening is strong"
    elif early >= 60:
        start_phrase = "The opening is okay"
    else:
        start_phrase = "The opening is weak"

    if sustain < 60:
        middle_phrase = "then the pace drops"
    elif transition < 60:
        middle_phrase = "then the shots change too late"
    elif stability < 60:
        middle_phrase = "some frames feel crowded"
    elif density < 60:
        middle_phrase = "some visuals feel weak"
    else:
        middle_phrase = "then the cut holds together"

    tail = " The weak spots are marked below, and the fixes are listed right under them." if edit_count else " The marked sections are listed below."
    return f"{start_phrase}, but {middle_phrase}.{tail}"


def _simple_banner_text_en(metric_scores: dict[str, int], has_keep_item: bool, edit_count: int) -> str:
    parts: list[str] = []
    if has_keep_item:
        parts.append("Keep the strong sections intact")
    if metric_scores.get("transition", 0) < 60:
        parts.append("the weak spots usually improve with earlier shot changes")
    elif metric_scores.get("stability", 0) < 60:
        parts.append("the weak spots usually improve when the frame gets cleaner")
    elif metric_scores.get("density", 0) < 60:
        parts.append("the weak spots usually improve when the visual gets stronger")
    else:
        parts.append("the weak spots are marked below")
    if edit_count:
        parts.append("the concrete fixes are listed below")
    return ". ".join(part[:1].upper() + part[1:] for part in parts) + "."


def _build_phase_notes_en(report: dict[str, Any]) -> list[str]:
    timeline = report.get("timeline")
    points = timeline.get("points") if isinstance(timeline, dict) else None
    if not isinstance(points, list) or not points:
        return []

    scores = [float(point.get("signal_score") or 0.0) for point in points if isinstance(point, dict)]
    if not scores:
        return []

    third = max(1, len(scores) // 3)
    chunks = [scores[:third], scores[third:third * 2], scores[third * 2 :]]
    labels = ["Opening", "Middle", "Finish"]
    baseline = sum(scores) / max(len(scores), 1)
    notes: list[str] = []
    for label, chunk in zip(labels, chunks):
        if not chunk:
            continue
        ratio = (sum(chunk) / len(chunk)) / max(baseline, 1e-6)
        if ratio >= 1.08:
            notes.append(f"{label}: above the cut average. The curve holds well here.")
        elif ratio >= 0.92:
            notes.append(f"{label}: close to the cut average. No strong lift, but no major collapse either.")
        else:
            notes.append(f"{label}: below the cut average. This phase is worth checking for pacing and presentation.")
    return notes


def _build_compare_verdict_en(best: dict[str, Any], runner_up: dict[str, Any], delta: int) -> str:
    best_name = str(best.get("name") or best.get("variant_key") or "This cut")
    runner_name = str(runner_up.get("name") or runner_up.get("variant_key") or "the next cut")
    if delta >= 8:
        return f"{best_name} is the clear winner."
    if delta >= 4:
        return f"{best_name} is ahead of {runner_name}, but the gap is still editable."
    return f"{best_name} is slightly ahead, but the race is tight."


def _build_compare_executive_summary_en(best: dict[str, Any], runner_up: dict[str, Any], delta: int, top_axes: list[str]) -> str:
    best_name = str(best.get("name") or best.get("variant_key") or "The leading cut")
    runner_name = str(runner_up.get("name") or runner_up.get("variant_key") or "the next cut")
    if top_axes:
        axis_text = ", ".join(top_axes[:2])
        return f"{best_name} leads {runner_name} by {delta} points. The clearest separation shows up on {axis_text}."
    return f"{best_name} leads {runner_name} by {delta} points overall."


def _build_common_gaps_en(report: dict[str, Any]) -> list[str]:
    variants = [item for item in report.get("variants", []) if isinstance(item, dict)]
    if not variants:
        return []

    profile_key = str((report.get("analysis_mode") or {}).get("key") or "deep")
    cutoff = ANALYSIS_MODE_PROFILES.get(profile_key, ANALYSIS_MODE_PROFILES["deep"]).recommendation_cutoff
    gaps: list[str] = []
    metric_keys = [metric.get("key") for metric in variants[0].get("metrics", []) if isinstance(metric, dict)]
    for key in metric_keys:
        scores = [int((variant.get("metric_lookup") or {}).get(key, 0)) for variant in variants]
        if not scores:
            continue
        avg_score = sum(scores) / len(scores)
        label = next((metric.get("label") for metric in variants[0].get("metrics", []) if isinstance(metric, dict) and metric.get("key") == key), key)
        if avg_score < cutoff:
            gaps.append(f"Every version is still weak on {label}. Even the best cut does not create much headroom there.")
    return gaps[:3]


def _build_compare_banner_en(best: dict[str, Any], common_gaps: list[str]) -> str:
    strongest = str(best.get("strongest") or "the strongest area")
    if common_gaps:
        return f"Use the winner's {strongest} as the reference. Across the whole set, the shared gaps are listed below."
    return f"Use the winner's {strongest} as the reference and copy its strongest choices into the next edit."


def _build_compare_recommendations_en(best: dict[str, Any], common_gaps: list[str]) -> list[str]:
    best_name = str(best.get("name") or best.get("variant_key") or "the winning cut")
    strongest = str(best.get("strongest") or "its strongest area")
    recs = [f"Use {best_name} as the base cut.", f"Protect its edge on {strongest} while you test the next edit."]
    recs.extend(common_gaps[:2])
    return recs[:4]


def _speech_metric_label_en(metric_key: str, fallback: str) -> str:
    labels = {
        "speech_start": "Voice enters",
        "speech_pace": "Delivery speed",
        "articulation": "Delivery density",
        "pause_ratio": "Pauses",
        "confidence": "Transcript confidence",
    }
    return labels.get(metric_key, fallback)


def _speech_metric_summary_en(metric_key: str, value: Any) -> str:
    try:
        numeric = float(str(value).split()[0])
    except (ValueError, TypeError):
        numeric = None

    if metric_key == "speech_start" and numeric is not None:
        return "The main line enters early enough to support the hook." if numeric <= 2.0 else "The main line enters late, so the opening carries the message without words."
    if metric_key == "speech_pace" and numeric is not None:
        return "Delivery moves fast enough for this kind of cut." if numeric >= 2.2 else "Delivery speed is workable, but it could be tighter." if numeric >= 1.5 else "Delivery feels slow for this kind of cut."
    if metric_key == "articulation" and numeric is not None:
        return "The spoken part is dense enough to keep moving." if numeric >= 2.8 else "The spoken part is okay, but it could be denser." if numeric >= 2.0 else "The spoken part is sparse, so the message may feel stretched."
    if metric_key == "pause_ratio" and numeric is not None:
        return "There are not many long pauses." if numeric <= 0.15 else "There are some pauses, but not too many." if numeric <= 0.28 else "There are too many long pauses between lines."
    if metric_key == "confidence" and numeric is not None:
        return "Transcript confidence is strong." if numeric >= 0.85 else "Transcript confidence is usable, but not perfect." if numeric >= 0.65 else "Transcript confidence is weak, so read the speech layer carefully."
    return ""


def _format_seconds_for_copy(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def _fallback_action_timestamp(report: dict[str, Any]) -> str | None:
    windows = [item for item in report.get("focus_windows", []) if isinstance(item, dict)]
    for item in (windows[1] if len(windows) > 1 else None, windows[2] if len(windows) > 2 else None, windows[0] if windows else None):
        if isinstance(item, dict) and item.get("timestamp"):
            return str(item["timestamp"])
    for moment in report.get("drop_moments", []):
        if isinstance(moment, dict) and moment.get("timestamp"):
            return str(moment["timestamp"])
    return None


# ---------------------------------------------------------------------------
# Source-of-truth copy strings (Follow-up F3)
#
# These constants used to live inside ``tribe_review/_engine.py`` and inside
# ``tribe_review/curve_alignment.py``. Moving them here means localization
# concerns (Russian-default + English-overlay) sit in one module instead of
# being scattered across the engine.
#
# Status of the EN data:
#   * Action-item TITLES on the EN side are already covered by
#     ``LABEL_MAP_EN`` and by the native rewriting in
#     ``_rewrite_english_report``. ``ACTION_VARIANTS_EN`` adds the matching
#     INSTRUCTIONS so a future PR can teach ``_rewrite_action_items_en`` to
#     prefer the curated translation over its current heuristic builder.
#   * Curve-alignment default labels/summaries get used when the editorial
#     layer copies them into ``focus_windows`` / ``drop_moments`` without
#     overriding them; the EN translations are merged into ``LABEL_MAP_EN``
#     below so ``_apply_known_labels`` picks them up automatically.
# ---------------------------------------------------------------------------


ACTION_VARIANTS_ES: dict[str, list[tuple[str, str]]] = {
    "early_response": [
        ("Refuerza el primer frame", "Mete antes de este punto un frame donde se vea de volada el objeto principal, el resultado o el conflicto."),
        ("Empieza con el resultado", "Pon primero el outcome o el efecto más claro; la explicación va después."),
        ("Tumba la entrada larga", "Si antes de este punto hay setup que no agrega significado nuevo, recórtalo hasta la primera acción."),
        ("Sube el objeto principal", "Haz el objeto más grande o más al centro desde el arranque del bache."),
        ("Promete antes", "Si el cut está vendiendo un resultado, muestra el beneficio antes del bache, no después."),
        ("Arranca con acción", "Cambia la entrada tranquila por un frame con movimiento, gesto o cambio claro."),
        ("Mueve un frame fuerte adelante", "Toma el frame fuerte más cercano después del bache y pruébalo más temprano."),
        ("Recorta el arranque vacío", "Tumba los frames donde el espectador todavía no entiende qué está viendo."),
        ("Muestra el contexto desde el inicio", "Mete una pista visual corta para que el mensaje aterrice antes del bache."),
        ("Endurece la entrada", "Apura los primeros segundos: menos pausa, objeto más grande, acción más clara."),
    ],
    "sustain": [
        ("Acorta el tramo arrastrado", "Tumba 1-2 segundos antes de este punto, o brinca más rápido al siguiente beat."),
        ("Mete un giro nuevo", "Inserta un detalle, movimiento o cambio de shot antes de este punto para que el cut no se cuelgue."),
        ("Aprieta el ritmo", "Quítale la pausa y deja solo los frames que mueven la escena hacia adelante."),
        ("Refresca la mitad", "Mete información nueva aquí: una reacción, un detalle, un payoff o un cambio de acción."),
        ("Tumba la repetición", "Si el frame repite un beat que el espectador ya entendió, deja solo la versión más fuerte."),
        ("Cambia el encuadre", "Antes del bache pasa a otra escala: close-up, wide shot o un detalle."),
        ("Suelta un mini-payoff", "Aterriza un mini-resultado rápido antes de que la curva empiece a caer."),
        ("Mueve el beat antes", "Si la acción importante aterriza después, pruébala 1-2 segundos más temprano."),
        ("Tumba el frame neutral", "Un frame sin info nueva se ve mejor como movimiento o reacción."),
        ("Parte el shot largo", "Divide el tramo estático con un cambio de ángulo rápido o un detalle insertado."),
    ],
    "transition": [
        ("Cambia el shot antes", "Cambia el ángulo, encuadre o acción más temprano para que este tramo no arrastre."),
        ("Mete un acento visual", "Antes de este punto mete movimiento, gesto, push-in o cambio de escala."),
        ("Tumba el shot detenido", "Si el frame se queda sin acción nueva, recórtalo hasta el primer movimiento claro."),
        ("Mete un detalle", "Inserta un close-up corto de un detalle para darle al espectador un motivo nuevo de seguir viendo."),
        ("Cambia el ángulo", "Mantén la misma acción pero muéstrala desde otro ángulo antes de que empiece el bache."),
        ("Mete una reacción", "Si hay una persona, animal u objeto en movimiento, inserta una reacción o consecuencia."),
        ("Apura el cut", "Prueba una toma más corta aquí sin cambiar lo que significa la escena."),
        ("Haz visible el cambio", "Usa movimiento o un match-cut para que la transición no se sienta accidental."),
        ("Parte el tramo uniforme", "Adentro de un fragmento largo mete una segunda fase visual: antes-después, ahora-luego."),
        ("Mete un caption como ancla", "Si la imagen se parece a sí misma, mete un caption corto que introduzca un beat nuevo."),
    ],
    "stability": [
        ("Limpia el frame", "Deja un objeto principal y tumba los detalles o textos extra a su alrededor."),
        ("Endurece el foco", "Resalta el objeto principal con tamaño, posición o un fondo más limpio."),
        ("Descongestiona la composición", "Tumba los elementos que compiten para que la mirada no se parta entre detalles."),
        ("Esconde el texto extra", "Si hay muchas palabras cerca del objeto, deja un caption corto o tumba todo."),
        ("Sube el tamaño del objeto", "Sube el objeto importante en escala para que no pelee con el fondo."),
        ("Limpia el fondo", "Prueba el frame sin objetos extra, brillos o detalles detrás de la acción principal."),
        ("Haz visible el movimiento", "Si la acción es chica, muéstrala más grande o repítela desde un ángulo más legible."),
        ("Tumba el segundo foco", "Deja un solo foco principal; oscurece, recorta o mueve el secundario para después."),
        ("Estabiliza el frame", "Si el bache coincide con un shake o un cut duro, prueba un fragmento más tranquilo."),
        ("Separa objeto del fondo", "Sube el contraste con luz, color o un frame para que lo principal sobresalga."),
    ],
    "density": [
        ("Sube el nivel promedio", "Refuerza no solo el pico sino los frames de a diario alrededor de este punto: objeto más grande, fondo más limpio, acción más visible."),
        ("Muestra el producto más grande", "Sube el objeto en escala, mete movimiento o sube el contraste."),
        ("Endurece el visual punch", "Antes de este punto mete un frame más brillante, un close-up o una acción más fuerte."),
        ("Sube el contraste", "Separa el objeto del fondo con luz, color o una composición más limpia."),
        ("Mete movimiento", "Si el frame está estático, prueba movimiento de mano, cámara, objeto o un cambio de posición."),
        ("Muestra el detalle más cerca", "Inserta un close-up del detalle que el espectador debe notar."),
        ("Tumba el frame gris", "Cambia el fragmento neutral por uno con acción o emoción más clara."),
        ("Muestra el beneficio", "Si el producto o resultado es difícil de leer, muestra su efecto dentro del frame."),
        ("Mete contraste visual", "Prueba un objeto brillante en un fondo oscuro, un acento de color o una composición más limpia."),
        ("Aprieta la escena", "Tumba los frames de relleno y deja solo aquellos donde objeto, acción y mensaje aterrizan al mismo tiempo."),
    ],
    "speech_start": [
        ("Di lo principal antes", "Si el mensaje vive en las palabras, suelta la frase clave antes de este punto y recorta la entrada muda."),
        ("Mueve la frase adelante", "Pon la frase clave más cerca del arranque del tramo flojo."),
        ("Abre con una frase corta", "Mete una frase clara antes del bache, sin explicación larga."),
        ("Tumba el opening mudo", "Si los primeros segundos sin palabras no jalan, recórtalos o monta encima la idea clave."),
        ("Sincroniza palabra y frame", "Que la frase importante aterrice cuando el objeto principal ya esté visible."),
    ],
    "pause": [
        ("Tumba la pausa", "Recorta el hueco vacío o mete la frase más apretada para que el tramo no se caiga."),
        ("Aprieta el habla", "Comprime el espacio entre palabras y deja solo la frase que necesitas."),
        ("Aprieta la entrega", "Haz la frase más corta y más cerca de la acción del frame."),
        ("Tapa el aire muerto", "Si no puedes quitar la pausa, tápala con acción, una reacción o un close-up."),
        ("Parte la frase larga", "Divide el habla en pedacitos y pega cada uno con el frame correcto."),
    ],
}


CURVE_FOCUS_WINDOW_LABELS_ES: tuple[str, ...] = (
    "Tramo fuerte",
    "Dónde arreglar primero",
    "Otro bache",
)
CURVE_FOCUS_WINDOW_SUMMARIES_ES: tuple[str, ...] = (
    "Tómalo de referencia para el resto.",
    "Aquí se ve un bache claro en la curva.",
    "Aquí se ve otro bache claro en la curva.",
)
CURVE_DROP_DEFAULT_REASON_ES = "Aquí se ve un bache claro en la curva."
CURVE_PLAN_TITLE_KEEP_ES = "Dejar"
CURVE_PLAN_TITLE_FIRST_ES = "Hacer primero"
CURVE_PLAN_TITLE_NEXT_ES = "Hacer después"


ACTION_VARIANTS_EN: dict[str, list[tuple[str, str]]] = {
    "early_response": [
        ("Strengthen the first frame", "Place a frame here that immediately shows the main subject, the result, or the conflict."),
        ("Open with the result", "Lead with the outcome or the clearest payoff and put the explanation behind it."),
        ("Cut the long intro", "If there is setup before this point that adds no new meaning, trim it down to the first action."),
        ("Lift the main subject", "Make the subject larger or closer to centre right at the start of the weak window."),
        ("Promise earlier", "If the cut is selling a result, show its benefit before the dip, not after."),
        ("Open on action", "Replace the calm opener with a frame that has motion, a gesture, or a clear change."),
        ("Move a strong frame forward", "Take the nearest strong frame after the dip and try it earlier in the cut."),
        ("Trim the empty start", "Drop frames where the viewer does not yet know what they are looking at."),
        ("Show context up front", "Add a short visual cue so the meaning lands before the weak section."),
        ("Sharpen the entry", "Speed up the first seconds: less pause, bigger subject, clearer action."),
    ],
    "sustain": [
        ("Trim the dragged section", "Cut 1-2 seconds before this point, or jump faster to the next beat."),
        ("Add a new turn", "Insert a new detail, motion, or shot change before this point so the cut does not sag."),
        ("Tighten the pacing", "Squeeze the pause and keep only the frames that move the scene forward."),
        ("Refresh the middle", "Add new information here: a reaction, a detail, a payoff, or a change of action."),
        ("Cut the repeat", "If the frame restates a beat the viewer already got, keep only the strongest copy."),
        ("Switch the framing", "Move to a different scale before the dip: close-up, wide shot, or a detail."),
        ("Drop a small payoff", "Land a quick mini-result before the curve starts to fall."),
        ("Move the beat earlier", "If the important action lands later, try it 1-2 seconds sooner."),
        ("Drop the neutral frame", "A frame with no new info plays better as a motion or reaction beat."),
        ("Break up the long take", "Split the static stretch with a fast angle change or an inserted detail."),
    ],
    "transition": [
        ("Change the shot earlier", "Switch the angle, framing, or action sooner so this stretch does not drag."),
        ("Add a visual accent", "Before this point add motion, a gesture, a push-in, or a scale change."),
        ("Cut the held shot", "If the frame sits without new action, trim it to the first clear movement."),
        ("Insert a detail", "Drop in a short close-up of a detail so the viewer gets a new reason to keep watching."),
        ("Switch the angle", "Keep the same action but show it from another angle before the dip starts."),
        ("Add a reaction", "If there is a person, animal, or object in motion, insert a reaction or aftermath."),
        ("Speed up the cut", "Try a shorter take here without changing what the scene means."),
        ("Make the transition obvious", "Use motion or a match-cut so the change does not feel accidental."),
        ("Split the uniform stretch", "Inside a long fragment add a second visual phase: before-after, then-now."),
        ("Add a text anchor", "If the picture looks the same to itself, add a short caption that introduces a new beat."),
    ],
    "stability": [
        ("Clean up the frame", "Keep one main subject and remove the extra detail or text around it."),
        ("Sharpen the focus", "Make the main subject pop with size, position, or a cleaner background."),
        ("Declutter the composition", "Cut the competing elements so the eye does not split between multiple details."),
        ("Hide the extra text", "If there are too many words near the subject, leave one short caption or drop it entirely."),
        ("Make the subject larger", "Push the important subject up in scale so it does not fight the background."),
        ("Clean the background", "Try the frame without stray objects, glare, or detail behind the main action."),
        ("Make the motion obvious", "If the action is small, show it bigger or repeat it from a more readable angle."),
        ("Remove the second focal point", "Keep one main focus; darken, crop, or move the secondary element later."),
        ("Stabilise the frame", "If the dip lines up with shake or a hard cut, try a calmer fragment instead."),
        ("Separate subject from background", "Boost the contrast with light, colour, or a frame so the main thing stands out."),
    ],
    "density": [
        ("Lift the average level", "Strengthen not just the peak but the everyday frames around this point: bigger subject, cleaner background, more visible action."),
        ("Show the product larger", "Push the subject up in scale, add motion, or boost the contrast."),
        ("Sharpen the visual punch", "Before this point add a brighter frame, a close-up, or a louder action."),
        ("Boost the contrast", "Separate the subject from the background with light, colour, or a cleaner composition."),
        ("Add motion", "If the frame is static, try a hand, camera, or subject motion or a change of position."),
        ("Show the detail closer", "Insert a close-up of the detail you want the viewer to notice."),
        ("Cut the grey frame", "Replace the neutral fragment with a frame that has clearer action or emotion."),
        ("Show the benefit", "If the product or result is hard to read, show its effect right inside the frame."),
        ("Add visual contrast", "Try a bright subject on a dark background, a colour accent, or a cleaner composition."),
        ("Tighten the scene", "Drop the weak filler frames and keep only ones where subject, action, and meaning land at once."),
    ],
    "speech_start": [
        ("Say the main point earlier", "If the meaning lives in the words, deliver the key line before this point and trim the silent intro."),
        ("Move the line forward", "Place the key line closer to the start of the weak section."),
        ("Open with a short line", "Add one clear line before the dip, without a long explanation."),
        ("Cut the silent opener", "If the first seconds without words are not working, trim them or lay the key thought on top."),
        ("Sync word and frame", "Let the important line land at the moment the main subject is already visible."),
    ],
    "pause": [
        ("Cut the pause", "Trim the empty gap or deliver the line tighter so the section does not sag."),
        ("Tighten the speech", "Compress the gap between words and keep only the line you need."),
        ("Tighten the delivery", "Make the line shorter and closer to the action in the frame."),
        ("Cover the dead air", "If you cannot remove the pause, cover it with action, a reaction, or a close-up."),
        ("Break the long line", "Split the speech into short pieces and place each next to the right frame."),
    ],
}


# Curve-alignment defaults (used by tribe_review.curve_alignment when the
# editorial layer doesn't override them).
CURVE_FOCUS_WINDOW_LABELS_EN: tuple[str, ...] = (
    "Best section",
    "Weak window",
    "Another drop",
)
CURVE_FOCUS_WINDOW_SUMMARIES_EN: tuple[str, ...] = (
    "Use this section as the anchor.",
    "There is a clear dip here on the curve.",
    "There is another clear dip on the curve here.",
)
CURVE_DROP_DEFAULT_REASON_EN = "There is a clear dip here on the curve."
CURVE_PLAN_TITLE_KEEP_EN = "Keep"
CURVE_PLAN_TITLE_FIRST_EN = "Do first"
CURVE_PLAN_TITLE_NEXT_EN = "Do next"


def get_action_variants(language: str | None = None) -> dict[str, list[tuple[str, str]]]:
    """Return the action-variant catalogue for the given language.

    Defaults to Spanish (Mexican coloquial — the engine's
    source-of-truth language post Stage 3 / S1). Pass ``"en"`` for
    the parallel English catalogue.
    """

    if (language or "").strip().lower() == "en":
        return ACTION_VARIANTS_EN
    return ACTION_VARIANTS_ES


# Make every Spanish action-item title and instruction translatable via
# the existing ``_apply_known_labels`` machinery. Stage 3 / S1 dropped
# the RU tables so this population block is now ES-keyed.
for _es_metric_key, _es_pairs in ACTION_VARIANTS_ES.items():
    _en_pairs = ACTION_VARIANTS_EN.get(_es_metric_key, [])
    for (_es_title, _es_instruction), (_en_title, _en_instruction) in zip(_es_pairs, _en_pairs):
        LABEL_MAP_EN.setdefault(_es_title, _en_title)
        LABEL_MAP_EN.setdefault(_es_instruction, _en_instruction)
del _es_metric_key, _es_pairs, _en_pairs, _es_title, _es_instruction, _en_title, _en_instruction

for _es_label, _en_label in zip(CURVE_FOCUS_WINDOW_LABELS_ES, CURVE_FOCUS_WINDOW_LABELS_EN):
    LABEL_MAP_EN.setdefault(_es_label, _en_label)
for _es_summary, _en_summary in zip(CURVE_FOCUS_WINDOW_SUMMARIES_ES, CURVE_FOCUS_WINDOW_SUMMARIES_EN):
    LABEL_MAP_EN.setdefault(_es_summary, _en_summary)
LABEL_MAP_EN.setdefault(CURVE_DROP_DEFAULT_REASON_ES, CURVE_DROP_DEFAULT_REASON_EN)
LABEL_MAP_EN.setdefault(CURVE_PLAN_TITLE_KEEP_ES, CURVE_PLAN_TITLE_KEEP_EN)
LABEL_MAP_EN.setdefault(CURVE_PLAN_TITLE_FIRST_ES, CURVE_PLAN_TITLE_FIRST_EN)
LABEL_MAP_EN.setdefault(CURVE_PLAN_TITLE_NEXT_ES, CURVE_PLAN_TITLE_NEXT_EN)
del _es_label, _en_label, _es_summary, _en_summary


# ============================================================================
# Conditional-copy banded summaries (Stage-2 / G3)
# ----------------------------------------------------------------------------
# Score-band copy for the five TRIBE metrics and value-band copy for the five
# speech-side metrics. Both used to live as ternary chains / inline dicts in
# ``tribe_review/copy_ru.py``; G3 lifts them here so ``copy_ru`` becomes a
# thin delegator and EN translations live alongside RU.
#
# Bands:
# * Metric-side (early_response / sustain / transition / stability / density):
#   "high" if score >= 75, "mid" if score >= 60, else "low".
# * Speech-side (speech_start / speech_pace / articulation / pause_ratio /
#   confidence): per-metric thresholds, see ``SPEECH_BAND_RULES``. ``"high"``
#   always means the desirable end of the spectrum.
# ============================================================================


METRIC_SUMMARY_LIBRARY_ES: dict[str, dict[str, str]] = {
    "early_response": {
        "high": "Desde el primer shot ya está claro qué ver: el objeto principal o la acción se notan de volada.",
        "mid": "El arranque está bien, pero el objeto principal o la acción se podría mostrar antes y más grande.",
        "low": "Los primeros segundos están flojos: lo principal aparece muy tarde o no se ve claro de entrada.",
    },
    "sustain": {
        "high": "A lo largo del cut hay frames o acciones nuevas, así que el interés no se cae.",
        "mid": "El interés no aguanta parejo: hay tramos donde no pasa nada nuevo por mucho tiempo.",
        "low": "Hay tramos sin acción nueva o sin imagen nueva, así que el cut se quiere saltar.",
    },
    "transition": {
        "high": "Los shots cambian a tiempo: ningún plano se queda más de lo necesario.",
        "mid": "El cambio de shots está, pero a veces un plano se queda un poco más de lo que debería.",
        "low": "Los shots cambian muy tarde: un mismo plano se atora y el cut empieza a arrastrar.",
    },
    "stability": {
        "high": "El frame se lee fácil: un objeto principal o una acción jalan la atención de volada.",
        "mid": "A veces el frame trae demasiado de un jalón: varios objetos, texto chico o un fondo cargado.",
        "low": "Hay demasiado en el frame: fondo, texto y detalles pelean entre ellos y se pierde lo principal.",
    },
    "density": {
        "high": "La imagen está fuerte: el objeto se ve bien, el movimiento se lee, el contraste aguanta.",
        "mid": "La imagen está bien, pero a veces el objeto sale chico, hay poco movimiento o falta contraste.",
        "low": "La imagen está floja: poco tamaño, poco movimiento o poco contraste para jalar el ojo.",
    },
}


METRIC_SUMMARY_LIBRARY_EN: dict[str, dict[str, str]] = {
    "early_response": {
        "high": "The main thing is clear from the first shot.",
        "mid": "The opening is okay, but the main subject could appear earlier and bigger.",
        "low": "The hook is weak. The main thing shows up too late or is not clear enough right away.",
    },
    "sustain": {
        "high": "The cut keeps introducing enough change to hold attention.",
        "mid": "Retention is uneven. Some sections sit too long without anything new.",
        "low": "There are sections with no new action or no new visual, so the cut feels skippable.",
    },
    "transition": {
        "high": "The shots change at the right time.",
        "mid": "The pacing is workable, but some shots hang a little too long.",
        "low": "The shots change too late, so the cut starts to drag.",
    },
    "stability": {
        "high": "The frame is easy to read. One main subject wins the attention quickly.",
        "mid": "Some frames feel crowded with extra objects, small text, or a noisy background.",
        "low": "Too many elements compete inside the frame, so the main point gets lost.",
    },
    "density": {
        "high": "The visual is strong: the subject reads well, motion is visible, and contrast holds.",
        "mid": "The visual is fine, but the subject gets small, motion is limited, or contrast is weak.",
        "low": "The visual feels weak: not enough scale, motion, or contrast to really pull the eye.",
    },
}


# Speech-side band thresholds. ``direction`` controls which side of each
# threshold counts as the "high" (= desirable) band.
SPEECH_BAND_RULES: dict[str, dict[str, Any]] = {
    "speech_start": {"direction": "lower-is-better", "high": 0.8, "mid": 2.0},
    "speech_pace": {"direction": "higher-is-better", "high": 2.8, "mid": 1.4},
    "articulation": {"direction": "higher-is-better", "high": 3.0, "mid": 1.8},
    "pause_ratio": {"direction": "lower-is-better", "high": 0.12, "mid": 0.28},
    "confidence": {"direction": "higher-is-better", "high": 0.75, "mid": 0.55},
}


SPEECH_SUMMARY_LIBRARY_ES: dict[str, dict[str, str]] = {
    "speech_start": {
        "high": "La voz entra casi de volada — la pista de texto llega temprano.",
        "mid": "La voz arranca un beat después, pero todavía en la parte temprana del cut.",
        "low": "La voz entra tarde — antes de eso el cut se aguanta solo en imagen y audio.",
    },
    "speech_pace": {
        "high": "La entrega está densa para lo que dura el cut.",
        "mid": "El ritmo de entrega está moderado, sin saturar el cut con texto.",
        "low": "La capa de voz está dispersa: pocas palabras para lo que dura el cut.",
    },
    "articulation": {
        "high": "Las frases entran apretadas, sin estiramientos largos dentro del habla.",
        "mid": "La densidad de la articulación se ve normal.",
        "low": "El habla se siente estirada o muy dispersa dentro de los tramos hablados.",
    },
    "pause_ratio": {
        "high": "Pocas pausas largas; el flujo de la voz se mantiene apretado.",
        "mid": "Hay pausas, pero todavía no dominan lo que dura el cut.",
        "low": "El porcentaje de pausas largas está alto — entre frases hay mucho aire.",
    },
    "confidence": {
        "high": "El ASR reconoce voz con confianza. La pista de audio se lee limpia.",
        "mid": "La voz se lee en general, pero a veces la calidad del audio limita la confianza.",
        "low": "La confianza está baja: revisa ruido, volumen y dicción.",
    },
}


SPEECH_SUMMARY_LIBRARY_EN: dict[str, dict[str, str]] = {
    "speech_start": {
        "high": "The voice enters almost immediately, so the text cue lands early.",
        "mid": "The voice starts a beat later but still in the early part of the cut.",
        "low": "The voice enters late; before that the cut leans on visual and audio without words.",
    },
    "speech_pace": {
        "high": "Delivery is dense for the length of the cut.",
        "mid": "Delivery pace is moderate, without overloading the cut with text.",
        "low": "The speech layer is sparse: few words for the cut's length.",
    },
    "articulation": {
        "high": "Phrases land tight, without long stretches inside the speech itself.",
        "mid": "Articulation density looks ordinary.",
        "low": "Speech feels stretched or very sparse inside the spoken stretches.",
    },
    "pause_ratio": {
        "high": "Few long pauses; the speech flow stays tight.",
        "mid": "There are pauses, but they don't dominate the cut's length yet.",
        "low": "The share of long pauses is high — there is a lot of empty air between phrases.",
    },
    "confidence": {
        "high": "ASR recognises speech confidently. The audio track reads cleanly.",
        "mid": "Speech reads overall, but in places the audio quality limits recognition confidence.",
        "low": "Confidence is low: check noise, voice loudness, and diction clarity.",
    },
}


def _score_band(score: int) -> str:
    """``"high"`` if score >= 75, ``"mid"`` if score >= 60, else ``"low"``."""
    if score >= 75:
        return "high"
    if score >= 60:
        return "mid"
    return "low"


def _speech_band(metric_key: str, value: float) -> str:
    """Per-metric value banding for the speech-side summaries.

    ``"high"`` always means the desirable end (early speech start / fast pace /
    tight articulation / few pauses / strong confidence). The threshold sense
    flips depending on whether the metric is "higher-is-better" (pace,
    articulation, confidence) or "lower-is-better" (speech_start, pause_ratio).
    """
    rule = SPEECH_BAND_RULES.get(metric_key)
    if rule is None:
        return "low"
    high = float(rule["high"])
    mid = float(rule["mid"])
    if rule["direction"] == "higher-is-better":
        if value >= high:
            return "high"
        if value >= mid:
            return "mid"
        return "low"
    # lower-is-better
    if value <= high:
        return "high"
    if value <= mid:
        return "mid"
    return "low"


def metric_band_summary(metric_key: str, score: int, language: str = "es") -> str:
    """Banded summary for a TRIBE metric. ``language`` is ``"es"`` (default,
    Mexican coloquial) or ``"en"``. Unknown languages fall back to ES.

    Stage 3 / S1 dropped the RU table entirely.
    """
    library = METRIC_SUMMARY_LIBRARY_EN if (language or "").strip().lower() == "en" else METRIC_SUMMARY_LIBRARY_ES
    return library.get(metric_key, {}).get(_score_band(score), "")


def speech_metric_summary(metric_key: str, value: float, language: str = "es") -> str:
    """Banded summary for a speech-side metric (see ``SPEECH_BAND_RULES`` for
    the per-metric thresholds). ``language`` is ``"es"`` (default, Mexican
    coloquial) or ``"en"``. Unknown languages fall back to ES.

    Stage 3 / S1 dropped the RU table entirely.
    """
    library = SPEECH_SUMMARY_LIBRARY_EN if (language or "").strip().lower() == "en" else SPEECH_SUMMARY_LIBRARY_ES
    return library.get(metric_key, {}).get(_speech_band(metric_key, value), "")
