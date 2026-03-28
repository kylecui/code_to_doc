# code-to-doc

把目录中的源代码文件递归收集后，按路径顺序写入一个 Markdown 文档。

每个文件输出格式：

```text
<相对路径>
```语言
文件内容
```
```

自动跳过：

- 依赖目录与构建产物（如 `.venv`、`node_modules`、`dist`、`build` 等）
- 非源码文件（按扩展名过滤）
- 二进制文件
- 临时文件和常见中间产物
- 忽略规则命中的文件（默认读取 `.gitignore`，也可自定义）

## 使用 uv

```bash
uv sync
uv run code-to-doc <源码目录> <输出markdown文件>
```

示例：

```bash
uv run code-to-doc . out/source_dump.md
```

可选参数：

```bash
# 仅导出指定扩展名（支持重复传参或逗号分隔）
uv run code-to-doc . out/source_dump.md --include-ext .py,.ts --include-ext .tsx

# 排除指定扩展名
uv run code-to-doc . out/source_dump.md --exclude-ext .json

# 指定忽略规则文件（gitignore 语法）
uv run code-to-doc . out/source_dump.md --ignore-file .gitignore

# 跟随符号链接目录
uv run code-to-doc . out/source_dump.md --follow-symlinks

# 限制导出文件大小（支持 B/KB/MB/GB）
uv run code-to-doc . out/source_dump.md --max-file-size 500KB
```

运行结束后会输出统计信息：

- Scanned files: 扫描到的文件总数
- Exported source files: 最终导出的源码文件数
- Exported source lines: 导出的源码总行数
- Skipped files: 总跳过文件数
- 以及按原因分组的跳过计数（如 ignore 规则、扩展名过滤、过大文件、二进制文件等）
