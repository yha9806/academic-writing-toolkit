#!/usr/bin/env python3
"""Render deterministic v0.5.0 plugin listing screenshots with Pillow."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
HEIGHT = 1000

NAVY = "#0B132B"
INK = "#111A33"
MUTED = "#3F4C65"
BG = "#F5F7FB"
PANEL = "#FFFFFF"
BORDER = "#D7DFEC"
BLUE = "#246BFD"
CYAN = "#00A8C6"
GREEN = "#0B735F"
GREEN_BG = "#E8F7F2"
AMBER = "#934600"
AMBER_BG = "#FFF0CF"
RED = "#D92D45"
RED_BG = "#FDECEF"
VIOLET = "#7657D5"
SLATE_BG = "#EEF2F8"


def font_candidates(bold: bool = False, semibold: bool = False) -> list[Path]:
    windows = Path("C:/Windows/Fonts")
    linux = Path("/usr/share/fonts/truetype/dejavu")
    if bold:
        names = [
            windows / "segoeuib.ttf",
            windows / "arialbd.ttf",
            linux / "DejaVuSans-Bold.ttf",
        ]
    elif semibold:
        names = [
            windows / "seguisb.ttf",
            windows / "segoeuisb.ttf",
            linux / "DejaVuSans-Bold.ttf",
        ]
    else:
        names = [
            windows / "segoeui.ttf",
            windows / "arial.ttf",
            linux / "DejaVuSans.ttf",
        ]
    return names


def load_font(size: int, *, bold: bool = False, semibold: bool = False) -> ImageFont.FreeTypeFont:
    for path in font_candidates(bold=bold, semibold=semibold):
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


FONTS = {
    "eyebrow": load_font(20, bold=True),
    "title": load_font(52, bold=True),
    "subtitle": load_font(25),
    "section": load_font(30, bold=True),
    "card_title": load_font(24, bold=True),
    "body": load_font(22),
    "body_semibold": load_font(22, semibold=True),
    "small": load_font(18, semibold=True),
    "small_bold": load_font(18, bold=True),
    "micro": load_font(15, semibold=True),
}


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and text_width(draw, candidate, font) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: str,
    max_width: int,
    line_gap: int = 8,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = wrap_text(draw, text, font, max_width)
    if max_lines is not None:
        lines = lines[:max_lines]
    line_height = draw.textbbox((0, 0), "Ag", font=font)[3]
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height + line_gap
    return y


def rounded_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str = PANEL,
    outline: str = BORDER,
    radius: int = 22,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    fill: str,
    text_fill: str,
    font: ImageFont.ImageFont = FONTS["small_bold"],
    pad_x: int = 16,
    pad_y: int = 9,
) -> tuple[int, int, int, int]:
    x, y = xy
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0] + 2 * pad_x
    height = box[3] - box[1] + 2 * pad_y
    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=height // 2,
        fill=fill,
    )
    draw.text((x + pad_x, y + pad_y - 2), text, font=font, fill=text_fill)
    return (x, y, x + width, y + height)


def header(
    draw: ImageDraw.ImageDraw,
    *,
    eyebrow: str,
    title: str,
    subtitle: str,
) -> None:
    draw.rectangle((0, 0, WIDTH, 196), fill=NAVY)
    draw.text((52, 32), eyebrow.upper(), font=FONTS["eyebrow"], fill="#8ED9FF")
    draw.text((52, 66), title, font=FONTS["title"], fill="#FFFFFF")
    draw.text((54, 137), subtitle, font=FONTS["subtitle"], fill="#CED8EA")
    pill(
        draw,
        (1370, 34),
        "v0.5.0",
        fill="#16305C",
        text_fill="#DDF4FF",
    )


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    fill: str = "#A5B2C7",
    width: int = 4,
) -> None:
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2 - 12, y2), fill=fill, width=width)
    draw.polygon(
        [(x2 - 12, y2 - 8), (x2, y2), (x2 - 12, y2 + 8)],
        fill=fill,
    )


def research_spine_image() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(
        draw,
        eyebrow="Academic Writing Toolkit",
        title="Research spine, before another rewrite",
        subtitle="Lock the project truth, then test every upward claim against its evidence licence.",
    )

    pill(draw, (52, 222), "CANONICAL  manuscript-v7", fill="#E8F0FF", text_fill=BLUE)
    pill(draw, (360, 222), "INTENT  INT-01", fill="#E8F7F2", text_fill=GREEN)
    pill(draw, (550, 222), "AUTHOR-APPROVED", fill="#E8F7F2", text_fill=GREEN)
    pill(draw, (795, 222), "NO PROSE CHANGED", fill=SLATE_BG, text_fill=MUTED)

    labels = [
        ("GAP", "GAP-01", "Traceability is missing", BLUE),
        ("DATA", "DAT-01", "40 edit episodes", CYAN),
        ("RESULT", "RES-01", "9/40 vs 18/40", GREEN),
        ("CLAIM", "CLM-01", "Drift was reduced", AMBER),
        ("CONTRIBUTION", "CON-01", "Provenance checklist", VIOLET),
        ("INNOVATION", "NOV-01", "Compared, bounded", RED),
    ]
    card_y = 314
    card_w = 226
    card_h = 150
    gap = 28
    x = 52
    for index, (kind, object_id, statement, accent) in enumerate(labels):
        rounded_panel(draw, (x, card_y, x + card_w, card_y + card_h))
        draw.rounded_rectangle(
            (x, card_y, x + 9, card_y + card_h),
            radius=5,
            fill=accent,
        )
        draw.text((x + 25, card_y + 21), kind, font=FONTS["micro"], fill=accent)
        draw.text(
            (x + 25, card_y + 51),
            object_id,
            font=FONTS["card_title"],
            fill=INK,
        )
        draw_wrapped(
            draw,
            (x + 25, card_y + 91),
            statement,
            font=FONTS["small"],
            fill=MUTED,
            max_width=card_w - 46,
            line_gap=3,
            max_lines=2,
        )
        if index < len(labels) - 1:
            draw_arrow(
                draw,
                (x + card_w + 5, card_y + card_h // 2),
                (x + card_w + gap - 5, card_y + card_h // 2),
            )
        x += card_w + gap

    rounded_panel(draw, (52, 510, 772, 860), fill=PANEL)
    draw.text((82, 540), "Evidence licence", font=FONTS["section"], fill=INK)
    pill(draw, (82, 596), "LICENSED", fill=GREEN_BG, text_fill=GREEN)
    draw_wrapped(
        draw,
        (82, 650),
        "Within this 40-episode evaluation, the checklist reduced untraceable revisions from 18 to 9.",
        font=FONTS["body_semibold"],
        fill=INK,
        max_width=630,
        line_gap=10,
        max_lines=3,
    )
    draw.text(
        (82, 780),
        "Scope: one team · one workflow · uncertainty not reported",
        font=FONTS["small"],
        fill=MUTED,
    )

    rounded_panel(draw, (812, 510, 1548, 860), fill=PANEL)
    draw.text((842, 540), "Headline boundary", font=FONTS["section"], fill=INK)
    pill(draw, (842, 596), "UNLICENSED", fill=RED_BG, text_fill=RED)
    draw_wrapped(
        draw,
        (842, 650),
        "“The checklist eliminates claim drift universally.”",
        font=FONTS["body_semibold"],
        fill=INK,
        max_width=640,
        line_gap=10,
        max_lines=2,
    )
    draw.text(
        (842, 755),
        "Missing: uncertainty · transfer evidence · external validation",
        font=FONTS["small"],
        fill=MUTED,
    )
    pill(
        draw,
        (842, 802),
        "NEXT  argument-governance",
        fill=AMBER_BG,
        text_fill=AMBER,
    )

    draw.text(
        (52, 914),
        "One canonical intent  ·  one primary route  ·  every counter-signal preserved",
        font=FONTS["body_semibold"],
        fill=INK,
    )
    return image


def attempt_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    number: str,
    decision: str,
    note: str,
    *,
    accent: str,
    accent_bg: str,
) -> None:
    rounded_panel(draw, (x, 300, x + 330, 454), fill=PANEL)
    pill(draw, (x + 24, 322), f"ATTEMPT {number}", fill=accent_bg, text_fill=accent)
    draw.text((x + 24, 378), decision, font=FONTS["card_title"], fill=INK)
    draw.text((x + 24, 418), note, font=FONTS["small"], fill=MUTED)


def controlled_revision_image() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(
        draw,
        eyebrow="Academic Writing Toolkit",
        title="Three revisions, then diagnose",
        subtitle="A failed cycle becomes a structured decision—not a fourth uncontrolled patch.",
    )

    pill(draw, (52, 222), "ISSUE  ri-abstract-scope", fill="#E8F0FF", text_fill=BLUE)
    pill(draw, (340, 222), "APPROVED VERSION  v7", fill=GREEN_BG, text_fill=GREEN)
    pill(draw, (635, 222), "ACCEPTANCE  one English benchmark", fill=SLATE_BG, text_fill=MUTED)

    attempt_card(
        draw,
        52,
        "1",
        "REVISE",
        "Universal scope remained",
        accent=AMBER,
        accent_bg=AMBER_BG,
    )
    draw_arrow(draw, (390, 376), (438, 376))
    attempt_card(
        draw,
        446,
        "2",
        "ROLLBACK",
        "Approved boundary was lost",
        accent=RED,
        accent_bg=RED_BG,
    )
    draw_arrow(draw, (784, 376), (832, 376))
    attempt_card(
        draw,
        840,
        "3",
        "REVISE",
        "No cross-lingual evidence",
        accent=AMBER,
        accent_bg=AMBER_BG,
    )
    draw_arrow(draw, (1178, 376), (1226, 376), fill=RED)
    rounded_panel(
        draw,
        (1234, 300, 1548, 454),
        fill=RED_BG,
        outline="#F3A8B4",
    )
    pill(draw, (1258, 322), "STOP", fill=RED, text_fill="#FFFFFF")
    draw.text((1258, 378), "NO ATTEMPT 4", font=FONTS["card_title"], fill=RED)
    draw.text((1258, 418), "Diagnose before editing", font=FONTS["small"], fill=INK)

    rounded_panel(draw, (52, 502, 750, 836), fill=PANEL)
    draw.text((82, 532), "Revision Escalation Check", font=FONTS["section"], fill=INK)
    rows: Sequence[tuple[str, str, str]] = [
        ("CATEGORY", "Evidence gap", RED),
        ("SCOPE", "Full reframing", AMBER),
        ("MISSING", "Cross-lingual evidence", MUTED),
        ("SAFE NEXT", "Narrow claim or collect evidence", GREEN),
    ]
    y = 595
    for label, value, color in rows:
        draw.text((82, y), label, font=FONTS["micro"], fill=MUTED)
        draw.text((230, y - 4), value, font=FONTS["body_semibold"], fill=color)
        y += 58

    rounded_panel(draw, (790, 502, 1548, 836), fill=PANEL)
    draw.text((820, 532), "Author decision gate", font=FONTS["section"], fill=INK)
    draw.text(
        (820, 585),
        "Choose one bounded route before work resumes.",
        font=FONTS["body"],
        fill=MUTED,
    )
    pill(draw, (820, 642), "A  NARROW THE CLAIM", fill=GREEN_BG, text_fill=GREEN)
    pill(draw, (820, 700), "B  COLLECT EVIDENCE", fill="#E8F0FF", text_fill=BLUE)
    pill(draw, (820, 758), "C  APPROVE REFRAME", fill=AMBER_BG, text_fill=AMBER)
    pill(
        draw,
        (1215, 758),
        "PENDING",
        fill="#334E7D",
        text_fill="#FFFFFF",
    )

    rounded_panel(draw, (52, 870, 1548, 958), fill=NAVY, outline=NAVY, radius=18)
    draw.text((80, 893), "SESSION SUMMARY", font=FONTS["micro"], fill="#8ED9FF")
    draw.text(
        (265, 887),
        "inspected 3 contracts  ·  changed nothing  ·  preserved v7  ·  next: author decision",
        font=FONTS["body_semibold"],
        fill="#FFFFFF",
    )
    return image


def save_images(out_dir: Path) -> Iterable[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        (out_dir / "screenshot-workflow.png", research_spine_image()),
        (out_dir / "screenshot-progress.png", controlled_revision_image()),
    ]
    for path, image in outputs:
        image.save(path, format="PNG", optimize=True)
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the Academic Writing Toolkit plugin screenshots."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("plugins/academic-writing-toolkit/assets"),
        help="output directory relative to the current working directory",
    )
    args = parser.parse_args()
    for path in save_images(args.out_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
