"""Multi-variant comparison logic and the comparison entrypoint.

Owns ``generate_comparison_report`` plus all the helpers that aggregate
per-variant numbers into a ranking, axis-winners list, common-gaps list,
comparison rows, and prose summaries. Reads from :mod:`tribe_review.copy_ru`
for friendly metric labels and from :mod:`tribe_review.metrics` for the
templated-prose helper.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

import numpy as np

from analysis_settings import AnalysisModeProfile, get_analysis_mode_profile

from tribe_review.copy_ru import _friendly_metric_label
from tribe_review.metrics import _pick_template


def generate_comparison_report(reviews: list[dict[str, Any]], analysis_mode: str | None = None) -> dict[str, Any]:
    if len(reviews) < 2:
        raise ValueError("Need at least two reviews to compare.")
    profile = get_analysis_mode_profile(analysis_mode)

    variants = []
    for index, review in enumerate(reviews, start=1):
        variant = dict(review)
        variant["variant_key"] = variant.get("variant_key") or f"v{index}"
        variants.append(variant)
    variants = _prepare_comparison_variants(variants)

    ranked = sorted(
        variants,
        key=lambda item: (
            item.get("comparison_score", item["overall_score"]),
            item.get("comparison_early_avg", 0),
            item.get("comparison_signal_avg", 0),
            item["metric_lookup"].get("sustain", 0),
        ),
        reverse=True,
    )
    best = ranked[0]
    runner_up = ranked[1]
    comparison_rows = _build_comparison_rows(ranked)
    axis_winners = _build_axis_winners(comparison_rows)
    common_gaps = _build_common_gaps(ranked, profile)

    return {
        "mode": "compare",
        "title": f"Сравнение {len(ranked)} версий",
        "variant_count": len(ranked),
        "best_variant_key": best["variant_key"],
        "best_variant_name": best["title"],
        "overall_score": best.get("comparison_score", best["overall_score"]),
        "verdict": _build_compare_verdict(best, runner_up, len(ranked)),
        "executive_summary": _build_compare_executive_summary(best, runner_up, axis_winners, profile),
        "product_summary": _build_compare_product_summary(best, runner_up, common_gaps, profile),
        "recommendations": _build_comparison_recommendations(best, runner_up, common_gaps),
        "analysis_mode": {
            "key": profile.key,
            "label": profile.label,
            "short_label": profile.short_label,
            "description": profile.description,
            "note": profile.ui_note,
            "comparison_note": profile.comparison_spread_note,
        },
        "ranking": _build_ranking(ranked, best),
        "axis_winners": axis_winners,
        "common_gaps": common_gaps,
        "comparison_rows": comparison_rows,
        "variants": ranked,
        "signal_note": "Сравнение строится по одному расчетному графику для всех версий. Выигрывает не разовый пик, а версия с более сильным стартом, более высоким средним уровнем и меньшим числом резких просадок.",
    }


def _prepare_comparison_variants(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable_ends = [_comparison_usable_end(variant) for variant in variants]
    positive_ends = [end for end in usable_ends if end > 0]
    common_end = min(positive_ends) if positive_ends else 0.0
    common_end = max(common_end, 1.0)

    prepared: list[dict[str, Any]] = []
    for variant, usable_end in zip(variants, usable_ends):
        item = dict(variant)
        original_score = int(round(float(item.get("overall_score") or 0)))
        item["analysis_score"] = original_score
        comparison = _comparison_signal_score(item, common_end, usable_end)
        item.update(comparison)
        item["overall_score"] = comparison["comparison_score"]
        prepared.append(item)
    return prepared


def _comparison_usable_end(variant: dict[str, Any]) -> float:
    timeline_points = ((variant.get("timeline") or {}).get("points") or [])
    timeline_end = max((float(point.get("seconds") or 0.0) for point in timeline_points if isinstance(point, dict)), default=0.0)
    video = variant.get("video") if isinstance(variant.get("video"), dict) else {}
    duration = float(video.get("duration_seconds") or timeline_end or 0.0)
    end = max(timeline_end, duration)
    if end > 7.0:
        return max(1.0, end - 5.0)
    return max(1.0, end)


def _comparison_signal_score(variant: dict[str, Any], common_end: float, usable_end: float) -> dict[str, Any]:
    points = [point for point in ((variant.get("timeline") or {}).get("points") or []) if isinstance(point, dict)]
    usable_points = [
        (float(point.get("seconds") or 0.0), max(0.0, min(100.0, float(point.get("signal_score") or 0.0))))
        for point in points
        if float(point.get("seconds") or 0.0) <= max(usable_end, 1.0)
    ]
    common_points = [(seconds, score) for seconds, score in usable_points if seconds <= common_end]
    if not common_points:
        common_points = usable_points
    if not common_points:
        fallback = int(round(float(variant.get("analysis_score") or variant.get("overall_score") or 0)))
        return {
            "comparison_score": fallback,
            "comparison_signal_avg": fallback,
            "comparison_early_avg": fallback,
            "comparison_floor": fallback,
            "comparison_window_seconds": round(common_end, 2),
        }

    scores = [score for _, score in common_points]
    early_limit = min(common_end, max(3.0, common_end * 0.45))
    early_scores = [score for seconds, score in common_points if seconds <= early_limit] or scores
    sorted_scores = sorted(scores)
    floor_count = max(1, int(round(len(sorted_scores) * 0.35)))
    floor_score = float(np.mean(sorted_scores[:floor_count]))
    signal_avg = float(np.mean(scores))
    early_avg = float(np.mean(early_scores))
    comparison_score = int(round(0.48 * early_avg + 0.34 * signal_avg + 0.18 * floor_score))
    return {
        "comparison_score": max(0, min(100, comparison_score)),
        "comparison_signal_avg": round(signal_avg, 1),
        "comparison_early_avg": round(early_avg, 1),
        "comparison_floor": round(floor_score, 1),
        "comparison_window_seconds": round(common_end, 2),
    }


def _comparison_value(variant: dict[str, Any], key: str, fallback: float = 0.0) -> float:
    value = variant.get(key)
    if value is None:
        value = variant.get("overall_score", fallback)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _comparison_score_value(variant: dict[str, Any]) -> int:
    return int(round(_comparison_value(variant, "comparison_score", _comparison_value(variant, "overall_score", 0.0))))


def _variant_metric(variant: dict[str, Any], mode: str) -> dict[str, Any]:
    metrics = [metric for metric in variant.get("metrics", []) if isinstance(metric, dict)]
    if not metrics:
        return {"key": "sustain", "label": _friendly_metric_label("sustain"), "score": 0}
    fn = max if mode == "max" else min
    metric = fn(metrics, key=lambda item: int(item.get("score") or 0))
    return {
        "key": str(metric.get("key") or ""),
        "label": _friendly_metric_label(str(metric.get("key") or ""), str(metric.get("label") or "")),
        "score": int(metric.get("score") or 0),
    }


def _build_comparison_rows(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_keys = [str(metric.get("key") or "") for metric in variants[0].get("metrics", []) if isinstance(metric, dict)]
    rows = []
    for key in metric_keys:
        scores = [{"variant_key": variant["variant_key"], "name": variant["title"], "score": int(variant["metric_lookup"].get(key, 0))} for variant in variants]
        ordered = sorted(scores, key=lambda item: item["score"], reverse=True)
        rows.append({
            "key": key,
            "label": _friendly_metric_label(key),
            "winner_name": ordered[0]["name"],
            "winner_score": ordered[0]["score"],
            "spread": ordered[0]["score"] - ordered[-1]["score"],
            "scores": scores,
        })
    rows.sort(key=lambda item: item["spread"], reverse=True)
    return rows


def _build_axis_winners(comparison_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": row["label"],
            "winner_name": row["winner_name"],
            "winner_score": row["winner_score"],
            "summary": f"По показателю «{row['label'].lower()}» у этой версии самый заметный отрыв от остальных.",
        }
        for row in comparison_rows[:4]
    ]


def _build_common_gaps(variants: list[dict[str, Any]], profile: AnalysisModeProfile) -> list[str]:
    gaps = []
    metric_keys = [str(metric.get("key") or "") for metric in variants[0].get("metrics", []) if isinstance(metric, dict)]
    for key in metric_keys:
        scores = [int(variant["metric_lookup"].get(key, 0)) for variant in variants]
        if scores and mean(scores) < profile.recommendation_cutoff:
            gaps.append(f"Во всех версиях слабее выглядит «{_friendly_metric_label(key).lower()}». Даже лидер не дает там уверенного запаса, поэтому это хороший кандидат для отдельного теста.")
    return gaps[:3]


def _build_ranking(variants: list[dict[str, Any]], best: dict[str, Any]) -> list[dict[str, Any]]:
    ranking = []
    best_score = _comparison_score_value(best)
    for index, variant in enumerate(variants, start=1):
        strongest = _variant_metric(variant, "max")
        weakest = _variant_metric(variant, "min")
        score = _comparison_score_value(variant)
        delta = best_score - score
        ranking.append({
            "rank": index,
            "variant_key": variant["variant_key"],
            "name": variant["title"],
            "overall_score": score,
            "analysis_score": variant.get("analysis_score"),
            "comparison_signal_avg": variant.get("comparison_signal_avg"),
            "comparison_early_avg": variant.get("comparison_early_avg"),
            "comparison_window_seconds": variant.get("comparison_window_seconds"),
            "delta_vs_best": delta,
            "strongest": strongest["label"],
            "weakest": weakest["label"],
            "summary": _variant_compare_summary(variant, delta),
        })
    return ranking


def _variant_compare_summary(variant: dict[str, Any], delta: int) -> str:
    strongest = _variant_metric(variant, "max")
    weakest = _variant_metric(variant, "min")
    avg = _comparison_value(variant, "comparison_signal_avg", _comparison_value(variant, "overall_score", 0.0))
    early = _comparison_value(variant, "comparison_early_avg", avg)
    floor = _comparison_value(variant, "comparison_floor", avg)
    score = _comparison_score_value(variant)
    candidates = [
        (delta == 0 and early >= 65 and avg >= 60, f"Лидер сравнения: быстро набирает уровень и держит хороший средний график. Главная опора - «{strongest['label'].lower()}»."),
        (delta == 0 and floor < 35, f"Лидер по итоговому score, но не без риска: есть глубокие просадки. Следующая правка - «{weakest['label'].lower()}»."),
        (delta == 0, f"Лидер сравнения. Версия выигрывает не одним всплеском, а суммой показателей; сильнее всего выглядит «{strongest['label'].lower()}»."),
        (delta <= 3 and early >= avg + 8, f"Почти лидер за счет сильного старта, но дальше средний уровень не добирает. Проверь «{weakest['label'].lower()}»."),
        (delta <= 3, f"Почти рядом с лидером: разница небольшая. В следующем тесте сравни именно старт и середину, а не отдельные пики."),
        (delta <= 7 and avg >= 55, f"Версия конкурентная по среднему уровню, но уступает лидеру в деталях. Главный резерв - «{weakest['label'].lower()}»."),
        (early < 45, "Версия проигрывает старт: график поздно набирает уровень, поэтому даже сильные моменты дальше не спасают итог полностью."),
        (floor < 30, f"Основная проблема - глубокие провалы. Сильная сторона «{strongest['label'].lower()}» есть, но «{weakest['label'].lower()}» тянет результат вниз."),
        (score >= 55, f"У версии есть рабочая база, но лидер выглядит ровнее. Сохрани «{strongest['label'].lower()}» и отдельно проверь «{weakest['label'].lower()}»."),
        (True, f"Версия заметно уступает лидеру. Лучшее в ней - «{strongest['label'].lower()}», но общий график пока слишком неровный."),
    ]
    return _pick_template(candidates, "")


def _build_compare_verdict(best: dict[str, Any], runner_up: dict[str, Any], variant_count: int) -> str:
    delta = _comparison_score_value(best) - _comparison_score_value(runner_up)
    best_avg = _comparison_value(best, "comparison_signal_avg", _comparison_score_value(best))
    best_early = _comparison_value(best, "comparison_early_avg", best_avg)
    runner_avg = _comparison_value(runner_up, "comparison_signal_avg", _comparison_score_value(runner_up))
    window = best.get("comparison_window_seconds")
    window_line = f" Сравнение идет по общему окну примерно до {window} с; последние 5 секунд не участвуют." if window else ""
    candidates = [
        (delta >= 12 and best_early >= 65, f"Из {variant_count} версий явнее всего лидирует «{best['title']}»: она быстро набирает график и сохраняет отрыв по среднему уровню.{window_line}"),
        (delta >= 12, f"«{best['title']}» сейчас заметно впереди по общему score сравнения. Главная причина - более высокий средний уровень, а не один случайный пик.{window_line}"),
        (delta >= 7 and runner_avg >= best_avg - 5, f"«{best['title']}» лидирует, но «{runner_up['title']}» остается близким контролем. Разницу лучше перепроверить новым A/B, особенно в начале и середине.{window_line}"),
        (delta >= 7, f"«{best['title']}» выглядит первым кандидатом для следующего теста: у нее сильнее рабочая часть графика и меньше цена слабых окон.{window_line}"),
        (delta <= 3 and best_early < runner_avg, f"Лидерство «{best['title']}» минимальное. Это не окончательный победитель, а версия, которую стоит проверить против «{runner_up['title']}» еще раз.{window_line}"),
        (delta <= 3, f"Разрыв между «{best['title']}» и «{runner_up['title']}» небольшой. Решение лучше принимать после следующего сравнительного прогона с одной точечной правкой.{window_line}"),
        (best_early >= 70 and best_avg < 55, f"«{best['title']}» выигрывает за счет сильного старта, но средний уровень пока не дает большого запаса. Нужна проверка середины ролика.{window_line}"),
        (best_avg >= 65, f"«{best['title']}» лидирует за счет более высокого среднего уровня графика. Это надежнее, чем победа за счет одного позднего всплеска.{window_line}"),
        (best_avg < 50, f"Даже лидер «{best['title']}» пока не выглядит уверенным. Сравнение показывает лучший из текущих вариантов, но не финальную версию.{window_line}"),
        (True, f"Сейчас первым стоит брать «{best['title']}», а «{runner_up['title']}» оставить ближайшим контролем для следующего A/B.{window_line}"),
    ]
    return _pick_template(candidates, "")


def _build_compare_executive_summary(best: dict[str, Any], runner_up: dict[str, Any], axis_winners: list[dict[str, Any]], profile: AnalysisModeProfile) -> str:
    del profile
    best_score = _comparison_score_value(best)
    runner_score = _comparison_score_value(runner_up)
    delta = best_score - runner_score
    best_avg = round(_comparison_value(best, "comparison_signal_avg", best_score), 1)
    best_early = round(_comparison_value(best, "comparison_early_avg", best_score), 1)
    runner_avg = round(_comparison_value(runner_up, "comparison_signal_avg", runner_score), 1)
    top_axis = str(axis_winners[0]["label"]).lower() if axis_winners else _variant_metric(best, "max")["label"].lower()
    candidates = [
        (delta >= 12 and best_early >= 65, f"Лучший кандидат - «{best['title']}»: старт {best_early}, средний уровень {best_avg}. Отрыв от «{runner_up['title']}» - {delta} пунктов, поэтому ее логично брать базой."),
        (delta >= 12, f"«{best['title']}» впереди на {delta} пунктов. Важнее всего не пик, а средний уровень {best_avg} против {runner_avg} у ближайшей версии."),
        (delta <= 3, f"«{best['title']}» пока впереди всего на {delta} пункта. Это близкая гонка: «{runner_up['title']}» стоит оставить в контроле и сравнить еще раз после точечной правки."),
        (best_early < 50, f"Лидер выбран по сумме графика, но старт у него не идеален: {best_early}. Следующий тест должен усилить первые секунды, а не только середину."),
        (best_avg < 50, f"Даже лучшая версия пока не дает высокого среднего уровня. «{best['title']}» выигрывает текущий набор, но весь пакет нуждается в усилении."),
        (top_axis == "старт графика", f"Разница лучше всего видна в старте: «{best['title']}» быстрее набирает график и за счет этого обходит «{runner_up['title']}»."),
        (top_axis == "средний уровень", f"Ключевой плюс лидера - средний уровень. «{best['title']}» выглядит полезнее как база, потому что держится не только на отдельных всплесках."),
        (top_axis == "резкие просадки", f"Лидер выигрывает тем, что меньше проваливается между сильными местами. Для следующей версии важно сохранить эту ровность."),
        (top_axis == "темп событий", f"Главное отличие лидера - темп событий. Он чаще дает зрителю новый повод смотреть дальше."),
        (True, f"«{best['title']}» сейчас первый кандидат, «{runner_up['title']}» - контроль. Сравнивайте старт, средний уровень и просадки, а не только самый высокий пик."),
    ]
    return _pick_template(candidates, "")


def _build_compare_product_summary(best: dict[str, Any], runner_up: dict[str, Any], common_gaps: list[str], profile: AnalysisModeProfile) -> str:
    del profile
    delta = _comparison_score_value(best) - _comparison_score_value(runner_up)
    best_avg = _comparison_value(best, "comparison_signal_avg", _comparison_score_value(best))
    best_floor = _comparison_value(best, "comparison_floor", best_avg)
    weakest = _variant_metric(best, "min")["label"].lower()
    gap_line = common_gaps[0] if common_gaps else ""
    candidates = [
        (delta >= 10 and best_floor >= 45, f"Для следующего теста бери «{best['title']}» как основную версию: она выигрывает не только пиком, но и более устойчивым графиком без глубоких провалов."),
        (delta >= 10, f"«{best['title']}» лучше текущего набора, но слабые окна все еще есть. Перед масштабированием отдельно проверь «{weakest}»."),
        (delta <= 3, f"Не называй победителя финальным. «{best['title']}» и «{runner_up['title']}» близко, поэтому следующий тест должен менять один конкретный элемент."),
        (best_avg < 50, f"Даже лидер пока слабоват по среднему уровню. Нужно не выбирать победителя, а поднять базовую силу всех версий."),
        (bool(gap_line), f"Первой базой бери «{best['title']}», но общий риск одинаков для всех: {gap_line}"),
        (_variant_metric(runner_up, "max")["key"] == _variant_metric(best, "min")["key"], f"У «{runner_up['title']}» есть полезная подсказка по слабому месту лидера. Сравни, как она решает «{weakest}», и перенеси прием в «{best['title']}»."),
        (_comparison_value(best, "comparison_early_avg", 0) < 55, f"Лидерство есть, но старт можно усилить. Следующая итерация «{best['title']}» должна быстрее показывать главный объект или результат."),
        (_comparison_value(best, "comparison_floor", 0) < 35, f"Главная задача - убрать глубокие провалы у лидера. Не добавляй новые эффекты, пока слабые окна не станут понятнее."),
        (delta >= 5, f"«{best['title']}» можно нести первой, а «{runner_up['title']}» оставить контрольной версией для проверки следующей правки."),
        (True, f"Следующий шаг - A/B между «{best['title']}» и «{runner_up['title']}». Смотрите, какая версия лучше держит старт, середину и слабые окна."),
    ]
    return _pick_template(candidates, "")


def _build_comparison_recommendations(best: dict[str, Any], runner_up: dict[str, Any], common_gaps: list[str]) -> list[str]:
    delta = _comparison_score_value(best) - _comparison_score_value(runner_up)
    best_avg = _comparison_value(best, "comparison_signal_avg", _comparison_score_value(best))
    best_early = _comparison_value(best, "comparison_early_avg", best_avg)
    best_floor = _comparison_value(best, "comparison_floor", best_avg)
    runner_avg = _comparison_value(runner_up, "comparison_signal_avg", _comparison_score_value(runner_up))
    weakest = _variant_metric(best, "min")["label"].lower()
    strongest = _variant_metric(best, "max")["label"].lower()
    candidates = [
        (True, f"В следующий тест неси «{best['title']}» как базу: сейчас у нее лучший score по общему окну сравнения."),
        (delta <= 3, f"Отрыв маленький. Не делай вывод по одному прогону: сравни «{best['title']}» и «{runner_up['title']}» еще раз после одной точечной правки."),
        (delta >= 8, f"Сохрани у лидера «{strongest}» без лишних изменений. Это главный прием, который сейчас дает отрыв."),
        (best_early < 55, "У лидера есть запас в первых секундах. Попробуй раньше показать главный объект, результат или конфликт."),
        (best_avg < 55, "Средний уровень у лидера недостаточно высокий. Нужна правка не одного пика, а нескольких обычных кадров между сильными моментами."),
        (best_floor < 35, f"У лидера есть глубокие просадки. Начни с «{weakest}» и сравни слабые окна с соседними сильными местами."),
        (runner_avg >= best_avg - 5, f"«{runner_up['title']}» оставь ближайшим контролем: по среднему уровню она близко и может подсказать, что именно переносить в лидера."),
        (bool(common_gaps), common_gaps[0] if common_gaps else ""),
        (_comparison_value(runner_up, "comparison_early_avg", 0) > best_early + 5, f"У «{runner_up['title']}» старт лучше, чем у лидера. Проверь, можно ли перенести ее первый кадр или заход в «{best['title']}»."),
        (True, "Последние 5 секунд не используй как главный аргумент. Смотри старт, середину и провалы в общем окне сравнения."),
    ]
    recs: list[str] = []
    for condition, text in candidates:
        if condition and text and text not in recs:
            recs.append(text)
        if len(recs) >= 4:
            break
    return recs[:4]
