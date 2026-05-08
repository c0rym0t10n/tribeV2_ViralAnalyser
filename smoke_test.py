from __future__ import annotations

import argparse
from pathlib import Path

from review_engine import generate_review
from speech_runtime import SpeechTranscriber
from tribe_runtime import TribeVideoBackend


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one local TRIBE review smoke test.")
    parser.add_argument("video", type=Path, help="Path to a local test video file.")
    args = parser.parse_args()

    if not args.video.exists():
        raise FileNotFoundError(args.video)

    backend = TribeVideoBackend()
    transcriber = SpeechTranscriber()

    run = backend.predict_video(args.video)
    speech = transcriber.transcribe(args.video)
    review = generate_review(args.video, run, speech=speech)

    print("device:", review["device"])
    print("modalities:", "+".join(review["modalities"]))
    print("overall_score:", review["overall_score"])
    print("verdict:", review["verdict"])
    print("speech_available:", review["speech"]["available"])
    print("speech_language:", review["speech"]["language"])
    print("speech_words:", review["speech"]["word_count"])
    for metric in review["metrics"]:
        print(metric["label"], metric["score"], metric["raw_value"])


if __name__ == "__main__":
    main()
