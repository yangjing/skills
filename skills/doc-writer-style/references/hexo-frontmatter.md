# Hexo frontmatter 参考（可选特性）

frontmatter YAML 是 Hexo 的要求，不是写作风格本身，也不是所有博客、文章系统都有此要求。本文件只登记 Hexo 通用事实；具体站点的格式选择、字段顺序、分类词表、文件名细则登记在各站 overlay（技能目录旁 `doc-writer-style.overlay.md`），overlay 优先于本文件。

## 兼容性（Hexo 7.3.0 + hexo-front-matter 4.2.1 实测）

| 写法 | 解析结果 |
|---|---|
| 标准 `---` 包裹（官方文档格式） | 正常：title、date、category、tags 全部解析，正文正确分离 |
| 省略开头 `---`，字段后以单个 `---` 与正文分隔 | 同样正常，解析结果与标准格式完全一致 |
| 全文无任何 `---` | 不解析：整篇被当作正文，元数据丢失 |

结论：开头 `---` 可以省，结尾 `---` 不能省。官方文档：https://hexo.io/docs/front-matter

## 官方 front-matter 变量

layout、title、date、updated、comments、tags、categories、permalink、excerpt 等。注意：

- 官方分类字段名为复数 `categories`；单数 `category` 也能被解析（实测），站点用哪种以 overlay 登记为准
- 日期格式 `YYYY-MM-DD HH:mm:ss`
- tags 接受 `[]` 行内列表或多行列表

## 文件名

由站点 `_config.yml` 的 `new_post_name` 决定（如 `:year-:month-:day-:title.md`）。写入前查看目标站点配置，或沿用该站点已有文章的命名习惯。
