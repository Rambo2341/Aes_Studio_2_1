#!/usr/bin/env bash
# Train Aes 3.x on a rented Linux GPU (RunPod / Vast.ai / Lambda ...) and produce a GGUF for your PC.
#
# Usage (on the GPU server, inside this project folder):
#   bash trainer/cloud_train.sh <dataset.jsonl> [base_model] [name]
# Example:
#   bash trainer/cloud_train.sh aes_training_123.jsonl Qwen/Qwen2.5-Coder-7B-Instruct aes-3.0
#
# Output: out/<name>-Q4_K_M.gguf  -> download it, then in Aes: Models -> runtime llama_cpp -> Browse .gguf
set -euo pipefail
DATA="${1:?dataset.jsonl required}"
BASE="${2:-Qwen/Qwen2.5-Coder-7B-Instruct}"
NAME="${3:-aes-3.0}"
EXTRA="${AES_TRAIN_ARGS:-}"   # e.g. "--qlora" on 16-24 GB cards; leave empty on 40-80 GB cards

python -m pip install -q -r trainer/requirements-training.txt
mkdir -p out
python trainer/train_lora.py --base "$BASE" --dataset "$DATA" --output "out/$NAME-lora" --epochs 2 $EXTRA
python trainer/merge_lora.py --base "$BASE" --adapter "out/$NAME-lora" --output "out/$NAME-merged"

if [ ! -d llama.cpp ]; then git clone --depth 1 https://github.com/ggml-org/llama.cpp; fi
python -m pip install -q -r llama.cpp/requirements.txt
python llama.cpp/convert_hf_to_gguf.py "out/$NAME-merged" --outfile "out/$NAME-f16.gguf" --outtype f16
cmake -S llama.cpp -B llama.cpp/build -DGGML_CUDA=ON >/dev/null && cmake --build llama.cpp/build --target llama-quantize -j >/dev/null
llama.cpp/build/bin/llama-quantize "out/$NAME-f16.gguf" "out/$NAME-Q4_K_M.gguf" Q4_K_M
echo "Done: out/$NAME-Q4_K_M.gguf  (download it to your PC; ~4.7 GB for a 7B model, fits an RTX 3070)"
