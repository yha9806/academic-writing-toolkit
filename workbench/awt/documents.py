"""Local document extraction and rendered-copy comparison, with stable locators."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import zipfile
from contextlib import closing
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_FILE_BYTES = 80_000_000
MAX_TOTAL_BYTES = 160_000_000
MAX_FILES = 20
MAX_PAGES = 1000
MAX_TEXT_CHARS = 12_000_000
MAX_BLOCK_CHARS = 1200
MAX_LAYOUT_PAGES = 60
MAX_BLOCKS = 100_000
PDF_LOCK = threading.RLock()  # PDFium is not thread-safe, even across documents.
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}
ROLES = {
    "abstract": r"abstract|摘要",
    "methods": r"method(?:s|ology)?|materials and methods|方法|材料与方法|研究设计",
    "results": r"results?|findings|结果|实验结果",
    "discussion": r"discussion|conclusions?|讨论|结论",
    "introduction": r"introduction|引言|绪论",
    "references": r"references|bibliography|参考文献",
}


class DocumentError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section_role(text: str) -> str:
    value = re.sub(r"[_\-]", " ", text.lower())
    for role, pattern in ROLES.items():
        if re.search(r"(?<![a-z])(?:" + pattern + r")(?![a-z])", value):
            return role
    return "other"


def heading_level(text: str):
    """Conservative structural hints; unknown titles remain manually classifiable."""
    value = text.strip()
    markdown = re.match(r"^(#{1,6})\s+", value)
    if markdown:
        return len(markdown[1])
    if re.match(r"^(?:chapter\s+\w+\b|第[零一二三四五六七八九十百\d]+章)", value, re.I):
        return 1
    numbered = re.match(r"^(\d+(?:\.\d+){0,4})[.\s、]\s*\S", value)
    if numbered and len(value) < 100 and not re.search(r"[。!?！？]", value):
        return numbered[1].count(".") + 1
    return 1 if len(value) < 85 and section_role(value) != "other" and not re.search(r"[。.?!]", value) else None


def _pdf_groups(fragments):
    """Join adjacent lines within one column, without altering their characters."""
    pending = []
    def merged():
        text, spans = "", []
        for fragment in pending:
            if text:
                text += "\n"
            start = len(text)
            text += fragment["text"]
            spans.append({"start": start, "end": len(text), "locator": fragment["locator"], "bounds": fragment["bounds"]})
        first = pending[0]
        bounds = [min(f["bounds"][0] for f in pending), min(f["bounds"][1] for f in pending),
                  max(f["bounds"][2] for f in pending), max(f["bounds"][3] for f in pending)]
        return {**first, "text": text, "bounds": bounds, "source_spans": spans,
                "locator": first["locator"] + (f" 至区域 {pending[-1]['region']}" if len(pending) > 1 else "")}
    for fragment in fragments:
        combine = False
        if pending and fragment["kind"] == "paragraph" and not fragment["heading"]:
            last = pending[-1]
            left, bottom, right, top = last["bounds"]
            nx, ny, nr, nt = fragment["bounds"]
            height = max(1, top - bottom)
            combine = (last["kind"] == "paragraph" and not last["heading"]
                       and abs(nx - left) <= 8 and -1 <= bottom - nt <= height * 1.7
                       and ny < bottom and sum(len(f["text"]) + 1 for f in pending) + len(fragment["text"]) <= MAX_BLOCK_CHARS)
        if pending and not combine:
            yield merged()
            pending = []
        pending.append(fragment)
    if pending:
        yield merged()


def decode_upload(payload: dict) -> tuple[str, bytes]:
    if not isinstance(payload, dict) or not isinstance(payload.get("filename"), str):
        raise DocumentError("材料需要文件名和 base64 内容")
    name = payload["filename"]
    if not name or len(name) > 200 or re.search(r"[\\/\x00-\x1f]", name):
        raise DocumentError("文件名无效；请使用不含路径的文件名")
    value = payload.get("content_base64")
    if not isinstance(value, str) or len(value) > (MAX_FILE_BYTES * 4 // 3 + 8):
        raise DocumentError("单份材料上限为 80 MB；大文件请使用分段上传")
    try:
        data = base64.b64decode(value, validate=True)
    except ValueError:
        raise DocumentError("文件内容不是有效 base64") from None
    if not data or len(data) > MAX_FILE_BYTES:
        raise DocumentError("材料为空或超过 80 MB")
    return name, data


def _xml(data: bytes):
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise DocumentError("文档 XML 含有不支持的实体声明")
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise DocumentError("DOCX 的 XML 结构损坏") from None


def _docx_archive(data: bytes):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        entries = archive.infolist()
        if len(entries) > 10000 or sum(item.file_size for item in entries) > 240_000_000:
            raise DocumentError("DOCX 解压大小或文件数超过限制")
        if len({item.filename for item in entries}) != len(entries):
            raise DocumentError("DOCX 包含重复成员")
        if any("vbaproject" in item.filename.lower() or item.flag_bits & 1 for item in entries):
            raise DocumentError("不接受带宏或加密的 DOCX")
        if "word/document.xml" not in archive.namelist():
            raise DocumentError("不是有效的 DOCX 文档")
        return archive
    except (zipfile.BadZipFile, RuntimeError):
        raise DocumentError("无法读取 DOCX 容器") from None


def _paragraph_text(element) -> str:
    # Deleted revision text (w:delText) is not silently promoted to current prose.
    parts = []
    for child in element.iter():
        if child.tag == "{" + NS["w"] + "}t":
            parts.append(child.text or "")
        elif child.tag == "{" + NS["w"] + "}tab":
            parts.append("\t")
        elif child.tag in {"{" + NS["w"] + "}br", "{" + NS["w"] + "}cr"}:
            parts.append("\n")
    return "".join(parts)


def import_document(name: str, data: bytes) -> dict:
    suffix = Path(name).suffix.lower()
    document = {"id": "d" + digest(name.encode() + b"\0" + data)[:20],
                "filename": name, "sha256": digest(data), "size_bytes": len(data),
                "format": suffix[1:], "blocks": [], "assets": [], "warnings": [], "pages": []}
    current = {"section": Path(name).stem, "role": section_role(Path(name).stem), "path": [Path(name).stem]}
    extracted_chars = 0

    def add(text, locator, *, kind="paragraph", heading=False, page=None, bounds=None, level=None, source_spans=None):
        nonlocal extracted_chars
        if not text.strip():
            return
        extracted_chars += len(text)
        if extracted_chars > MAX_TEXT_CHARS or len(document["blocks"]) + (len(text) // MAX_BLOCK_CHARS + 1) > MAX_BLOCKS:
            raise DocumentError("文档提取内容超过限制；请拆分材料")
        if heading:
            level = level or heading_level(text) or 1
            title = re.sub(r"^\s*#{1,6}\s+", "", text.strip())[:180]
            path = current["path"][:level - 1] + [title]
            role = section_role(title)
            current.update(section=title, path=path, role=role if role != "other" or level == 1 else current["role"])
            kind = "heading"
        # Splitting is deterministic; offsets refer to the extracted source block.
        for start in range(0, len(text), MAX_BLOCK_CHARS):
            part = text[start:start + MAX_BLOCK_CHARS]
            identifier = document["id"] + ":b" + str(len(document["blocks"]) + 1)
            document["blocks"].append({"id": identifier, "document_id": document["id"],
                "locator": locator + (f"，字符 {start + 1}–{start + len(part)}" if len(text) > MAX_BLOCK_CHARS else ""),
                "text": part, "kind": kind, "section": current["section"], "role": current["role"],
                "page": page, "bounds": bounds, "offset": start,
                "chapter": current["path"][0], "section_path": list(current["path"]),
                "source_spans": [{**span, "start": max(span["start"], start) - start,
                                  "end": min(span["end"], start + len(part)) - start}
                                 for span in source_spans or [] if span["end"] > start and span["start"] < start + len(part)]})

    if suffix in {".txt", ".md", ".tex", ".csv", ".json", ".bib"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise DocumentError("文本材料需要 UTF-8 编码") from None
        if "\0" in text or len(text) > MAX_TEXT_CHARS:
            raise DocumentError("文本包含二进制内容或超过提取长度限制")
        for number, line in enumerate(text.splitlines(), 1):
            title = re.match(r"^\s*#{1,6}\s+(.+)|^\s*\\(?:sub)*section\*?\{([^}]+)\}", line)
            level = heading_level(line)
            is_heading = bool(title) or level is not None
            kind = "table" if suffix == ".csv" or line.lstrip().startswith("|") else "paragraph"
            if re.match(r"^\s*(?:Figure|Fig\.?|Table|图|表)\s*[\d一二三四五六七八九十]", line, re.I):
                kind = "caption"
            add(line, f"第 {number} 行", kind=kind, heading=is_heading, level=level)
        if suffix == ".tex":
            document["warnings"].append("LaTeX 只索引所选文件；未展开的 include、宏和外部图片尚未检查。")
    elif suffix == ".docx":
        with _docx_archive(data) as archive:
            root = _xml(archive.read("word/document.xml"))
            body = root.find("w:body", NS)
            if body is None:
                raise DocumentError("DOCX 缺少正文")
            paragraph = table = 0
            relationships = {}
            if "word/_rels/document.xml.rels" in archive.namelist():
                for rel in _xml(archive.read("word/_rels/document.xml.rels")):
                    if rel.get("TargetMode") != "External":
                        target = rel.get("Target", "")
                        if not target.startswith("/") and ".." not in target.split("/"):
                            relationships[rel.get("Id")] = "word/" + target
            def capture_objects(paragraph_node, locator):
                for drawing in paragraph_node.findall(".//a:blip", NS):
                    target = relationships.get(drawing.get("{" + NS["r"] + "}embed"))
                    if target and target in archive.namelist():
                        image_data = archive.read(target)
                        mime = "image/png" if image_data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if image_data.startswith(b"\xff\xd8\xff") else None
                        asset_id = document["id"] + ":image" + str(len(document["assets"]) + 1)
                        document["assets"].append({"id": asset_id, "kind": "image", "locator": locator + f"，嵌入图 {len(document['assets']) + 1}",
                            "page": None, "mime_type": mime, "text": _paragraph_text(paragraph_node)[:500], "sha256": digest(image_data),
                            "data_base64": base64.b64encode(image_data).decode() if mime else None})
                for reference in paragraph_node.findall(".//c:chart", NS):
                    target = relationships.get(reference.get("{" + NS["r"] + "}id"))
                    if target and target in archive.namelist():
                        chart = _xml(archive.read(target))
                        series = []
                        for item in chart.findall(".//c:ser", NS):
                            series.append({node.tag.split("}")[-1]: [value.text or "" for value in node.findall(".//c:v", NS)]
                                           for node in item if node.tag.split("}")[-1] in {"tx", "cat", "val", "xVal", "yVal", "bubbleSize"}})
                        add(json.dumps(series, ensure_ascii=False), locator + "，图表缓存 " + Path(target).name, kind="chart_data")
            for child in body:
                if child.tag == "{" + NS["w"] + "}tbl":
                    table += 1
                    for row_number, row in enumerate(child.findall("w:tr", NS), 1):
                        for cell_number, cell in enumerate(row.findall("w:tc", NS), 1):
                            text = "\n".join(_paragraph_text(p) for p in cell.findall("w:p", NS))
                            add(text, f"表 {table}，第 {row_number} 行第 {cell_number} 格", kind="table")
                            for p in cell.findall("w:p", NS):
                                capture_objects(p, f"表 {table}，第 {row_number} 行第 {cell_number} 格")
                else:
                    paragraphs = [child] if child.tag == "{" + NS["w"] + "}p" else child.findall(".//w:p", NS)
                    for p in paragraphs:
                        paragraph += 1
                        text = _paragraph_text(p)
                        style = p.find("w:pPr/w:pStyle", NS)
                        style_name = style.get("{" + NS["w"] + "}val", "") if style is not None else ""
                        heading = bool(re.search(r"heading|标题", style_name, re.I))
                        kind = "caption" if re.search(r"caption|题注", style_name, re.I) else "paragraph"
                        style_level = re.search(r"(\d+)$", style_name)
                        add(text, f"段落 {paragraph}", kind=kind, heading=heading,
                            level=int(style_level[1]) if style_level else None)
                        capture_objects(p, f"段落 {paragraph}")
            if root.findall(".//w:ins", NS) or root.findall(".//w:del", NS):
                document["warnings"].append("含修订记录：提取当前可见插入文本并排除删除文本；请在 Word 中确认修订视图。")
            document["warnings"].append("DOCX 使用稳定段落和表格定位；页码须以排版后的 PDF 为准。页眉页脚、批注、公式、浮动对象和合并单元格布局未完整提取。图表缓存不是独立核验的数据。")
    elif suffix == ".pdf":
        _extract_pdf(data, document, add)
    else:
        raise DocumentError("支持 PDF、DOCX、TXT、MD、TEX、CSV、JSON 和 BIB")
    if sum(len(block["text"]) for block in document["blocks"]) > MAX_TEXT_CHARS or len(document["blocks"]) > MAX_BLOCKS:
        raise DocumentError("文档提取内容超过限制；请拆分材料")
    if not document["blocks"]:
        document["warnings"].append("没有可提取的正文；文字覆盖为零。扫描件需要人工转写/OCR，或单独选择页面做视觉检查。")
    return document


def _extract_pdf(data, document, add):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise DocumentError('PDF 导入需要可选依赖：python -m pip install ".[documents]"') from None
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > MAX_PAGES:
                raise DocumentError("PDF 已加密或超过 1000 页")
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                document["pages"].append({"page": number, "width": float(page.mediabox.width), "height": float(page.mediabox.height), "text_chars": len(text), "geometry_available": False})
                add(text, f"第 {number} 页（页面文本）", page=number)
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("无法提取 PDF；请检查文件是否损坏或加密") from None
        document["warnings"].append("当前仅使用 pypdf 提取页面文字；安装 documents 扩展后可获得区域定位和页面预览。")
    else:
        with PDF_LOCK:
            try:
                with pdfium.PdfDocument(data) as pdf:
                    if len(pdf) > MAX_PAGES:
                        raise DocumentError("PDF 超过 1000 页；请拆分材料")
                    for number in range(len(pdf)):
                        with closing(pdf[number]) as page, closing(page.get_textpage()) as textpage:
                            width, height = page.get_size()
                            text = textpage.get_text_bounded()
                            count = textpage.count_rects()
                            if count > 5000:
                                raise DocumentError("PDF 单页文字区域过多；请提供简化副本")
                            document["pages"].append({"page": number + 1, "width": width, "height": height, "text_chars": len(text), "geometry_available": True})
                            fragments = []
                            for index in range(count):
                                rect = list(textpage.get_rect(index))
                                fragment = textpage.get_text_bounded(*rect).replace("\r\n", "\n")
                                level = heading_level(fragment)
                                kind = "caption" if re.match(r"^\s*(?:Figure|Fig\.?|Table|图|表)\s*\d", fragment, re.I) else "paragraph"
                                if fragment.strip():
                                    fragments.append({"text": fragment, "locator": f"第 {number + 1} 页，文字区域 {index + 1}",
                                        "region": index + 1, "bounds": rect, "heading": level is not None, "level": level, "kind": kind})
                            for group in _pdf_groups(fragments):
                                add(group["text"], group["locator"], page=number + 1, bounds=group["bounds"],
                                    heading=group["heading"], level=group["level"], kind=group["kind"], source_spans=group["source_spans"])
            except DocumentError:
                raise
            except Exception:
                raise DocumentError("无法提取 PDF；请检查文件是否损坏、加密或字体异常") from None
    for page in document["pages"]:
        document["assets"].append({"id": document["id"] + f":page{page['page']}", "kind": "page", "page": page["page"],
            "locator": f"第 {page['page']} 页图像", "mime_type": "image/png", "text": "页面图形与排版；仅文字提取不能确认图像内容"})
        if not page["text_chars"]:
            document["warnings"].append(f"第 {page['page']} 页无可提取文字，文字内容尚未检查。")
    document["warnings"].append("PDF 文字区域不等于语义段落；多栏顺序、表格结构、公式与图形须结合页面预览核对。")


def render_pdf_page(data: bytes, number: int) -> bytes:
    try:
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError:
        raise DocumentError('页面预览需要：python -m pip install ".[documents]"') from None
    with PDF_LOCK:
        try:
            with pdfium.PdfDocument(data) as pdf:
                if type(number) is not int or not 1 <= number <= len(pdf):
                    raise DocumentError("页码超出范围")
                with closing(pdf[number - 1]) as page:
                    width, height = page.get_size()
                    if min(width, height) <= 0:
                        raise DocumentError("PDF 页面尺寸无效")
                    with closing(page.render(scale=min(1.5, 1600 / max(width, height)))) as bitmap:
                        image = bitmap.to_pil().convert("RGB")
                        output = io.BytesIO()
                        image.save(output, format="PNG")
                        return output.getvalue()
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("PDF 页面渲染失败") from None


def pdf_page_info(data: bytes, number=None):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise DocumentError('排版核验需要：python -m pip install ".[documents]"') from None
    with PDF_LOCK:
        try:
            with pdfium.PdfDocument(data) as pdf:
                if not 1 <= len(pdf) <= MAX_PAGES:
                    raise DocumentError("排版 PDF 需要 1–1000 页")
                if number is None:
                    return {"page_count": len(pdf)}
                if type(number) is not int or not 1 <= number <= len(pdf):
                    raise DocumentError("排版页码无效")
                with closing(pdf[number - 1]) as page, closing(page.get_textpage()) as textpage:
                    width, height = page.get_size()
                    count = textpage.count_rects()
                    if count > 5000:
                        raise DocumentError("单页文字区域过多")
                    outside = [list(textpage.get_rect(i)) for i in range(count)
                        if (textpage.get_rect(i)[0] < -1 or textpage.get_rect(i)[1] < -1 or
                            textpage.get_rect(i)[2] > width + 1 or textpage.get_rect(i)[3] > height + 1)]
                    return {"width": width, "height": height, "text_outside_page": outside}
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("无法读取排版 PDF 页面") from None


def compare_pdf_page(before, after, number, before_pages, after_pages):
    from PIL import Image, ImageChops
    images = {}
    for side, data, count in (("before", before, before_pages), ("after", after, after_pages)):
        if number <= count:
            images[side] = render_pdf_page(data, number)
    blank, outside = False, []
    if "after" in images:
        with Image.open(io.BytesIO(images["after"])) as image:
            blank = ImageChops.difference(image.convert("RGB"), Image.new("RGB", image.size, "white")).getbbox() is None
        outside = pdf_page_info(after, number)["text_outside_page"]
    return {"page": number, "rendered": True, "changed": images.get("before") != images.get("after"),
        "before_available": "before" in images, "after_available": "after" in images, "after_blank": blank,
        "text_outside_page": outside, "human_checked": False,
        "image_hashes": {side: digest(data) for side, data in images.items()}}, images


def as_pdf(name: str, data: bytes) -> bytes:
    if Path(name).suffix.lower() == ".pdf":
        return data
    if Path(name).suffix.lower() != ".docx":
        raise DocumentError("排版对照需要 PDF 或 DOCX")
    with _docx_archive(data):
        pass
    command = os.environ.get("AWT_LIBREOFFICE") or shutil.which("soffice")
    if not command:
        raise DocumentError("DOCX 排版对照需要本地 LibreOffice；也可在 Word 中导出 PDF 后上传")
    with tempfile.TemporaryDirectory(prefix="awt-layout-") as directory:
        root = Path(directory)
        source = root / "selected.docx"
        source.write_bytes(data)
        try:
            result = subprocess.run([command, "-env:UserInstallation=" + (root / "profile").as_uri(),
                "--headless", "--safe-mode", "--convert-to", "pdf", "--outdir", str(root), str(source)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise DocumentError("LibreOffice 排版失败或超时；请上传手动导出的 PDF") from None
        target = root / "selected.pdf"
        if result.returncode or not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
            raise DocumentError("LibreOffice 未生成有效 PDF；请上传手动导出的 PDF")
        return target.read_bytes()


def compare_layout(before_name: str, before: bytes, after_name: str, after: bytes) -> tuple[dict, dict[str, bytes]]:
    """Legacy in-memory helper. Workbench uses resumable LayoutManager instead."""
    before_pdf, after_pdf = as_pdf(before_name, before), as_pdf(after_name, after)
    left, right = import_document("before.pdf", before_pdf), import_document("after.pdf", after_pdf)
    if max(len(left["pages"]), len(right["pages"])) > MAX_LAYOUT_PAGES:
        raise DocumentError("旧版内存排版接口限 60 页；请使用 Workbench 的逐页排版任务处理长文档")
    from PIL import Image, ImageChops
    previews, rows = {}, []
    for number in range(1, max(len(left["pages"]), len(right["pages"])) + 1):
        image_data = []
        for side, pdf, document in (("before", before_pdf, left), ("after", after_pdf, right)):
            value = render_pdf_page(pdf, number) if number <= len(document["pages"]) else None
            if value:
                previews[f"{side}-{number}.png"] = value
            image_data.append(value)
        changed = image_data[0] != image_data[1]
        blank = False
        if image_data[1]:
            with Image.open(io.BytesIO(image_data[1])) as image:
                blank = ImageChops.difference(image.convert("RGB"), Image.new("RGB", image.size, "white")).getbbox() is None
        outside = []
        if number <= len(right["pages"]):
            page = right["pages"][number - 1]
            outside = [block["id"] for block in right["blocks"] if block["page"] == number and block["bounds"] and
                (block["bounds"][0] < -1 or block["bounds"][1] < -1 or block["bounds"][2] > page["width"] + 1 or block["bounds"][3] > page["height"] + 1)]
        rows.append({"page": number, "changed": changed, "before_available": bool(image_data[0]), "after_available": bool(image_data[1]),
                     "after_blank": blank, "text_outside_page": outside, "human_checked": False})
    return {"before_filename": before_name, "after_filename": after_name, "before_sha256": digest(before), "after_sha256": digest(after),
        "before_render_sha256": digest(before_pdf), "after_render_sha256": digest(after_pdf),
        "before_pages": len(left["pages"]), "after_pages": len(right["pages"]), "pages": rows,
        "status": "awaiting_human_review", "scope": "页面像素变化、页数、空白页与文字越界提示；逐页人工检查图表截断、重叠、字体和分页。DOCX 使用 LibreOffice 渲染，可能不同于 Word。",
        "source_unchanged": True}, previews
