#!/bin/bash
# ダブルクリックで GUI を起動します。
cd "$(dirname "$0")" || exit 1
exec python3 ./prp_path_fixer.py "$@"
