#!/usr/bin/env bash
# Shared runtime environment for ProofAlign VLA / LIBERO runs.
#
# Source this file before loading OpenVLA/OpenVLA-OFT or running online LIBERO:
#   source scripts/env_vla.sh

export HF_HOME="${HF_HOME:-/data0/ldx/huggingface}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-${HF_HOME}/hub}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-${HF_HOME}/transformers}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/data0/ldx/uv-cache}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/data0/ldx/pip-cache}"

export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/proofalign-mpl}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/proofalign-cache}"

export PROOFALIGN_UV="${PROOFALIGN_UV:-/home/ldx/.conda/envs/proofalign-libero/bin/uv}"
