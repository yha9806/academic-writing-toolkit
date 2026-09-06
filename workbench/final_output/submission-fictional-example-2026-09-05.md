# 投稿前校验报告

目标：Fictional thesis submission — revised rules
状态：存在阻断问题

本地规则检查及显式人工记录；按所选文件和规则快照评估。没有联网验证期刊要求、来源真实性或科学有效性，不代表投稿系统验收。

报告 SHA-256：`6ca68ce29098a81ce122aa4ea850f86a0ff2c976c18cabdb084d6130cc08458c`
绑定：`7cd83e31701eded7bc4503cd53ff5282194dc2e7718d0f6c2015d5e536242fcb`

## 文件与规则

规则 SHA-256：`6f5057074dec34ffa820a55e09834741a6d8537a277c8c0f68669f74d0fc76ef`

| 文件 | 角色 | SHA-256 |
|---|---|---|
| paper.md | manuscript | bc44fd3d887acb76b4a77bc325d4f2513a1f560239df32d9674d4f3a2cdb37fd |
| refs.bib | references | ca47d01126a0659c832e4db18304e237828e1cffd01516565f078999b14f1ccf |
| cover-letter.md | attachment | ead316ca34a671038de07e8ad0f63cf9c58e2f78d08dfa7084468206fb853ed5 |

## 检查结果

### 规则检查通过 · 已记录本轮要求配置

按填写的规则进行检查；没有联网验证来源。

### 规则检查通过 · 必需材料：cover-letter.md

已纳入并绑定文件哈希。

### 阻断问题 · 必需材料：checklist.pdf

当前检查范围没有这份文件。

### 警告 · 存在工作标记或未解决内容

TODO

- paper.md · 第 10 行：TODO explain the failed cases.
### 已记录人工核对 · 确认匿名范围与隐藏身份信息

检查标题页、致谢、自引措辞、文件名、图像、补充材料及隐藏属性；自动扫描只覆盖选为正文的文件。


人工记录：Fixture reviewer · 2026-09-05T17:13:04.623718+00:00 · checked · 虚构软件验收材料，本项已人工检查。此记录不代表真实作者批准。

### 阻断问题 · 正文长度与上限对照

提取统计 53，上限 1；单位为英文词及逐个汉字。正文包含标题、图注和表格，排除识别到的参考文献；最终口径须与指南一致。

### 规则检查通过 · 大纲章节：Methods

已找到实际标题；标题存在不证明章节任务已完成。

- paper.md · 第 3 行：# Methods
### 警告 · Methods：关键词 failed cases

本章及已识别子节没有匹配文本；请检查遗漏、别名或任务偏离。

- paper.md · 第 3 行：# Methods
### 需人工核对 · 确认章节任务落实：Methods

说明样本、比较方式及失败案例

- paper.md · 第 3 行：# Methods
### 规则检查通过 · 大纲章节：Results

已找到实际标题；标题存在不证明章节任务已完成。

- paper.md · 第 6 行：# Results
### 需人工核对 · 确认章节任务落实：Results

报告与大纲一致的结果

- paper.md · 第 6 行：# Results
### 阻断问题 · 未找到大纲章节：Conclusion

按归一化标题匹配；可能需要更正标题识别或填写实际标题。

### 阻断问题 · 必需声明：Data availability

选定正文中没有找到该声明标识。

### 警告 · 图 2 未找到正文引用

按可识别的图号匹配；范围引用、宏和图注识别误差需人工核对。

- paper.md · 第 8 行：Figure 2. An unreferenced analysis.
### 警告 · 图 9 未找到对应图注

请核对编号、补充材料或提取遗漏；发现文字引用不等于找到图像。

- paper.md · 第 5 行：See Figure 1(a), Figure 9 and Table 1.
### 需人工核对 · 核对图组内容与最终图像质量

核对多图之间的指标、单位、样本、图例、子图、正文结论和可读性；编号配对不验证图像内容。

### 规则检查通过 · BibTeX 离线结构检查通过

解析 1 条；未核实文献真实性、撤稿状态或在线元数据。

### 阻断问题 · 引用未找到条目：missing

只在纳入的参考文献中查找；请补充对应 .bib 或核对键名。

- paper.md · 第 4 行：ups were assessed. The protocol follows \cite{known,missing}.
### 规则检查通过 · 已完成所选引用模式扫描

识别 2 个引用项；配对问题见单独记录，未支持的样式仍需核对。

### 需人工核对 · 核对来源真实性与引用用途

离线检查不验证 DOI 可达性、题名作者一致性、撤稿状态及原文是否支持对应主张。可使用原有 verify-refs --online 工具辅助核验。

### 尚未检查 · 已有审阅覆盖

正文 12 处未完成文字批次；任务共 6 个已规划批次未完成，跨章节规划尚未完成。全部计划内批次完成仍不能证明发现全部问题。

### 尚未检查 · 部分正文没有可绑定的最终排版文件

请导入最终 PDF 或 DOCX 后核对排版；文本和源代码不能代替最终版面。

### 需人工核对 · 作者确认内容与提交材料

核对作者名单与顺序、声明、数据和图像使用权限，以及主张的证据边界；按实际适用要求记录决定。此工具不执行投稿。


## 规则快照

```json
{
  "target": "Fictional thesis submission — revised rules",
  "kind": "thesis",
  "requirements_source": "本地虚构验收规则 · 2026-09-05",
  "requirements_confirmed": true,
  "files": {
    "cover-letter.md": "attachment",
    "paper.md": "manuscript",
    "refs.bib": "references"
  },
  "count_unit": "words",
  "max_words": 1,
  "max_abstract_words": null,
  "max_pages": null,
  "max_figures": null,
  "max_tables": null,
  "page_width_mm": null,
  "page_height_mm": null,
  "min_image_dpi": null,
  "embedded_fonts": false,
  "anonymous": true,
  "anonymous_terms": [
    "Professor Identity"
  ],
  "citation_mode": "auto",
  "outline": [
    {
      "heading": "Methods",
      "task": "说明样本、比较方式及失败案例",
      "keywords": [
        "failed cases"
      ]
    },
    {
      "heading": "Results",
      "task": "报告与大纲一致的结果",
      "keywords": []
    },
    {
      "heading": "Conclusion",
      "task": "",
      "keywords": []
    }
  ],
  "declarations": [
    "Data availability"
  ],
  "required_files": [
    "cover-letter.md",
    "checklist.pdf"
  ],
  "require_model_review": true,
  "require_layout": true
}
```
