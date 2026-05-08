"""Verdict, executive / product summaries, recommendations, and action items.

Owns all the prose-level outputs of a single-variant review: strengths,
weaknesses, the verdict line, the executive + product summaries, the long
recommendation list, the recommendation plan, and the action-item builder.
Pulls labels and copy from :mod:`tribe_review.copy_ru`, score helpers from
:mod:`tribe_review.metrics`, and timeline-shape helpers from
:mod:`tribe_review.timeline`.
"""

from __future__ import annotations

from typing import Any

from analysis_settings import AnalysisModeProfile, get_analysis_mode_profile

from tribe_review.copy_ru import (
    ACTION_VARIANTS,
    _friendly_metric_label,
    _simple_metric_action,
)
from tribe_review.metrics import (
    ReviewMetric,
    _metric_display,
    _metric_scores,
    _pick_template,
)
from tribe_review.timeline import (
    _drop_timestamps,
    _speech_line,
)


def _build_strengths(metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    del profile
    strengths = [
        f"Сильнее всего сейчас «{_metric_display(metrics[0])}»: {metrics[0].summary.lower()}",
        f"Второй рабочий ориентир - «{_metric_display(metrics[1])}»: {metrics[1].summary.lower()}",
    ]
    if speech_layer.get("available"):
        strengths.append("Речь распознана, поэтому сильные места можно сверить с конкретными фразами и подачей.")
    else:
        strengths.append("Без надежной речи сильные места лучше проверять по картинке, темпу и звуку.")
    return strengths


def _build_weaknesses(metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    del profile
    items = [
        f"Главное слабое место - «{_metric_display(metrics[-1])}»: {metrics[-1].summary.lower()}",
        f"Следом проверь «{_metric_display(metrics[-2])}»: там есть следующий понятный запас для правки.",
    ]
    if speech_layer.get("available") and isinstance(speech_layer.get("speech_start_seconds"), float) and speech_layer["speech_start_seconds"] > 2.0:
        items.append("Речь начинается поздно, поэтому первые секунды должны держаться на картинке и действии без словесной опоры.")
    return items


def _build_recommendations(metrics: list[ReviewMetric], drop_moments: list[dict[str, Any]], duration_seconds: float, speech: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    scores = _metric_scores(metrics)
    cutoff = 60 if profile.key == "simplified" else profile.recommendation_cutoff
    drops = _drop_timestamps(drop_moments)
    min_key = min(scores, key=scores.get)
    max_key = max(scores, key=scores.get)
    speech_start = speech.get("speech_start_seconds")
    speech_start_is_late = isinstance(speech_start, (int, float)) and float(speech_start) > 2.0
    speech_start_text = (
        f"Речь начинается около {float(speech_start):.2f} с. Если ключевой смысл в словах, перенеси главную фразу ближе к старту."
        if speech_start_is_late
        else ""
    )
    pause_ratio = speech.get("pause_ratio")
    pause_ratio_is_high = isinstance(pause_ratio, (int, float)) and float(pause_ratio) > 0.28

    candidates = [
        (scores.get("early_response", 0) < cutoff, "Старт набирает уровень поздно. Проверь первый кадр: главное должно появиться раньше, крупнее или с более ясным результатом."),
        (scores.get("sustain", 0) < cutoff, "После сильных мест график быстро падает. Перед просадкой добавь новый поворот, смену крупности или сократи отрезок, который не двигает сцену."),
        (scores.get("transition", 0) < cutoff, "Темп событий слабый: кадр слишком долго остается в одном состоянии. Добавь смену плана, жест, действие или короткий текст раньше."),
        (scores.get("stability", 0) < cutoff, "Есть резкие просадки. Сравни слабые окна с соседними сильными местами и убери лишние детали, которые размывают главный фокус."),
        (scores.get("density", 0) < cutoff, "Средний уровень ниже пиков. Подними базу ролика: крупнее главный объект, чище фон, заметнее движение или сильнее контраст."),
        (bool(drops), f"Сначала открой окна {drops}: там график проседает относительно соседних точек. Проверь, что в эти секунды меняется в кадре, тексте и темпе."),
        (bool(speech.get("available")) and speech_start_is_late, speech_start_text),
        (bool(speech.get("available")) and pause_ratio_is_high, "В речи много пустых промежутков. Подрежь паузы или сделай подачу плотнее, особенно рядом со слабыми окнами графика."),
        (not speech.get("available"), "Если слова важны для смысла, проверь громкость, шум и разборчивость: сейчас текстовый слой не дает надежной опоры для разбора."),
        (duration_seconds > 30, "После основной правки протестируй короткую версию. Так проще понять, выигрывает ли график от сокращения или теряется важный контекст."),
        (scores.get("early_response", 0) >= cutoff and scores.get("sustain", 0) < cutoff, "Начало уже можно оставить как ориентир, а правку начинать с середины: там нужно добавить новый информационный или визуальный повод смотреть дальше."),
        (scores.get("density", 0) >= 75 and scores.get("stability", 0) < cutoff, "Картинка в среднем сильная, но есть резкие провалы. Не усиливай все подряд - точечно сглади слабые окна, чтобы не потерять сильные кадры."),
        (scores.get("transition", 0) >= 75 and scores.get("sustain", 0) < cutoff, "Событий хватает, но линия все равно падает. Значит, проблема не только в частоте смен, а в том, насколько новые кадры дают понятный смысл."),
        (scores.get("early_response", 0) < cutoff and scores.get("density", 0) >= 70, "Визуал достаточно сильный, но старт не успевает его раскрыть. Перенеси самый понятный крупный кадр ближе к первым секундам."),
        (scores[min_key] < 45 and scores[max_key] >= 70, f"Разрыв между сильной и слабой стороной большой. Не перепридумывай весь ролик: сохрани «{_friendly_metric_label(max_key).lower()}» и отдельно чини «{_friendly_metric_label(min_key).lower()}»."),
    ]

    recs: list[str] = []
    for condition, text in candidates:
        if condition and text not in recs:
            recs.append(text)
        if len(recs) >= 6:
            break
    if not recs:
        recs.append("Явной крупной поломки по графику нет. Следующий тест лучше строить как A/B: меняй один элемент за раз и сравнивай старт, средний уровень и просадки.")
    return recs[:6]


def _build_simple_recommendations(metrics: list[ReviewMetric], drop_moments: list[dict[str, Any]], duration_seconds: float, speech: dict[str, Any]) -> list[str]:
    profile = get_analysis_mode_profile("simplified")
    return _build_recommendations(metrics, drop_moments, duration_seconds, speech, profile)


def _build_recommendation_plan(recommendations: list[str], top_metric: ReviewMetric, weak_metric: ReviewMetric, profile: AnalysisModeProfile) -> list[dict[str, str]]:
    del profile
    return [
        {"title": "Что оставить", "detail": f"Не ломай сильную часть «{_metric_display(top_metric)}»: она уже дает ролику рабочую опору."},
        {"title": "Что проверить первым", "detail": recommendations[0] if recommendations else _simple_metric_action(weak_metric)},
        {"title": "Как перепроверить", "detail": "После правки сравни старую и новую версии по графику: старт, средний уровень и резкие просадки должны стать лучше."},
    ]


def _build_verdict(overall_score: int, metrics: list[ReviewMetric], profile: AnalysisModeProfile) -> str:
    del profile
    scores = _metric_scores(metrics)
    strongest = _metric_display(metrics[0])
    weakest = _metric_display(metrics[-1])
    early = scores.get("early_response", 0)
    sustain = scores.get("sustain", 0)
    transition = scores.get("transition", 0)
    stability = scores.get("stability", 0)
    density = scores.get("density", 0)
    candidates = [
        (overall_score >= 78 and scores.get(metrics[-1].key, 0) >= 65, f"Ролик выглядит сильным и достаточно ровным. Главная опора - «{strongest}», а улучшать лучше точечно через «{weakest}»."),
        (overall_score >= 75 and scores.get(metrics[-1].key, 0) < 60, f"У ролика есть сильная основа, но она держится не везде. Оставь «{strongest}» и первым делом проверь «{weakest}»."),
        (early < 60 and density >= 65, "Главная проблема не в картинке, а в том, как быстро ролик раскрывает ее на старте. Сильный визуал стоит подать раньше."),
        (early < 60, f"Ролик слишком медленно набирает уровень. Первый приоритет - старт, затем уже правка «{weakest}»."),
        (sustain < 60 and early >= 65, "Начало работает лучше середины. Не ломай старт, а добавь новый поворот перед первым заметным провалом графика."),
        (transition < 60, "График проседает из-за нехватки новых событий. Участки без смены плана или действия нужно сжимать раньше."),
        (stability < 60, "Главный риск - резкие просадки. Ролик может иметь хорошие кадры, но слабые окна между ними тянут итог вниз."),
        (density < 60 and overall_score < 55, "Пока ролик держится на отдельных моментах. Нужно поднимать средний уровень, а не только искать один яркий пик."),
        (overall_score >= 60, f"Версия рабочая, но неровная. Сильнее всего выглядит «{strongest}», главный запас - «{weakest}»."),
        (overall_score < 60, f"Это скорее черновик для доработки. Сначала усили «{weakest}», потом перепроверь весь ролик сравнительным тестом."),
    ]
    return _pick_template(candidates, f"Главный ориентир - «{strongest}». Основная правка сейчас в зоне «{weakest}».")


def _build_executive_summary(overall_score: int, top_metric: ReviewMetric, weak_metric: ReviewMetric, runner_metric: ReviewMetric, speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> str:
    del profile
    scores = {top_metric.key: top_metric.score, weak_metric.key: weak_metric.score, runner_metric.key: runner_metric.score}
    top = _metric_display(top_metric)
    runner = _metric_display(runner_metric)
    weak = _metric_display(weak_metric)
    speech = _speech_line(speech_layer)
    candidates = [
        (overall_score >= 80, f"Это сильная версия: график держится высоко, а «{top}» дает основную опору. Улучшения стоит делать точечно через «{weak}». {speech}"),
        (overall_score >= 72 and weak_metric.score < 60, f"Общий уровень хороший, но итог ограничивает «{weak}». Сначала проверь слабые окна, не меняя то, что уже работает в «{top}». {speech}"),
        (weak_metric.key == "early_response", f"Главный вопрос - старт: ролик поздно набирает уровень. Сохрани «{top}», но перенеси более понятный кадр или смысл ближе к первым секундам. {speech}"),
        (weak_metric.key == "sustain", f"Старт и отдельные кадры работают лучше, чем продолжение. Нужно понять, где график начинает падать, и дать там новый поворот. {speech}"),
        (weak_metric.key == "transition", f"Ролику не хватает новых событий в нужный момент. «{top}» можно сохранить, а монтаж проверить на слишком длинные планы. {speech}"),
        (weak_metric.key == "stability", f"Главная проблема - резкие просадки между сильными местами. Проверь слабые окна на лишние детали, паузы или потерю фокуса. {speech}"),
        (weak_metric.key == "density", f"Лучшие места заметно сильнее среднего уровня. Нужно не добавлять еще один пик, а поднять базовую силу большинства кадров. {speech}"),
        (scores.get(top_metric.key, 0) - scores.get(weak_metric.key, 0) >= 25, f"Разрыв между сильной и слабой частью большой: «{top}» трогать опасно, а «{weak}» дает самый понятный запас роста. {speech}"),
        (overall_score >= 60, f"Версия уже рабочая, но требует аккуратной правки. Ориентир - «{top}», второй сильный признак - «{runner}», главный ремонт - «{weak}». {speech}"),
        (overall_score < 60, f"Пока это внутренний вариант для доработки. Начни не с полной переработки, а с одного слабого признака: «{weak}». {speech}"),
    ]
    return _pick_template(candidates, f"Сильная сторона - «{top}», слабая - «{weak}». Следующий шаг: одна правка и повторное сравнение графика.")


def _build_product_summary(overall_score: int, ordered_metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> str:
    del profile
    scores = _metric_scores(ordered_metrics)
    strongest = _metric_display(ordered_metrics[0])
    weakest = _metric_display(ordered_metrics[-1])
    speech = _speech_line(speech_layer)
    candidates = [
        (overall_score >= 80, f"Можно брать эту версию как базу для следующего теста. Она уже держит график достаточно высоко; правки лучше ограничить зоной «{weakest}». {speech}"),
        (overall_score >= 70 and scores.get("early_response", 0) >= 70, f"Старт можно сохранять как рабочий. Следующий тест лучше строить вокруг того, как ролик держится после первых секунд. {speech}"),
        (scores.get("early_response", 0) < 60, f"Для продукта сейчас важнее всего быстрее объяснить ценность. Перенеси результат, товар или конфликт ближе к началу. {speech}"),
        (scores.get("sustain", 0) < 60, f"Версия теряет темп после удачных моментов. Добавь в середину новый смысловой шаг: действие, реакцию, деталь или payoff. {speech}"),
        (scores.get("transition", 0) < 60, f"Монтаж выглядит затянутым. Следующий вариант должен чаще менять состояние кадра, но без хаотичной нарезки. {speech}"),
        (scores.get("stability", 0) < 60, f"Слабые места похожи на потерю фокуса. Для следующей версии сделай главный объект и действие проще для чтения. {speech}"),
        (scores.get("density", 0) < 60, f"Ролику не хватает среднего уровня: отдельные хорошие места есть, но базовая картинка должна стать сильнее. {speech}"),
        (overall_score >= 60, f"Основа рабочая. Не перепридумывай весь ролик: сохрани «{strongest}» и проверь одну правку в зоне «{weakest}». {speech}"),
        (overall_score < 50, f"Сейчас лучше делать не мелкий полишинг, а новую итерацию вокруг слабого признака «{weakest}». {speech}"),
        (True, f"Для следующего прогона меняй один элемент за раз и смотри, что происходит со стартом, средним уровнем и просадками. {speech}"),
    ]
    return _pick_template(candidates, f"Сильнее всего выглядит «{strongest}», слабее всего - «{weakest}».")


def _action_copy_for_metric(metric_key: str, variant_index: int) -> tuple[str, str]:
    variants = ACTION_VARIANTS.get(metric_key) or ACTION_VARIANTS["sustain"]
    return variants[variant_index % len(variants)]


def _action_metric_candidates(metrics: list[Any], speech_layer: dict[str, Any]) -> list[str]:
    keys = [str(item.key) for item in sorted(metrics, key=lambda metric: metric.score) if getattr(item, "key", "")]
    if speech_layer.get("available") and isinstance(speech_layer.get("speech_start_seconds"), float) and speech_layer["speech_start_seconds"] > 2.0:
        keys.append("speech_start")
    if speech_layer.get("available") and isinstance(speech_layer.get("pause_ratio"), float) and speech_layer["pause_ratio"] > 0.28:
        keys.append("pause")

    seen: set[str] = set()
    ordered: list[str] = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered or ["sustain"]


def _build_action_items(
    recommendations: list[str],
    focus_windows: list[Any],
    drop_moments: list[dict[str, Any]],
    speech_layer: dict[str, Any],
    metrics: list[Any],
    profile: Any,
) -> list[dict[str, str]]:
    del recommendations

    targets: list[dict[str, str]] = []
    for item in drop_moments:
        timestamp = str(item.get("timestamp") or "").strip()
        if not timestamp:
            continue
        targets.append(
            {
                "timestamp": timestamp,
                "why": str(item.get("reason") or "").strip(),
            }
        )

    if not targets and focus_windows:
        weak_window = focus_windows[1] if getattr(profile, "key", "") == "simplified" and len(focus_windows) > 1 else focus_windows[0]
        if getattr(profile, "key", "") != "simplified":
            weak_window = next(
                (
                    item
                    for item in focus_windows
                    if "лаб" in str(getattr(item, "label", "")).lower()
                ),
                focus_windows[0],
            )
        targets.append(
            {
                "timestamp": str(getattr(weak_window, "timestamp", "")).strip(),
                "why": str(getattr(weak_window, "summary", "")).strip(),
            }
        )

    metric_keys = _action_metric_candidates(metrics, speech_layer)
    actions: list[dict[str, str]] = []
    used_titles: set[str] = set()
    metric_use_count: dict[str, int] = {}
    for index, target in enumerate(targets[: getattr(profile, "max_action_items", 4)]):
        metric_key = metric_keys[min(index, len(metric_keys) - 1)]
        variant_index = metric_use_count.get(metric_key, 0)
        title, instruction = _action_copy_for_metric(metric_key, variant_index)
        metric_use_count[metric_key] = variant_index + 1
        if title in used_titles:
            for offset in range(1, 5):
                title, instruction = _action_copy_for_metric(metric_key, variant_index + offset)
                if title not in used_titles:
                    break
        used_titles.add(title)
        actions.append(
            {
                "timestamp": target["timestamp"],
                "title": title,
                "instruction": instruction,
                "why": target["why"],
            }
        )

    seen_timestamps: set[str] = set()
    deduped: list[dict[str, str]] = []
    for action in actions:
        timestamp = action["timestamp"]
        if not timestamp or timestamp in seen_timestamps:
            continue
        seen_timestamps.add(timestamp)
        deduped.append(action)
    return deduped[: getattr(profile, "max_action_items", 4)]
