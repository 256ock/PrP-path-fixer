#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PrP Path Fixer
==============

Premiere Pro のプロジェクトファイル (.prproj) を Mac ⇔ Windows 間で受け渡したときに、
素材パスに含まれる濁点・半濁点 (が, ぱ, ヴ ...) のせいでリンクが切れる問題を修復する。

原因:
  macOS はファイル名を NFD (「か」+「゛」の分解形) で扱うことが多く、
  Windows は NFC (「が」の合成形) で扱う。見た目は同じでもバイト列が違うため、
  prproj に記録されたパスと実ファイル名が一致せず「メディアオフライン」になる。

対処:
  prproj (gzip 圧縮された XML) を展開し、パスを表す要素の文字列だけを
  移行先 OS に合わせた正規化形式 (Windows = NFC / Mac = NFD) に変換して保存し直す。

使い方:
  python3 prp_path_fixer.py                      # GUI を起動
  python3 prp_path_fixer.py --to win a.prproj    # Mac で作った prproj を Windows 用に
  python3 prp_path_fixer.py --to mac a.prproj    # Windows で作った prproj を Mac 用に
  python3 prp_path_fixer.py --to win フォルダ     # フォルダ内の .prproj をまとめて変換

標準ライブラリのみで動作 (Python 3.8+)。
"""

from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

__version__ = "1.0.0"

TARGET_FORMS = {"win": "NFC", "mac": "NFD"}

# macOS (HFS+) の NFD は Unicode 標準の NFD と少し違い、以下の範囲は分解しない。
# 特に CJK 互換漢字 (例: U+FA11 﨑) は NFC/NFD どちらでも別の漢字に置き換わってしまい
# 元に戻せないため、どちらの方向でも変換対象から除外する。
_EXCLUDED_RANGES = (
    (0x2000, 0x2FFF),
    (0xF900, 0xFAFF),
    (0x2F800, 0x2FAFF),
)


def _is_excluded(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EXCLUDED_RANGES)


def normalize_text(text: str, form: str) -> str:
    """text を form (NFC/NFD) に正規化する。ただし除外範囲の文字はそのまま残す。"""
    if unicodedata.is_normalized(form, text):
        return text
    out: List[str] = []
    buf: List[str] = []
    for ch in text:
        if _is_excluded(ch):
            if buf:
                out.append(unicodedata.normalize(form, "".join(buf)))
                buf = []
            out.append(ch)
        else:
            buf.append(ch)
    if buf:
        out.append(unicodedata.normalize(form, "".join(buf)))
    return "".join(out)


# パスを保持する XML 要素 (ActualMediaFilePath, FilePath, RelativePath,
# ConformedAudioPath, PeakFilePath, ProxyPath ... など) を名前で拾う。
_PATH_ELEMENT_RE = re.compile(
    r"<(?P<tag>[A-Za-z_][\w.\-]*(?:Path|FileName)[\w.\-]*)(?P<attrs>(?:\s[^>]*)?)>"
    r"(?P<text>[^<]*)"
    r"</(?P=tag)>"
)


@dataclass
class FixResult:
    changed: List[Tuple[str, str]] = field(default_factory=list)  # (before, after)

    @property
    def count(self) -> int:
        return len(self.changed)


def fix_xml_text(xml: str, form: str, all_text: bool = False) -> Tuple[str, FixResult]:
    """XML 文字列中のパスを正規化する。all_text=True ならドキュメント全体を対象にする。"""
    result = FixResult()

    if all_text:
        for m in _PATH_ELEMENT_RE.finditer(xml):
            before = m.group("text")
            after = normalize_text(before, form)
            if before != after:
                result.changed.append((before, after))
        return normalize_text(xml, form), result

    def repl(m: "re.Match[str]") -> str:
        before = m.group("text")
        after = normalize_text(before, form)
        if before == after:
            return m.group(0)
        result.changed.append((before, after))
        return "<{0}{1}>{2}</{0}>".format(m.group("tag"), m.group("attrs"), after)

    return _PATH_ELEMENT_RE.sub(repl, xml), result


def read_prproj(path: Path) -> Tuple[str, bool]:
    """prproj を読み込み (XML 文字列, gzip 圧縮されていたか) を返す。"""
    raw = path.read_bytes()
    compressed = raw[:2] == b"\x1f\x8b"
    if compressed:
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="surrogateescape"), compressed


def write_prproj(path: Path, xml: str, compressed: bool) -> None:
    data = xml.encode("utf-8", errors="surrogateescape")
    if compressed:
        data = gzip.compress(data)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def default_output_path(src: Path, target: str) -> Path:
    return src.with_name("{}_{}{}".format(src.stem, target, src.suffix))


def fix_file(
    src: Path,
    target: str,
    out: Optional[Path] = None,
    inplace: bool = False,
    all_text: bool = False,
    dry_run: bool = False,
) -> Tuple[Optional[Path], FixResult]:
    """1 ファイルを変換する。書き出し先 (変更がなければ None) と結果を返す。"""
    form = TARGET_FORMS[target]
    xml, compressed = read_prproj(src)
    if "<PremiereData" not in xml:
        raise ValueError("Premiere Pro のプロジェクトファイルではないようです: {}".format(src))

    new_xml, result = fix_xml_text(xml, form, all_text=all_text)
    if new_xml == xml or dry_run:
        return None, result

    if inplace:
        backup = src.with_name(src.name + ".bak")
        shutil.copy2(src, backup)
        dest = src
    else:
        dest = out or default_output_path(src, target)
    write_prproj(dest, new_xml, compressed)
    return dest, result


def iter_prproj(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_dir():
            for f in sorted(p.rglob("*.prproj")):
                # Auto-Save フォルダや自分が出力したファイルは対象外
                if "Auto-Save" in f.parts or f.stem.endswith(("_win", "_mac")):
                    continue
                yield f
        else:
            yield p


def detect_target() -> Optional[str]:
    """実行中の OS から変換先を推定する。"""
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return None


def _log_result(src: Path, dest: Optional[Path], result: FixResult, verbose: bool, log) -> None:
    if result.count == 0:
        log("✔ {}: 修正が必要なパスはありませんでした".format(src.name))
        return
    if dest is None:
        log("… {}: {} 件のパスを修正できます (dry-run)".format(src.name, result.count))
    else:
        log("✔ {}: {} 件のパスを修正 → {}".format(src.name, result.count, dest))
    if verbose:
        seen = set()
        for before, _after in result.changed:
            if before not in seen:
                seen.add(before)
                log("    " + before)


def process(
    paths: Iterable[Path],
    target: str,
    out: Optional[Path] = None,
    inplace: bool = False,
    all_text: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    log=print,
) -> int:
    """複数ファイルを処理する。失敗件数を返す。"""
    errors = 0
    files = list(iter_prproj(paths))
    if not files:
        log("対象の .prproj ファイルが見つかりませんでした")
        return 1
    if out is not None and len(files) > 1:
        log("-o は 1 ファイルのときだけ指定できます")
        return 1
    for src in files:
        try:
            dest, result = fix_file(src, target, out, inplace, all_text, dry_run)
            _log_result(src, dest, result, verbose, log)
        except Exception as e:  # noqa: BLE001 - ユーザー向けにまとめて表示する
            errors += 1
            log("✘ {}: {}".format(src.name, e))
    return errors


# --------------------------------------------------------------------------- GUI


def run_gui(initial: Optional[List[Path]] = None) -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext
    except ImportError:
        print("tkinter が使えないため GUI を起動できません。コマンドラインで実行してください。")
        print("例: python3 prp_path_fixer.py --to win project.prproj")
        return 1

    root = tk.Tk()
    root.title("PrP Path Fixer - 濁点・半濁点パス修復")
    root.geometry("640x460")

    files: List[Path] = []
    target = tk.StringVar(value=detect_target() or "win")
    inplace = tk.BooleanVar(value=False)
    all_text = tk.BooleanVar(value=False)

    frm = tk.Frame(root, padx=12, pady=12)
    frm.pack(fill="both", expand=True)

    tk.Label(frm, text="1. 修復する .prproj を選択", font=("", 12, "bold")).pack(anchor="w")
    row = tk.Frame(frm)
    row.pack(fill="x", pady=(4, 10))
    file_label = tk.Label(row, text="(未選択)", anchor="w")
    file_label.pack(side="left", fill="x", expand=True)

    def set_files(paths: Iterable[str]) -> None:
        files[:] = [Path(p) for p in paths]
        names = ", ".join(p.name for p in files)
        file_label.config(text=names if len(names) < 80 else "{} ファイル".format(len(files)))

    def choose() -> None:
        selected = filedialog.askopenfilenames(
            title="prproj を選択", filetypes=[("Premiere Pro Project", "*.prproj"), ("All", "*")]
        )
        if selected:
            set_files(selected)

    tk.Button(row, text="ファイルを選択…", command=choose).pack(side="right")

    tk.Label(frm, text="2. このプロジェクトを開く OS", font=("", 12, "bold")).pack(anchor="w")
    tk.Radiobutton(frm, text="Windows で開く (Mac から受け取った)  → NFC", variable=target, value="win").pack(anchor="w")
    tk.Radiobutton(frm, text="Mac で開く (Windows から受け取った)  → NFD", variable=target, value="mac").pack(anchor="w")

    opt = tk.Frame(frm)
    opt.pack(fill="x", pady=(8, 8))
    tk.Checkbutton(opt, text="元ファイルを上書き (.bak を作成)", variable=inplace).pack(anchor="w")
    tk.Checkbutton(opt, text="パス以外 (クリップ名など) も変換する", variable=all_text).pack(anchor="w")

    log_box = scrolledtext.ScrolledText(frm, height=10)
    log_box.pack(fill="both", expand=True, pady=(4, 8))

    def log(msg: str) -> None:
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        root.update_idletasks()

    def run() -> None:
        if not files:
            messagebox.showwarning("PrP Path Fixer", "先に .prproj を選択してください")
            return
        errors = process(files, target.get(), inplace=inplace.get(), all_text=all_text.get(),
                         verbose=True, log=log)
        log("完了" if errors == 0 else "完了 (エラー {} 件)".format(errors))

    tk.Button(frm, text="3. 修復する", command=run, height=2).pack(fill="x")

    if initial:
        set_files(str(p) for p in initial)
    # Mac アプリ版: Dock / Finder でアプリアイコンにドロップされたファイルを受け取る
    root.createcommand("::tk::mac::OpenDocument", lambda *paths: set_files(paths))

    root.mainloop()
    return 0


# --------------------------------------------------------------------------- CLI


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if getattr(sys, "frozen", False):
        # アプリ版 (PyInstaller): アイコンにドロップされたファイルを読み込んだ状態で GUI を開く
        return run_gui([Path(a) for a in argv if not a.startswith("-psn")])
    if not argv:
        return run_gui()

    parser = argparse.ArgumentParser(
        prog="prp_path_fixer",
        description="Premiere Pro の prproj 内の素材パスを Mac(NFD) ⇔ Windows(NFC) 間で変換し、"
        "濁点・半濁点を含むパスのリンク切れを修復します。",
    )
    parser.add_argument("paths", nargs="+", type=Path, help=".prproj ファイル、またはそれを含むフォルダ")
    parser.add_argument(
        "--to",
        choices=["win", "mac", "auto"],
        default="auto",
        help="プロジェクトを開く OS。win=NFC, mac=NFD, auto=実行中の OS に合わせる (既定)",
    )
    parser.add_argument("-o", "--output", type=Path, help="出力先ファイル (1 ファイルのときのみ)")
    parser.add_argument("-i", "--inplace", action="store_true", help="元ファイルを上書き (.bak を作成)")
    parser.add_argument("--all", action="store_true", help="パス以外 (クリップ名など) も含め全体を変換")
    parser.add_argument("-n", "--dry-run", action="store_true", help="書き込まずに修正件数だけ表示")
    parser.add_argument("-v", "--verbose", action="store_true", help="修正したパスを一覧表示")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    target = args.to
    if target == "auto":
        target = detect_target()
        if target is None:
            parser.error("OS を判定できません。--to win または --to mac を指定してください")

    errors = process(args.paths, target, args.output, args.inplace, args.all, args.dry_run, args.verbose)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
