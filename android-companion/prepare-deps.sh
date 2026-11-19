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

python3 -m pip install --disable-pip-version-check --no-cache-dir "sherpa-onnx==2.0.2" click
printf 'HEY KIEMAEN\n' > "$TMP/keywords_raw.txt"
sherpa-onnx-cli text2token \
  --tokens "$MODEL_DIR/tokens.txt" \
  --tokens-type bpe \
  --bpe-model "$MODEL_DIR/bpe.model" \
  "$TMP/keywords_raw.txt" \
  "$MODEL_DIR/keywords.txt"

test -s "$MODEL_DIR/keywords.txt"
echo "Prepared verified Sherpa-ONNX runtime and Hey Kiemaen keyword model."
