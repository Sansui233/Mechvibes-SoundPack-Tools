Mechvibes SoundPack tools
===========================

このツールは Mechvibes SoundPack を自動生成します。最も簡単な使い方は次の通りです。
`mspt -i <your sound directory>` を実行すると、target 配下に soundpack が生成されます。

## 1. 必要環境

- [ffmpeg](https://www.ffmpeg.org/)（PATH に通っている必要があります）
- [Python](https://www.python.org/)（[uv](https://docs.astral.sh/uv/) の利用を推奨）

### インストール（mspt を使う前に必須）

```
# 現在の Python 環境を有効化してからインストール
pip install -e .
```

## 2. 作者情報

rule/common.json に作者名を設定します。

```json
{
  "author": "YourName"
}
```

## 3. 実行方法

ワンショット（sound.ogg + sourcemap.json + config.json を生成）：

```py
mspt -i <your sound directory>
```

分割実行：

```py
# step1: sound.ogg + sourcemap.json を生成
mspt prepare -i <your sound directory>

# step2: sourcemap.json から config.json を生成
mspt build -i target/<soundpack>
```

パッケージ：

```py
mspt -i <your sound directory> --release
# または
mspt pack -i target/<soundpack>
```

## 4. オプション

ワンショットと build で共通のオプション：

```
# ルールファイルで音源とキーを対応付け
mspt -i <your sound directory> --rule rule/example.rule.json

# timing を keydown/keyup に分割
mspt build -i target/<soundpack> --split

# 自動で zip を作成
mspt -i <your sound directory> --release

# DX 互換：Mechvibes v1/v2 の version を文字列（"1" / "2"）で出力
mspt -i <your sound directory> --dx-compatible
```

## 既知の問題

本プロジェクトの Schema は Mechvibes wiki の仕様に準拠しています：
https://github.com/hainguyents13/mechvibes/wiki/Config-Versions

ただし実機テストでは、一部の Mechvibes-dx ビルドにおいて `version` フィールドの型解析に不具合があり、
「インポート成功」と表示されても実際にはインポートされていない場合があります。

Mechvibes v1/v2 パックを Mechvibes-dx に取り込む必要がある場合は、`--dx-compatible` を付けて
v1/v2 の `version` を `"1"` / `"2"` として出力してください。

## デフォルトの割り当て

キー名（例: `enter.wav`）と一致する音源は該当キーに割り当てられます（大文字小文字は無視）。
キー名は [v2.py](./mspt/schema/v2.py) の KeyName を参照してください。

その他の音源は残りのキーへバランスよくランダムに割り当てられます。

## Rule ファイル形式

rule ファイルは単一の map オブジェクトです：`filePattern -> key selectors`。
詳細は [rule/example.rule.json](rule/example.rule.json)。

ポイント：
- 順序が重要（先勝ち）: 前のルールが先にファイルを消費し、後のルールは消費済みファイルを再利用できません。
- `filePattern` は以下に対応:
  - 数値の波括弧レンジ `{0-3}`（glob に展開）
  - 正規表現（優先。大小文字無視、`re.search`）
  - 正規表現のコンパイル失敗時は glob にフォールバック
- key selector はキー名の完全一致、または正規表現/glob が使えます。
- fallback:
  - selector リストに `"*"` を含めると keydown fallback（未割り当てキーがそれを使用）
  - selector リストに `"*_UP"` を含めると keyup fallback（Mechvibes v2 のみ）
- key selector の末尾に `_UP` を付けると key-up 定義に割り当てます（Mechvibes v2 のみ）。例: `"Enter_UP"` / `"Numpad*_UP"`。

rule ローダーは JSON5（コメントや trailing comma）に対応しているため、`//` コメントが使えます。

例：

```json
{
  "map": {
    "1.wav": ["Enter", "Tab"],
    "{0-3}.wav": ["Numpad*"],
    "fallback.wav": ["*"]
  }
}
```

V2 key-up 例（`_UP`）：

```json
{
  "map": {
    "down.wav": ["Enter", "*"],
    "up.wav": ["Enter_UP"],
    "up-fallback.wav": ["*_UP"]
  }
}
```

ヒント: より具体的なパターンを先に、広いパターン（`"*"` fallback など）は最後に置いてください。

## パッケージ

`target/<soundpack>` 配下から sourcemap.json を除いたファイルを zip 化し、target に出力します。

```py
# ワンショットまたは build 後に自動で zip 作成
mspt -i <your sound directory> --release

# pack サブコマンドを使用
mspt pack -i target/<soundpack>
```
