Mechvibes SoundPack tools
===========================

此工具用于自动化生成 Mechvibes SoundPack。最简单的情况下，你只需要运行
`mspt -i <your sound directory>`，即可在 target 下看到对应的 soundpack。

## 1. 运行环境

- [ffmpeg](https://www.ffmpeg.org/)，用于音频合并与转码，需要在环境变量
- [python](https://www.python.org/)，但建议使用 [uv](https://docs.astral.sh/uv/) 进行管理

### 安装（使用 mspt 前必须安装）

```
# 激活当前 Python 环境后安装
pip install -e .
```

## 2. 作者信息

在 rule/common.json 设置作者名，例如：

```json
{
  "author": "YourName"
}
```

## 3. 运行方式

一键运行（生成 sound.ogg + sourcemap.json + config.json）：

```py
mspt -i <your sound directory>
```

分步运行：

```py
# step1: 生成 sound.ogg + sourcemap.json
mspt prepare -i <your sound directory>

# step2: 使用 sourcemap.json 生成 config.json
mspt build -i target/<soundpack>
```

打包:

```py
mspt -i <your sound directory> --release
# 或者
mspt pack -i target/<soundpack>
```

## 4. 工具选项

一键运行与 build 共享以下选项。

```
# 使用 rule 文件映射特定音频文件与按键
mspt -i <your sound directory> --rule rule/example.rule.json

# 将时间戳从中间分割，以适配 keyup keydown 分别播放
mspt build -i target/<soundpack> --split

# 自动打包为 zip 到 target 目录下
mspt -i <your sound directory> --release

# DX 兼容：在生成 Mechvibes v1/v2 时，将 version 输出为字符串（"1" / "2"）
mspt -i <your sound directory> --dx-compatible
```

## 已知问题

本项目的 Schema 按 Mechvibes wiki 标准实现：
https://github.com/hainguyents13/mechvibes/wiki/Config-Versions

但在实际测试中发现，部分 Mechvibes-dx 版本对 `version` 字段的类型解析存在 bug，
会出现“显示导入成功但实际没有导入”的情况。

如果你的 v1 与 v2 需要导入 Mechvibes-dx，请添加 `--dx-compatible` 参数，让 v1/v2 输出 `"version": "1"` / `"version": "2"`。

## 默认生成规则

带有按键名的音频（如 `enter.wav`) 会被映射到具体的按键。所有按键名参照 [v2.py](./mspt/schema/v2.py) 中的 KeyName（忽略大小写）

其他音频将被随机分配到其他按键。

## Rule 文件格式

rule 文件只包含一个 map 对象：`filePattern -> key selectors`。见 [rule/example.rule.json](rule/example.rule.json)。

说明：
- 顺序很重要（先匹配优先）：越靠前的规则越优先消耗文件；后面的规则不能重复使用已被消耗的文件。
- `filePattern` 支持：
  - 数字花括号范围 `{0-3}`（会展开为 glob 模式）
  - 正则（优先；大小写不敏感，`re.search`）
  - 正则编译失败时回退为 glob
- key selector 支持：精确按键名或正则/glob。
- fallback：
  - selector 列表中包含 `"*"`：该音频作为 keydown fallback（未分配按键会使用它）
  - selector 列表中包含 `"*_UP"`：该音频作为 keyup fallback（仅 Mechvibes v2）
- 在 key selector 上追加 `_UP` 后缀可以指定 key-up（仅 Mechvibes v2），例如 `"Enter_UP"` / `"Numpad*_UP"`。

rule 加载器支持 JSON5（允许注释与 trailing comma），所以示例 rule 里可以写 `//` 注释。

示例：

```json
{
  "map": {
    "1.wav": ["Enter", "Tab"],
    "{0-3}.wav": ["Numpad*"],
    "fallback.wav": ["*"]
  }
}
```

V2 key-up 示例（`_UP`）：

```json
{
  "map": {
    "down.wav": ["Enter", "*"],
    "up.wav": ["Enter_UP"],
    "up-fallback.wav": ["*_UP"]
  }
}
```

建议：把更具体的规则放前面，把更宽泛的规则（如 `"*"` fallback）放最后。

## 打包

打包会把 `target/<soundpack>` 下除 sourcemap.json 以外的文件压缩为 zip，并写到 target 目录下。

```py
# 在一键运行或 build 后自动打包
mspt -i <your sound directory> --release

# 或使用 pack 子命令
mspt pack -i target/<soundpack>
```
