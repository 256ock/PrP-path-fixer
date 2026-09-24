# PrP Path Fixer

Premiere Pro のプロジェクトファイル（`.prproj`）を Mac ⇔ Windows 間で受け渡したときに、
素材パスに **濁点・半濁点（が・ぱ・ヴ など）** が含まれていると「メディアオフライン」になり
リンクできない問題を修復するツールです。

## なぜ起きるのか

「ガ」という文字には、Unicode 上で 2 通りの表し方があります。

| 形式 | 中身 | 主に使う OS |
|------|------|-------------|
| NFC（合成形） | `ガ` (U+30AC) の 1 文字 | Windows |
| NFD（分解形） | `カ` (U+30AB) ＋ `゛` (U+3099) の 2 文字 | macOS |

見た目は同じでもデータとしては別物なので、Mac で作ったプロジェクトに記録された
NFD のパスを、Windows 上の NFC のファイル名と照合できず、リンクが切れます（逆方向も同様）。

このツールは prproj（gzip 圧縮された XML）を展開し、**パスを表す要素だけ**を
移行先 OS の形式に変換して保存し直します。

## アプリ版（Python 不要）

### ブラウザ版 — いちばん手軽

[`app/PrP-Path-Fixer.html`](app/PrP-Path-Fixer.html) をダウンロードして、ダブルクリックでブラウザで開くだけです（Chrome / Edge / Safari / Firefox の最新版）。

1. 「このプロジェクトを開く OS」を選ぶ（開いているパソコンの OS が初期値）
2. `.prproj` をドラッグ＆ドロップ（複数可）
3. 修復済みの `元の名前_win.prproj` / `元の名前_mac.prproj` が自動でダウンロードされます

ファイルはブラウザ内だけで処理され、インターネットには送信されません（オフラインでも動作します）。

### Mac アプリ / Windows アプリ

GitHub の **Actions → Build apps** の実行結果（Artifacts）、または **Releases** から入手できます。

- **Mac** (`PrP-Path-Fixer-mac.zip`): 解凍して `PrP Path Fixer.app` を起動。
  `.prproj` をアプリのアイコンにドロップしても開けます。
  署名していないアプリのため、初回は **右クリック →「開く」** で起動してください
  （macOS 15 以降は「システム設定 → プライバシーとセキュリティ」で「このまま開く」）。
  Apple シリコン (M1 以降) 用です。Intel Mac ではブラウザ版を使ってください。
- **Windows** (`PrP-Path-Fixer-windows.zip`): 解凍して `PrP-Path-Fixer.exe` を起動。
  `.prproj` を exe にドロップしても開けます。
  SmartScreen の警告が出たら「詳細情報 →実行」を押してください。

`v1.0.0` のようなタグを push すると、両方のアプリが Releases に自動で添付されます。

## Python スクリプト版

### 必要なもの

- Python 3.8 以上（標準ライブラリのみ使用、追加インストール不要）
  - Windows: <https://www.python.org/downloads/> からインストール（「Add python.exe to PATH」にチェック）
  - Mac: `python3` が入っていなければ python.org 版をインストール（GUI に必要な Tk が同梱されています）

### 使い方

#### GUI

- **Mac**: `PrP-Path-Fixer-Mac.command` をダブルクリック
  （初回は右クリック →「開く」。実行権限がない場合は `chmod +x PrP-Path-Fixer-Mac.command`）
- **Windows**: `PrP-Path-Fixer-Windows.bat` をダブルクリック

1. 「ファイルを選択…」で `.prproj` を選ぶ（複数可）
2. 「このプロジェクトを開く OS」を選ぶ（実行中の OS が初期値）
3. 「修復する」

`元のファイル名_win.prproj` / `元のファイル名_mac.prproj` が同じフォルダに作られます。
元ファイルは変更しません。

#### Windows でドラッグ＆ドロップ

Mac から受け取った `.prproj`（またはそれが入ったフォルダ）を
`PrP-Path-Fixer-Windows.bat` にドロップすると、そのまま Windows 用に変換されます。

#### コマンドライン

```sh
# Mac で作ったプロジェクトを Windows で開けるようにする
python3 prp_path_fixer.py --to win project.prproj

# Windows で作ったプロジェクトを Mac で開けるようにする
python3 prp_path_fixer.py --to mac project.prproj

# フォルダ内の .prproj をまとめて変換（Auto-Save フォルダは除外）
python3 prp_path_fixer.py --to win ./projects

# 何件直るか確認だけ（書き込みしない）、修正したパスを表示
python3 prp_path_fixer.py --to win -n -v project.prproj
```

| オプション | 説明 |
|-----------|------|
| `--to win\|mac\|auto` | 開く側の OS。`win`=NFC、`mac`=NFD、`auto`=実行中の OS（既定） |
| `-o FILE` | 出力先を指定（1 ファイルのとき） |
| `-i`, `--inplace` | 元ファイルを上書き（`.bak` バックアップを作成） |
| `--all` | パス以外（クリップ名・シーケンス名など）も含めて全体を変換 |
| `-n`, `--dry-run` | 書き込まずに修正件数だけ表示 |
| `-v`, `--verbose` | 修正したパスを一覧表示 |

## 補足・注意

- 修復後の prproj を開いたあと、ドライブ名やフォルダ構成が異なる場合は、
  従来どおり Premiere Pro の「メディアをリンク」で場所を指定してください。
  濁点・半濁点が原因の不一致は解消されているため、フォルダを 1 つ指定すれば
  残りは自動で見つかるようになります。
- 素材ファイル側の名前も、コピー方法（NAS・USB メモリ・クラウド経由など）によっては
  NFD のまま Windows に渡ることがあります。その場合は変換方向を逆（`--to mac`）に
  すると一致することがあります。
- CJK 互換漢字（例: `﨑` U+FA11）は、通常の Unicode 正規化では別の字（`崎`）に
  置き換わってしまうため、macOS と同様に変換対象から除外しています。
- 念のため、元の prproj のバックアップを取ってから使ってください。

## 開発者向け

```sh
python3 -m unittest discover -s tests -v    # テスト
pip install pyinstaller
pyinstaller packaging/prp_path_fixer.spec   # 実行中の OS 向けのアプリを dist/ に作成
```
