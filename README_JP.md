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

ただし実機テストでは、一部の MechvibesDX ビルドにおいて `version` フィールドの型解析に不具合があり、
「インポート成功」と表示されても実際にはインポートされていない場合があります。

Mechvibes v1/v2 パックを Mechvibes に取り込む必要がある場合は、`--dx-compatible` を付けて
v1/v2 の `version` を `"1"` / `"2"` として出力してください。

## デフォルトの割り当て

キー名（例: `enter.wav`）と一致する音源は該当キーに割り当てられます（大文字小文字は無視）。
キー名は [v2.py](./mspt/schema/v2.py) の KeyName を参照してください。

その他の音源は残りのキーへバランスよくランダムに割り当てられます。

## Rule ファイル形式

rule ファイルは map オブジェクトのみを持ちます。詳細は [rule/example.rule.json](rule/example.rule.json)。

- map: audio file -> keynames のマッピング（正規表現または glob 対応）
- keynames に "*" を含む場合、その音源は fallback になります。未割り当てのキーは
  その音源を使用し、そうでない場合はデフォルトのランダム割り当てになります。

例：

```json
{
  "map": {
    "1.wav": ["Enter", "Tab"],
    "2.wav": ["Numpad0", "Numpad*"],
    "fallback.wav": ["*"]
  }
}
```

キー名とファイル名の両方で正規表現または glob が使えます。

## パッケージ

`target/<soundpack>` 配下から sourcemap.json を除いたファイルを zip 化し、target に出力します。

```py
# ワンショットまたは build 後に自動で zip 作成
mspt -i <your sound directory> --release

# pack サブコマンドを使用
mspt pack -i target/<soundpack>
```
