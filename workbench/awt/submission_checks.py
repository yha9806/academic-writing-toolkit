"""Offline, source-bound pre-submission checks; no model or network access."""
from __future__ import annotations

import bisect
import io
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

from awt.documents import DocumentError
from awt.review_index import fingerprint

VERSION = 1
STATUSES = ("block", "warning", "manual", "unchecked", "pass", "recorded")
FILE_ROLES = {"manuscript", "references", "attachment", "exclude"}
LABELS = {"block": "阻断问题", "warning": "警告", "manual": "需人工核对", "unchecked": "尚未检查", "pass": "规则检查通过", "recorded": "已记录人工核对"}
MAX_ITEMS = 2000


def default_profile(documents):
    return {"target": "", "kind": "journal", "requirements_source": "", "requirements_confirmed": False,
            "files": {d["filename"]: "references" if d["format"] == "bib" else "manuscript" if d["format"] in {"pdf", "docx", "txt", "md", "tex"} else "attachment" for d in documents},
            "count_unit": "words", "max_words": None, "max_abstract_words": None, "max_pages": None,
            "max_figures": None, "max_tables": None, "page_width_mm": None, "page_height_mm": None,
            "min_image_dpi": None, "embedded_fonts": False, "anonymous": False, "anonymous_terms": [],
            "citation_mode": "auto", "outline": [], "declarations": [], "required_files": [],
            "require_model_review": False, "require_layout": False}


def normalise_profile(value, documents):
    defaults = default_profile(documents)
    if not isinstance(value, dict) or set(value) - set(defaults):
        raise DocumentError("投稿规则包含未知字段或格式无效")
    result = {**defaults, **value}
    for key, limit in (("target", 200), ("requirements_source", 1200)):
        if not isinstance(result[key], str) or len(result[key]) > limit:
            raise DocumentError("投稿目标或要求来源过长")
        result[key] = result[key].strip()
    for key in ("requirements_confirmed", "embedded_fonts", "anonymous", "require_model_review", "require_layout"):
        if type(result[key]) is not bool:
            raise DocumentError("投稿规则开关需要布尔值")
    for key, choices in (("kind", {"journal", "thesis", "other"}), ("count_unit", {"words", "characters"}),
                         ("citation_mode", {"auto", "tex", "numbered", "author_year", "none"})):
        if not isinstance(result[key], str) or result[key] not in choices:
            raise DocumentError("投稿规则选项无效：" + key)
    for key, maximum in (("max_words", 12000000), ("max_abstract_words", 12000000), ("max_pages", 20000),
                         ("max_figures", 10000), ("max_tables", 10000), ("page_width_mm", 2000),
                         ("page_height_mm", 2000), ("min_image_dpi", 2400)):
        if result[key] is not None and (type(result[key]) is not int or not 1 <= result[key] <= maximum):
            raise DocumentError("投稿数量或尺寸上限无效：" + key)
    names = {d["filename"] for d in documents}
    if bool(result["page_width_mm"]) != bool(result["page_height_mm"]):
        raise DocumentError("页面宽度和高度要求需要同时填写")
    roles = result["files"]
    if not isinstance(roles, dict) or set(roles) - names or any(not isinstance(v, str) or v not in FILE_ROLES for v in roles.values()):
        raise DocumentError("材料角色与当前文件不匹配，请重新选择")
    result["files"] = {name: roles.get(name, "exclude") for name in sorted(names)}
    if "manuscript" not in result["files"].values():
        raise DocumentError("至少选择一份正文；同一稿件的 PDF 和源文件请避免重复计入正文")
    for key in ("anonymous_terms", "declarations", "required_files"):
        items = result[key]
        if not isinstance(items, list) or len(items) > 100 or any(not isinstance(s, str) or not s.strip() or len(s) > 250 for s in items):
            raise DocumentError("规则清单需要最多 100 条非空短文本：" + key)
        result[key] = list(dict.fromkeys(s.strip() for s in items))
    if any("/" in name or "\\" in name or name in {".", ".."} for name in result["required_files"]):
        raise DocumentError("必需材料请填写文件名，不填写本机路径")
    outline = result["outline"]
    if not isinstance(outline, list) or len(outline) > 200:
        raise DocumentError("大纲最多 200 项")
    clean = []
    for row in outline:
        if not isinstance(row, dict) or set(row) - {"heading", "task", "keywords"}:
            raise DocumentError("大纲项格式无效")
        heading, task, keywords = row.get("heading", ""), row.get("task", ""), row.get("keywords", [])
        if not isinstance(heading, str) or not heading.strip() or len(heading) > 180 or not isinstance(task, str) or len(task) > 600:
            raise DocumentError("每项大纲需要标题；任务说明最多 600 字符")
        if not isinstance(keywords, list) or len(keywords) > 20 or any(not isinstance(k, str) or not k.strip() or len(k) > 100 for k in keywords):
            raise DocumentError("大纲关键词格式无效")
        clean.append({"heading": heading.strip(), "task": task.strip(), "keywords": list(dict.fromkeys(k.strip() for k in keywords))})
    if len({normal_heading(r["heading"]) for r in clean}) != len(clean):
        raise DocumentError("大纲标题重复，请使用可区分的完整章节标题")
    result["outline"] = clean
    return result


def normal_heading(value):
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    value = re.sub(r"^\s*(?:#+\s*|\d+(?:\.\d+)*[.、]?\s+)", "", value)
    return re.sub(r"\s+", " ", value).rstrip(" .:：")


def count_text(value, unit):
    if unit == "characters":
        return sum(not ch.isspace() for ch in value)
    # English words plus individual CJK characters; the report states this scope.
    return len(re.findall(r"[A-Za-zÀ-ɏ0-9]+(?:['’\-][A-Za-zÀ-ɏ0-9]+)*|[\u3400-\u9fff]", value))


class Source:
    def __init__(self, document):
        self.document = document
        self.blocks = document["blocks"]
        self.starts, at = [], 0
        for block in self.blocks:
            self.starts.append(at)
            at += len(block["text"]) + 1
        self.text = "\n".join(b["text"] for b in self.blocks)

    def anchor(self, at=0):
        if not self.blocks:
            return {"filename": self.document["filename"], "location": "文件", "locator": "", "quote": ""}
        index = max(0, bisect.bisect_right(self.starts, at) - 1)
        block = self.blocks[index]
        offset = max(0, at - self.starts[index])
        return {"filename": self.document["filename"], "location": block["locator"], "locator": block["id"],
                "quote": block["text"][max(0, offset - 40):offset + 180]}


class Findings:
    def __init__(self):
        self.items, self.counts, self.total = [], Counter(), 0

    def add(self, code, status, title, detail, anchors=(), group="materials"):
        self.total += 1
        self.counts[status] += 1
        item = {"id": fingerprint([self.total, code, title, detail, list(anchors)])[:24], "code": code, "status": status,
                "title": title, "detail": detail, "anchors": list(anchors)[:4], "group": group}
        if len(self.items) < MAX_ITEMS:
            self.items.append(item)


def _braced(text, start, opening="{", closing="}"):
    depth, quoted, escaped = 1, False, False
    for end in range(start + 1, len(text)):
        char = text[end]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"' and depth == 1:
            quoted = not quoted
        elif not quoted:
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if not depth:
                    return text[start + 1:end], end + 1
    raise ValueError("unclosed entry")


def bib_entries(text):
    """Balanced multiline/single-line BibTeX; macros are never executed."""
    entries, errors, at = [], [], 0
    pattern = re.compile(r"@([A-Za-z]+)\s*([({])")
    while True:
        match = pattern.search(text, at)
        if not match:
            break
        try:
            body, at = _braced(text, match.end() - 1, match[2], ")" if match[2] == "(" else "}")
        except ValueError:
            errors.append(match.start())
            break
        kind = match[1].lower()
        if kind in {"comment", "preamble", "string"}:
            continue
        if "," not in body:
            errors.append(match.start())
            continue
        key, fields_text = body.split(",", 1)
        fields, pos = {}, 0
        while True:
            field = re.search(r"([A-Za-z_]+)\s*=\s*", fields_text[pos:])
            if not field:
                break
            begin = pos + field.end()
            try:
                if fields_text[begin:begin + 1] == "{":
                    value, end = _braced(fields_text, begin)
                elif fields_text[begin:begin + 1] == '"':
                    end = begin + 1
                    while end < len(fields_text) and (fields_text[end] != '"' or fields_text[end - 1] == "\\"):
                        end += 1
                    if end == len(fields_text):
                        raise ValueError()
                    value, end = fields_text[begin + 1:end], end + 1
                else:
                    end = fields_text.find(",", begin)
                    end = len(fields_text) if end < 0 else end
                    value = fields_text[begin:end]
            except ValueError:
                errors.append(match.start())
                break
            fields[field[1].lower()] = " ".join(value.strip().split())
            pos = end
        entries.append({"key": key.strip(), "type": kind, "fields": fields, "offset": match.start()})
    return entries, errors


def check_references(sources, reference_sources, profile, out):
    entries, by_key = [], defaultdict(list)
    required = {"article": ("title", "author", "year", "journal"), "inproceedings": ("title", "author", "year", "booktitle"),
                "book": ("title", "author", "year", "publisher"), "phdthesis": ("title", "author", "year", "school")}
    bib_sources = [s for s in reference_sources + sources if s.document["format"] == "bib" or re.search(r"@(?:article|book|inproceedings|misc|phdthesis)\s*[{(]", s.text, re.I)]
    errors_before = out.counts["block"] + out.counts["warning"]
    for source in bib_sources:
        rows, errors = bib_entries(source.text)
        for offset in errors:
            out.add("bib_parse", "warning", "参考文献条目未完整解析", "请核对括号、引号或宏；未解析条目不计为校验通过。", [source.anchor(offset)], "references")
        for row in rows:
            row["anchor"] = source.anchor(row["offset"])
            entries.append(row)
            by_key[row["key"]].append(row)
            fields = row["fields"]
            missing = [key for key in required.get(row["type"], ("title", "year")) if not fields.get(key)]
            if missing:
                out.add("bib_fields", "block", "参考文献缺少必需字段：" + row["key"], "缺少 " + ", ".join(missing), [row["anchor"]], "references")
            for key, pattern in (("doi", r"10\.\d{4,9}/\S+"), ("url", r"https?://[^\s/]+(?:/\S*)?"), ("year", r"(?:18|19|20|21)\d{2}[a-z]?")):
                if fields.get(key) and not re.fullmatch(pattern, fields[key], re.I):
                    out.add("bib_format", "warning", "参考文献字段格式需核对：" + row["key"], key + " = " + fields[key][:180], [row["anchor"]], "references")
    for key, rows in by_key.items():
        if len(rows) > 1:
            out.add("bib_duplicate", "block", "重复的参考文献键：" + key, "共 " + str(len(rows)) + " 条。", [r["anchor"] for r in rows], "references")
    if entries and errors_before == out.counts["block"] + out.counts["warning"]:
        out.add("bib_structure", "pass", "BibTeX 离线结构检查通过", f"解析 {len(entries)} 条；未核实文献真实性、撤稿状态或在线元数据。", group="references")
    mode, found, used = profile["citation_mode"], 0, set()
    if mode == "none":
        out.add("citation_scope", "pass", "按当前规则不检查文内引用配对", "此选项已写入报告规则快照。", group="references")
        return
    if mode in {"auto", "tex"}:
        for source in sources:
            for match in re.finditer(r"\\(?:[A-Za-z]*cite[A-Za-z]*|nocite)\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}", source.text):
                for key in (s.strip() for s in match[1].split(",")):
                    if key == "*":
                        used.update(by_key)
                        continue
                    found += 1
                    used.add(key)
                    if key not in by_key:
                        out.add("citation_missing", "warning" if not bib_sources else "block", "引用未找到条目：" + key,
                                "只在纳入的参考文献中查找；请补充对应 .bib 或核对键名。", [source.anchor(match.start())], "references")
    numbered = {}
    for source in reference_sources + sources:
        for match in re.finditer(r"(?m)^\s*\[?(\d{1,5})[\].)]\s+\S", source.text):
            anchor = source.anchor(match.start())
            block = source.blocks[max(0, bisect.bisect_right(source.starts, match.start()) - 1)] if source.blocks else None
            if source in reference_sources or (block and block["role"] == "references"):
                numbered[match[1]] = anchor
    if mode in {"auto", "numbered"}:
        for source in sources:
            for index, block in enumerate(source.blocks):
                if block["role"] == "references":
                    continue
                for match in re.finditer(r"\[(\d{1,5}(?:\s*[,;–-]\s*\d{1,5})*)\]", block["text"]):
                    keys = []
                    for part in re.split(r"[,;]", match[1]):
                        interval = re.split(r"[–-]", part.strip())
                        if len(interval) == 2 and 0 <= int(interval[1]) - int(interval[0]) <= 100:
                            keys.extend(str(n) for n in range(int(interval[0]), int(interval[1]) + 1))
                        elif len(interval) == 1:
                            keys.append(str(int(interval[0])))
                    if not keys:
                        continue
                    found += len(keys)
                    missing = [k for k in keys if k not in numbered]
                    if missing:
                        out.add("numbered_citation", "warning" if numbered else "unchecked", "数字引用待核对：" + match[0],
                                "未匹配 " + ", ".join(missing) + "；数字方括号也可能属于数据或公式。", [source.anchor(source.starts[index] + match.start())], "references")
    if mode in {"auto", "author_year"}:
        author_keys = set()
        for entry in entries:
            fields = entry["fields"]
            author = re.sub(r"[{}]", "", fields.get("author", "").split(" and ")[0]).strip()
            surname = author.split(",")[0].strip() if "," in author else (author.split()[-1] if author else "")
            author_keys.add((surname.casefold(), fields.get("year", "")[:4]))
        for source in sources:
            for match in re.finditer(r"\b([A-Z][A-Za-z'’\-]+)(?:\s+et\s+al\.?)?\s*(?:\(\s*|,\s*)((?:19|20)\d{2})[a-z]?", source.text):
                anchor = source.anchor(match.start())
                block = source.blocks[max(0, bisect.bisect_right(source.starts, match.start()) - 1)]
                if block["role"] == "references":
                    continue
                found += 1
                if (match[1].casefold(), match[2]) not in author_keys:
                    out.add("author_year_citation", "warning" if entries else "unchecked", "作者—年份引用待核对：" + match[0],
                            "未找到首作者姓氏与年份均匹配的 BibTeX 条目；姓名变体、多作者及中文引用需要人工核对。", [anchor], "references")
    if not found:
        out.add("citation_not_found", "unchecked", "未识别到可配对的文内引用", "支持常见 LaTeX cite、数字方括号和部分作者—年份形式；不代表全文没有引用。", group="references")
    else:
        out.add("citation_scan", "pass", "已完成所选引用模式扫描", f"识别 {found} 个引用项；配对问题见单独记录，未支持的样式仍需核对。", group="references")
    if entries or numbered or reference_sources:
        out.add("reference_truth", "manual", "核对来源真实性与引用用途", "离线检查不验证 DOI 可达性、题名作者一致性、撤稿状态及原文是否支持对应主张。可使用原有 verify-refs --online 工具辅助核验。", group="references")


FIGURE = re.compile(r"(?i)(?<![A-Za-z])(?P<kind>Figures?|Figs?\.?|Tables?|图|表)\s*(?P<number>[A-Z]?\d+(?:\.\d+)*(?:[a-z]|\([a-z]\))?)(?!\d)")


def figure_key(match):
    kind = "table" if match["kind"].casefold().startswith(("table", "表")) else "figure"
    number = match["number"].casefold()
    return kind, number


def check_figures(sources, profile, out):
    definitions, mentions, tex_labels, tex_refs = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for source in sources:
        for index, block in enumerate(source.blocks):
            if block["role"] == "references":
                continue
            for match in FIGURE.finditer(block["text"]):
                key = figure_key(match)
                prefix = block["text"][:match.start()].strip(" \t#*")
                tail = block["text"][match.end():]
                caption = not prefix and (bool(re.match(r"\s*[:.：、]\s*", tail)) or block["kind"] == "caption")
                (definitions if caption else mentions)[key].append(source.anchor(source.starts[index] + match.start()))
            for match in re.finditer(r"\\label\{([^}]+)\}", block["text"]):
                tex_labels[match[1]].append(source.anchor(source.starts[index] + match.start()))
            for match in re.finditer(r"\\(?:ref|autoref|[cC]ref|eqref)\*?\{([^}]+)\}", block["text"]):
                for key in match[1].split(","):
                    tex_refs[key.strip()].append(source.anchor(source.starts[index] + match.start()))
    for key, anchors in definitions.items():
        name = ("表 " if key[0] == "table" else "图 ") + key[1]
        if len(anchors) > 1:
            out.add("figure_duplicate", "warning", name + " 的图注编号重复", "可能是重复图注、不同文件重复稿件或章节编号冲突；需确认。", anchors, "figures")
        children = [k for k in mentions if k[0] == key[0] and re.sub(r"(?:\([a-z]\)|[a-z])$", "", k[1]) == key[1]]
        if key not in mentions and not children:
            out.add("figure_orphan", "warning", name + " 未找到正文引用", "按可识别的图号匹配；范围引用、宏和图注识别误差需人工核对。", anchors, "figures")
    for key, anchors in mentions.items():
        parent = (key[0], re.sub(r"(?:\([a-z]\)|[a-z])$", "", key[1]))
        if key not in definitions and parent not in definitions:
            out.add("figure_missing", "warning", ("表 " if key[0] == "table" else "图 ") + key[1] + " 未找到对应图注",
                    "请核对编号、补充材料或提取遗漏；发现文字引用不等于找到图像。", anchors, "figures")
    for key, anchors in tex_labels.items():
        if len(anchors) > 1:
            out.add("tex_label_duplicate", "block", "LaTeX label 重复：" + key, "请核对选定源文件。", anchors, "figures")
    for key, anchors in tex_refs.items():
        if key not in tex_labels:
            out.add("tex_ref_missing", "warning", "LaTeX 引用未找到 label：" + key, "没有追踪未选中的 include/input 文件；请补齐材料或检查引用。", anchors, "figures")
    counts = {kind: len({re.sub(r"(?:\([a-z]\)|[a-z])$", "", number) for k, number in definitions if k == kind}) for kind in ("figure", "table")}
    for kind, label in (("figure", "图"), ("table", "表")):
        limit = profile["max_" + kind + "s"]
        if limit is not None:
            count = counts[kind]
            out.add(kind + "_limit", "block" if count > limit else "manual", label + "数量与上限对照",
                    f"识别到 {count} 个独立编号，上限 {limit}。未编号图、范围和子图分组须人工确认。", group="figures")
    if definitions or tex_labels or profile["min_image_dpi"] or any(s.document["assets"] for s in sources):
        detail = "核对多图之间的指标、单位、样本、图例、子图、正文结论和可读性；编号配对不验证图像内容。"
        if profile["min_image_dpi"]:
            detail += f" 当前要求至少 {profile['min_image_dpi']} DPI，须按最终版面尺寸核验有效分辨率。"
        out.add("figure_semantics", "manual", "核对图组内容与最终图像质量", detail, group="figures")
    return counts


def check_pdf(source, raw, profile, out, progress):
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:
        out.add("pdf_inspection", "unchecked", source.document["filename"] + "：未检查 PDF 字体及元数据", "安装 documents 可选依赖后重试。", group="layout")
        return
    try:
        reader = PdfReader(io.BytesIO(raw))
        metadata = reader.metadata or {}
        if profile["anonymous"]:
            author = str(metadata.get("/Author", "")).strip()
            if author and author.casefold() not in {"anonymous", "unknown", "none", "anonymised", "anonymized"}:
                out.add("pdf_author", "warning", source.document["filename"] + "：PDF 作者元数据非空", "请核对匿名稿属性中的 Author 字段；可见正文与其他嵌入内容也需核对。", group="anonymity")
        seen, missing, annotations = set(), [], []
        for number, page in enumerate(reader.pages, 1):
            if number % 25 == 1:
                progress("检查 PDF 字体与页面 " + str(number))
            if profile["page_width_mm"] and profile["page_height_mm"]:
                sizes = [float(page.mediabox.width) * 25.4 / 72, float(page.mediabox.height) * 25.4 / 72]
                expected = [profile["page_width_mm"], profile["page_height_mm"]]
                if any(abs(a - b) > 1 for a, b in zip(sizes, expected)):
                    out.add("pdf_size", "block", f"{source.document['filename']}：第 {number} 页尺寸不符", f"页面约 {sizes[0]:.1f} × {sizes[1]:.1f} mm；要求 {expected[0]} × {expected[1]} mm（容差 1 mm）。", group="layout")
            resources = page.get("/Resources")
            fonts = resources.get_object().get("/Font", {}) if resources else {}
            for reference in fonts.get_object().values() if hasattr(fonts, "get_object") else fonts.values():
                font = reference.get_object()
                label = str(font.get("/BaseFont", "unnamed"))
                identity = (reference.idnum, reference.generation) if hasattr(reference, "idnum") else id(font)
                if identity in seen:
                    continue
                seen.add(identity)
                descendants = font.get("/DescendantFonts", [])
                base = descendants[0].get_object() if descendants else font
                descriptor = base.get("/FontDescriptor")
                descriptor = descriptor.get_object() if descriptor else {}
                if font.get("/Subtype") != "/Type3" and not any(k in descriptor for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                    missing.append(f"{label}（第 {number} 页）")
            for reference in page.get("/Annots", []):
                if str(reference.get_object().get("/Subtype")) in {"/Text", "/FreeText", "/Popup", "/FileAttachment", "/Redact"}:
                    annotations.append(number)
                    break
        if missing:
            out.add("pdf_fonts", "block" if profile["embedded_fonts"] else "warning", source.document["filename"] + "：发现未嵌入字体", ", ".join(missing[:30]) + "。只检查页面字体资源；图形对象内字体仍需核对。", group="layout")
        elif seen:
            out.add("pdf_fonts", "pass", source.document["filename"] + "：已识别页面字体有嵌入信息", f"检查 {len(seen)} 个字体资源；此项不证明最终排版无误。", group="layout")
        else:
            out.add("pdf_fonts", "unchecked", source.document["filename"] + "：未识别到可检查的页面字体", "可能为扫描图像或字体位于其他图形对象；需要核对实际文件。", group="layout")
        if annotations:
            out.add("pdf_annotations", "warning", source.document["filename"] + "：PDF 保留批注或附加内容", "涉及页码：" + ", ".join(map(str, annotations[:50])), group="layout")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, PyPdfError):
        out.add("pdf_inspection", "unchecked", source.document["filename"] + "：PDF 结构检查未完成", "文件结构无法完整解析；需要人工检查字体、元数据和页面属性。", group="layout")


def check_docx(source, raw, profile, out, progress):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if profile["anonymous"] and "docProps/core.xml" in archive.namelist():
                root = ET.fromstring(archive.read("docProps/core.xml"))
                values = [n.text for n in root.iter() if n.tag.rsplit("}", 1)[-1] in {"creator", "lastModifiedBy"} and n.text and n.text.strip().casefold() not in {"anonymous", "unknown"}]
                if values:
                    out.add("docx_author", "warning", source.document["filename"] + "：Word 作者属性非空", "请核对创建者、最后修改者及其他隐藏属性。", group="anonymity")
            counts = Counter()
            for name in ("word/document.xml", "word/comments.xml"):
                if name not in archive.namelist():
                    continue
                with archive.open(name) as stream:
                    for index, (_, node) in enumerate(ET.iterparse(stream, events=("end",))):
                        if index % 1000 == 0:
                            progress("检查 Word 修订与批注")
                        local = node.tag.rsplit("}", 1)[-1]
                        if local in {"ins", "del", "comment"}:
                            counts[local] += 1
                        node.clear()
            if sum(counts.values()):
                out.add("docx_revisions", "warning", source.document["filename"] + "：存在修订或批注", f"插入标记 {counts['ins']}、删除标记 {counts['del']}、批注 {counts['comment']}；请检查最终提交视图。", group="layout")
            else:
                out.add("docx_revisions", "pass", source.document["filename"] + "：已扫描正文未发现修订/批注标记", "未检查页眉页脚等其他故事范围，也未代替 Word 文档检查器。", group="layout")
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, ET.ParseError):
        out.add("docx_inspection", "unchecked", source.document["filename"] + "：Word 结构检查未完成", "请用 Word 检查修订、批注及隐藏属性。", group="layout")


def build_report(job, profile, read_source, progress=lambda stage: None):
    out = Findings()
    chosen = [d for d in job["documents"] if profile["files"].get(d["filename"]) != "exclude"]
    sources = [Source(d) for d in chosen if profile["files"][d["filename"]] == "manuscript"]
    refs = [Source(d) for d in chosen if profile["files"][d["filename"]] == "references"]
    if not profile["target"] or not profile["requirements_source"] or not profile["requirements_confirmed"]:
        out.add("venue_rules", "manual", "确认本次适用的投稿或送审要求", "填写目标和要求来源，并按当前指南确认规则；内置检查不自带最新期刊或学校标准。", group="rules")
    else:
        out.add("venue_rules", "pass", "已记录本轮要求配置", "按填写的规则进行检查；没有联网验证来源。", group="rules")
    by_name = {d["filename"]: d for d in chosen}
    for name in profile["required_files"]:
        out.add("required_file", "pass" if name in by_name else "block", "必需材料：" + name,
                "已纳入并绑定文件哈希。" if name in by_name else "当前检查范围没有这份文件。", group="materials")
    unknown_text = False
    for source in sources:
        progress("扫描 " + source.document["filename"])
        raw = read_source(source.document)
        if not source.text.strip() or any(not p.get("text_chars", 0) for p in source.document["pages"]):
            unknown_text = True
            out.add("text_missing", "unchecked", source.document["filename"] + "：存在无法确认的文字覆盖", "空白页、扫描页或提取遗漏不能计为文字审阅通过；当前没有自动 OCR。", group="materials")
        for match in re.finditer(r"\b(?:TODO|FIXME|TBD|XXX)\b|待补充|待完善|此处插入|\?\?", source.text, re.I):
            out.add("placeholder", "warning", "存在工作标记或未解决内容", match[0], [source.anchor(match.start())], "materials")
        for match in re.finditer(r"(?:[A-Za-z]:[\\/](?:Users|project|coproject)[^\s<>\"']*|/(?:Users|home)/[^\s<>\"']+)", source.text):
            out.add("local_path", "warning", "正文出现本机绝对路径", "请核对该路径是否应出现在提交稿中。", [source.anchor(match.start())], "materials")
        if profile["anonymous"]:
            for term in profile["anonymous_terms"]:
                match = re.search(re.escape(term), source.text, re.I)
                if match:
                    out.add("anonymous_term", "warning", "匿名稿出现需核对的信息：" + term, "这可能是作者身份，也可能是正常引文；请结合上下文判断。", [source.anchor(match.start())], "anonymity")
            email = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", source.text)
            if email:
                out.add("anonymous_email", "warning", "匿名正文出现电子邮箱", "核对邮箱归属和投稿匿名要求。", [source.anchor(email.start())], "anonymity")
        if source.document["format"] == "pdf":
            check_pdf(source, raw, profile, out, progress)
        elif source.document["format"] == "docx":
            check_docx(source, raw, profile, out, progress)
    if profile["anonymous"]:
        out.add("anonymous_manual", "manual", "确认匿名范围与隐藏身份信息", "检查标题页、致谢、自引措辞、文件名、图像、补充材料及隐藏属性；自动扫描只覆盖选为正文的文件。", group="anonymity")
    unit = profile["count_unit"]
    main_blocks = [b for s in sources for b in s.blocks if b["role"] != "references"]
    abstract_blocks = [b for b in main_blocks if b["role"] == "abstract"]
    metrics = {"text_count": sum(count_text(b["text"], unit) for b in main_blocks), "abstract_count": sum(count_text(b["text"], unit) for b in abstract_blocks),
               "count_unit": unit, "pdf_pages": sum(len(s.document["pages"]) for s in sources if s.document["format"] == "pdf")}
    for name, key, count, incomplete in (("正文", "max_words", metrics["text_count"], unknown_text),
                                        ("摘要", "max_abstract_words", metrics["abstract_count"], not abstract_blocks or unknown_text)):
        if profile[key] is not None:
            out.add(key, "block" if count > profile[key] else "unchecked" if incomplete else "pass", name + "长度与上限对照",
                    f"提取统计 {count}，上限 {profile[key]}；单位为{'非空白字符' if unit == 'characters' else '英文词及逐个汉字'}。正文包含标题、图注和表格，排除识别到的参考文献；最终口径须与指南一致。", group="limits")
    if profile["max_pages"] is not None:
        unknown_pages = any(s.document["format"] != "pdf" for s in sources)
        out.add("page_limit", "block" if metrics["pdf_pages"] > profile["max_pages"] else "unchecked" if unknown_pages else "pass",
                "正文页数与上限对照", f"已选 PDF 共 {metrics['pdf_pages']} 页，上限 {profile['max_pages']}；DOCX/文本须以最终 PDF 确定页数。", group="limits")
    if any(s.document["format"] != "pdf" for s in sources) and (profile["embedded_fonts"] or profile["page_width_mm"]):
        out.add("final_pdf_missing", "unchecked", "部分正文尚无最终 PDF 页面属性", "字体嵌入及物理页面尺寸规则只能对最终 PDF 检查；未渲染的 DOCX/文本不能计为通过。", group="layout")
    if not profile["outline"]:
        out.add("outline_unset", "unchecked", "未配置预期大纲", "可填写必需章节、章节任务和关键词，再检查大纲与正文的对应。", group="outline")
    actual = defaultdict(list)
    for source in sources:
        seen = set()
        for index, block in enumerate(source.blocks):
            heading = normal_heading(block["section"])
            if heading not in seen:
                seen.add(heading)
                actual[heading].append((source, block, index))
    for row in profile["outline"]:
        matches = actual.get(normal_heading(row["heading"]), [])
        if not matches:
            out.add("outline_missing", "block", "未找到大纲章节：" + row["heading"], "按归一化标题匹配；可能需要更正标题识别或填写实际标题。", group="outline")
            continue
        anchors = [s.anchor(s.starts[i]) for s, _, i in matches]
        out.add("outline_present", "warning" if len(matches) > 1 else "pass", "大纲章节：" + row["heading"],
                "多个正文文件有同名章节，请确认对应关系。" if len(matches) > 1 else "已找到实际标题；标题存在不证明章节任务已完成。", anchors, "outline")
        text = "\n".join(b["text"] for s, matched, _ in matches for b in s.blocks
                         if b["section"] == matched["section"] or matched["section"] in b.get("section_path", []))
        for keyword in row["keywords"]:
            present = keyword.casefold() in text.casefold()
            out.add("outline_keyword", "pass" if present else "warning", row["heading"] + "：关键词 " + keyword,
                    "找到字面文本；未判断论证充分性。" if present else "本章及已识别子节没有匹配文本；请检查遗漏、别名或任务偏离。", anchors, "outline")
        if row["task"]:
            out.add("outline_task", "manual", "确认章节任务落实：" + row["heading"], row["task"], anchors, "outline")
    for declaration in profile["declarations"]:
        match = next(((s, re.search(re.escape(declaration), s.text, re.I)) for s in sources if re.search(re.escape(declaration), s.text, re.I)), None)
        out.add("declaration", "manual" if match else "block", "必需声明：" + declaration,
                "已找到声明标识；须确认内容准确、适用且获相应作者确认。" if match else "选定正文中没有找到该声明标识。", [match[0].anchor(match[1].start())] if match else [], "declarations")
    progress("检查图表、交叉引用与参考文献")
    metrics.update(check_figures(sources, profile, out))
    check_references(sources, refs, profile, out)
    progress("汇总已有审阅和排版记录")
    done = [s for s in job["steps"] if s["status"] == "completed" and s["revision"] == job["revision"]]
    reviewed = {i for s in done if s["phase"] == "text" for i in s["block_ids"]}
    main_ids = {b["id"] for source in sources for b in source.blocks}
    remaining = len(main_ids - reviewed)
    metrics["unreviewed_blocks"] = remaining
    if profile["require_model_review"]:
        pending = sum(s["status"] != "completed" or s["revision"] != job["revision"] for s in job["steps"])
        out.add("review_coverage", "unchecked" if remaining or pending or not job["cross_built"] else "pass", "已有审阅覆盖",
                f"正文 {remaining} 处未完成文字批次；任务共 {pending} 个已规划批次未完成，跨章节规划{'已完成' if job['cross_built'] else '尚未完成'}。全部计划内批次完成仍不能证明发现全部问题。", group="review")
    for step in done:
        for finding in step["result"]["findings"]:
            out.add("review_finding", "warning", "已有模型意见：" + finding["message"], "模型意见需作者核对；记录处理决定不会改变原审阅结果。",
                    [{**a, "filename": "", "location": a["locator"]} for a in finding["anchors"]], "review")
    if profile["require_layout"] and any(s.document["format"] not in {"pdf", "docx"} for s in sources):
        out.add("layout_missing", "unchecked", "部分正文没有可绑定的最终排版文件", "请导入最终 PDF 或 DOCX 后核对排版；文本和源代码不能代替最终版面。", group="layout")
    for source in sources:
        if source.document["format"] not in {"pdf", "docx"}:
            continue
        layouts = [r for r in job["layouts"] if r["after_sha256"] == source.document["sha256"]]
        complete = any(r.get("state", "completed") == "completed" and r.get("page_start", 1) == 1
                       and len(r["pages"]) >= r["after_pages"] and all(p.get("rendered", True) and p["human_checked"] for p in r["pages"]) for r in layouts)
        out.add("layout_record", "pass" if complete else "unchecked" if profile["require_layout"] else "manual",
                source.document["filename"] + "：最终文件排版核验", "已有覆盖全稿且绑定当前修改副本哈希的逐页记录。" if complete else
                "尚无绑定当前正文哈希的全稿逐页记录。修改后的排版副本需作为同名修订导入正文，旧版或局部页记录不能代替本版全稿。", group="layout")
    out.add("author_final", "manual", "作者确认内容与提交材料", "核对作者名单与顺序、声明、数据和图像使用权限，以及主张的证据边界；按实际适用要求记录决定。此工具不执行投稿。", group="author")
    return {"schema_version": 1, "checker_version": VERSION, "profile": profile, "profile_sha256": fingerprint(profile),
            "source_manifest": [{"filename": d["filename"], "sha256": d["sha256"], "size_bytes": d["size_bytes"], "role": profile["files"][d["filename"]]} for d in chosen],
            "metrics": metrics, "items": out.items, "counts": {s: out.counts[s] for s in STATUSES},
            "item_count": out.total, "omitted_items": max(0, out.total - len(out.items)), "model_calls": 0,
            "scope": "本地规则检查及显式人工记录；按所选文件和规则快照评估。没有联网验证期刊要求、来源真实性或科学有效性，不代表投稿系统验收。"}
