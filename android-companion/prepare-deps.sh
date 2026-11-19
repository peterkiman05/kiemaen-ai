#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/app"
LIBS="$APP/libs"
ASSETS="$APP/src/main/assets"
MODEL_NAME="sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01-mobile"
MODEL_DIR="$ASSETS/$MODEL_NAME"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$LIBS" "$ASSETS"

AAR_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/v2.0.2/sherpa-onnx-2.0.2.aar"
AAR_SHA256="6420cfb86c2ef8462dadd77b2202b7430487bdfb2bc715e9ce2864871209a80e"
MODEL_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/${MODEL_NAME}.tar.bz2"

curl --fail --location --retry 3 --retry-delay 2 "$AAR_URL" --output "$LIBS/sherpa-onnx.aar"
echo "$AAR_SHA256  $LIBS/sherpa-onnx.aar" | sha256sum --check

curl --fail --location --retry 3 --retry-delay 2 "$MODEL_URL" --output "$TMP/model.tar.bz2"
tar -xjf "$TMP/model.tar.bz2" -C "$ASSETS"

test -s "$MODEL_DIR/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
test -s "$MODEL_DIR/decoder-epoch-12-avg-2-chunk-16-left-64.onnx"
test -s "$MODEL_DIR/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
test -s "$MODEL_DIR/tokens.txt"
test -s "$MODEL_DIR/bpe.model"

python3 -m pip install --disable-pip-version-check --no-cache-dir "sentencepiece==0.2.3"
python3 - "$MODEL_DIR" <<'PY'
import pathlib
import sys
import sentencepiece as spm

model_dir = pathlib.Path(sys.argv[1])
processor = spm.SentencePieceProcessor(model_file=str(model_dir / "bpe.model"))
tokens = processor.encode("HEY KIEMAEN", out_type=str)
if not tokens:
    raise SystemExit("SentencePiece returned no tokens for the wake phrase")
(model_dir / "keywords.txt").write_text(" ".join(tokens) + "\n", encoding="utf-8")
print("Encoded Hey Kiemaen wake phrase:", " ".join(tokens))
PY

test -s "$MODEL_DIR/keywords.txt"
echo "Prepared verified Sherpa-ONNX runtime and Hey Kiemaen keyword model."
