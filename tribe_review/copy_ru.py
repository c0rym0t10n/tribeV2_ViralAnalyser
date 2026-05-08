"""Russian copy strings and copy-related helpers.

Owns the per-metric labels, score-band summaries, speech-side summaries, and
the small ``_simple_metric_action`` mapping. Pure data + small string helpers
— no numpy, no engine state. Importable on its own.

The ``ACTION_VARIANTS`` constant is sourced from :mod:`report_localization`
(the F3 follow-up consolidated all action-variant copy there). This module
re-exports it under the historical name so engine code keeps the existing
import path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from analysis_settings import AnalysisModeProfile

# Re-export ACTION_VARIANTS from report_localization (the F3 follow-up moved
# the table there). ``noqa: F401`` because the alias name differs from the
# imported symbol — ruff doesn't auto-classify that as a re-export.
from report_localization import ACTION_VARIANTS_RU as ACTION_VARIANTS  # noqa: F401

if TYPE_CHECKING:
    # ``_simple_metric_action`` only reads ``metric.key``; we don't need the
    # ``ReviewMetric`` class at runtime, but keeping the type hint explicit
    # helps editors / mypy.
    from tribe_review.metrics import ReviewMetric  # noqa: F401


def _early_response_summary(score: int) -> str:
    return "Средняя активация в первой части ролика выше, чем в остальной. Для TRIBE это означает сильный ранний отклик." if score >= 75 else "Ранний отклик есть, но он не сильно превосходит остальную часть ролика." if score >= 60 else "Первая часть ролика даёт сравнительно слабый отклик относительно последующих сегментов."


def _sustain_summary(score: int) -> str:
    return "Уровень активации к концу ролика остаётся близким к началу. Сигнал не схлопывается." if score >= 75 else "Поздние сегменты ещё держат отклик, но уже слабее начальных." if score >= 60 else "Во второй половине средний отклик заметно ниже, чем в начале."


def _transition_summary(score: int) -> str:
    return "Сигнал часто меняется между соседними сегментами. Переходы плотные." if score >= 75 else "Переходы присутствуют, но их плотность умеренная." if score >= 60 else "Сигнал меняется редко или слишком неравномерно. Плотность переходов низкая."


def _stability_summary(score: int) -> str:
    return "Изменение сигнала выглядит относительно ровным, без сильной скачкообразности." if score >= 75 else "Сигнал в целом читается, но внутри есть заметная турбулентность." if score >= 60 else "Сигнал заметно шумный: соседние сегменты меняются слишком рвано."


def _density_summary(score: int) -> str:
    return "Средняя абсолютная активация высокая относительно собственных пиков ролика." if score >= 75 else "Плотность активации нормальная, но без выраженного запаса." if score >= 60 else "Средняя активация низкая относительно собственных пиков ролика."


def _speech_start_summary(start_seconds: float) -> str:
    return "Речь включается почти сразу. Текстовая опора приходит рано." if start_seconds <= 0.8 else "Речь стартует не мгновенно, но ещё в ранней фазе ролика." if start_seconds <= 2.0 else "Речь приходит поздно. До этого ролик держится в основном на визуале и звуке без слов."


def _speech_pace_summary(words_per_second: float) -> str:
    return "Речь подаётся плотно относительно длины ролика." if words_per_second >= 2.8 else "Темп речи умеренный, без сильной перегрузки текстом." if words_per_second >= 1.4 else "Речевой слой редкий: слов мало относительно общей длины ролика."


def _articulation_summary(words_per_second_active: float) -> str:
    return "Фразы произносятся плотно, без длинных растяжек внутри самой речи." if words_per_second_active >= 3.0 else "Артикуляция выглядит обычной по плотности." if words_per_second_active >= 1.8 else "Речь звучит растянуто или очень разреженно внутри речевых отрезков."


def _pause_summary(pause_ratio: float) -> str:
    return "Длинных пауз мало. Речевой поток собранный." if pause_ratio <= 0.12 else "Паузы есть, но они пока не доминируют в длительности ролика." if pause_ratio <= 0.28 else "Доля длинных пауз высокая. Между фразами много пустого воздуха."


def _confidence_summary(confidence: float) -> str:
    return "ASR уверенно распознаёт речь. Аудиодорожка читается чисто." if confidence >= 0.75 else "Речь в целом читается, но местами качество дорожки ограничивает уверенность распознавания." if confidence >= 0.55 else "Уверенность низкая: стоит проверить шум, громкость голоса и разборчивость дикции."


USER_METRIC_LABELS: dict[str, str] = {
    "early_response": "Старт графика",
    "sustain": "Как держится график",
    "transition": "Темп событий",
    "stability": "Резкие просадки",
    "density": "Средний уровень",
}


def _friendly_metric_label(key: str, fallback: str | None = None) -> str:
    return USER_METRIC_LABELS.get(str(key), fallback or str(key))


def _metric_label(key: str, profile: AnalysisModeProfile) -> str:
    del profile
    return _friendly_metric_label(key)


def _score_bucket(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 60:
        return "mid"
    return "low"


def _metric_summary(key: str, score: int, profile: AnalysisModeProfile) -> str:
    del profile
    library = {
        "early_response": {
            "high": "Ролик быстро набирает высокий уровень: главное видно рано и без долгого захода.",
            "mid": "Старт рабочий, но главное можно показать раньше или крупнее.",
            "low": "Начало набирает уровень поздно: зритель не сразу понимает, за что держаться.",
        },
        "sustain": {
            "high": "После старта линия держится ровно: в ролике регулярно появляется новый повод смотреть дальше.",
            "mid": "Линия держится не везде: часть отрезков можно сжать или оживить.",
            "low": "После сильных мест график быстро проседает: ролику не хватает новых событий по ходу просмотра.",
        },
        "transition": {
            "high": "Новые события появляются вовремя: кадр не застывает надолго.",
            "mid": "Темп в целом рабочий, но отдельные планы можно менять раньше.",
            "low": "Новых событий мало или они поздно появляются, поэтому некоторые участки начинают тянуться.",
        },
        "stability": {
            "high": "Резких провалов немного: зрителю легче непрерывно следить за главным.",
            "mid": "Есть заметные перепады: часть кадров слабее соседних и требует проверки.",
            "low": "Просадки резкие: рядом с сильными моментами есть участки, которые быстро теряют уровень.",
        },
        "density": {
            "high": "Средний уровень высокий: не только отдельные пики, но и большая часть ролика выглядит сильной.",
            "mid": "Средний уровень нормальный, но лучшие места заметно сильнее остальных.",
            "low": "Средний уровень низкий: ролик держится на отдельных удачных моментах, а не на всей конструкции.",
        },
    }
    return library.get(key, {}).get(_score_bucket(score), "")


def _signal_note(profile: AnalysisModeProfile) -> str:
    del profile
    return "Ниже показан расчетный график ролика: где уровень выше, где есть просадки и какие места стоит проверить в монтаже. Это подсказка для сравнительных тестов, а не обещание результата."


def _simple_metric_action(metric: ReviewMetric) -> str:
    actions = {
        "early_response": "Усиль старт: покажи главное раньше, убери длинный подвод и сделай первый кадр понятнее.",
        "sustain": "Подрежь участок перед просадкой или добавь там новый поворот, чтобы линия не падала после сильного момента.",
        "transition": "Добавь новое событие раньше: другой план, ракурс, действие, жест или короткую текстовую опору.",
        "stability": "Сглади резкую просадку: оставь один главный объект и убери детали, которые спорят за внимание.",
        "density": "Подними средний уровень: крупнее главный объект, чище фон, заметнее действие или сильнее контраст.",
    }
    return actions.get(metric.key, "Упрости этот участок и сделай главный объект заметнее.")
