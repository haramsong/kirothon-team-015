from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_CONNECTOR_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
SCREENSHOTS = Path(__file__).resolve().parent / "screenshots"
OUTPUT = ROOT / "PRESENTATION_SOURCE.pptx"

SLIDE_W = Inches(13.333333)
SLIDE_H = Inches(7.5)
FONT = "Apple SD Gothic Neo"

STONE_950 = RGBColor(28, 25, 23)
STONE_800 = RGBColor(41, 37, 36)
STONE_700 = RGBColor(68, 64, 60)
STONE_600 = RGBColor(87, 83, 78)
STONE_500 = RGBColor(120, 113, 108)
STONE_300 = RGBColor(214, 211, 209)
STONE_200 = RGBColor(231, 229, 228)
STONE_100 = RGBColor(245, 245, 244)
STONE_50 = RGBColor(250, 250, 249)
WHITE = RGBColor(255, 255, 255)
EMERALD_900 = RGBColor(6, 78, 59)
EMERALD_800 = RGBColor(6, 95, 70)
EMERALD_700 = RGBColor(4, 120, 87)
EMERALD_600 = RGBColor(5, 150, 105)
EMERALD_500 = RGBColor(16, 185, 129)
EMERALD_100 = RGBColor(209, 250, 229)
EMERALD_50 = RGBColor(236, 253, 245)
AMBER_800 = RGBColor(146, 64, 14)
AMBER_500 = RGBColor(245, 158, 11)
AMBER_100 = RGBColor(254, 243, 199)
RED_700 = RGBColor(185, 28, 28)
RED_100 = RGBColor(254, 226, 226)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
blank = prs.slide_layouts[6]


def set_background(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 20,
    color: RGBColor = STONE_950,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
    valign=MSO_ANCHOR.TOP,
    margin: float = 0,
    font: str = FONT,
    line_spacing: float | None = None,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    if line_spacing:
        paragraph.line_spacing = line_spacing
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_rich_text(slide, parts, x, y, w, h, *, size=20, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    p = frame.paragraphs[0]
    p.alignment = align
    for text, color, bold in parts:
        r = p.add_run()
        r.text = text
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.bold = bold
    return box


def add_round_rect(slide, x, y, w, h, *, fill, line=None, radius=True):
    shape_type = MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE if radius else MSO_AUTO_SHAPE_TYPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line or fill
    shape.line.width = Pt(1)
    return shape


def add_card(slide, x, y, w, h, *, fill=WHITE, line=STONE_200):
    return add_round_rect(slide, x, y, w, h, fill=fill, line=line)


def add_label(slide, text, x, y, w, *, fill=EMERALD_100, color=EMERALD_800):
    add_round_rect(slide, x, y, w, 0.33, fill=fill, line=fill)
    add_text(slide, text, x, y + 0.005, w, 0.31, size=10.5, color=color, bold=True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)


def add_title(slide, eyebrow: str, title: str, subtitle: str | None = None, *, dark=False):
    fg = WHITE if dark else STONE_950
    muted = EMERALD_100 if dark else EMERALD_700
    add_text(slide, eyebrow, 0.65, 0.4, 7.8, 0.3, size=11, color=muted, bold=True)
    add_text(slide, title, 0.65, 0.78, 12.0, 0.72, size=28, color=fg, bold=True)
    if subtitle:
        add_text(slide, subtitle, 0.65, 1.48, 11.8, 0.45, size=14, color=STONE_300 if dark else STONE_600)


def add_footer(slide, number: int, seconds: int, source: str | None = None, *, dark=False):
    color = STONE_300 if dark else STONE_500
    if source:
        add_text(slide, source, 0.65, 7.16, 10.9, 0.18, size=7.8, color=color)
    add_text(slide, f"{number:02d}  ·  {seconds}초", 11.65, 7.08, 1.05, 0.25, size=8.5, color=color,
             align=PP_ALIGN.RIGHT)


def add_phone(slide, image_name: str, x: float, y: float, w: float, h: float, *, caption: str | None = None):
    # 화면을 실제 휴대폰처럼 보이게 하는 단순 프레임입니다.
    add_round_rect(slide, x - 0.055, y - 0.055, w + 0.11, h + 0.11, fill=STONE_950, line=STONE_950)
    path = SCREENSHOTS / image_name
    picture = slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w), height=Inches(h))
    if caption:
        add_round_rect(slide, x + 0.12, y + h - 0.46, w - 0.24, 0.33, fill=STONE_950, line=STONE_950)
        add_text(slide, caption, x + 0.12, y + h - 0.455, w - 0.24, 0.3, size=9, color=WHITE,
                 bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    return picture


def add_picture_cover(slide, image_name: str, x: float, y: float, w: float, h: float):
    """이미지를 상자에 꽉 채우고 넘치는 부분을 중앙 기준으로 자릅니다."""
    path = SCREENSHOTS / image_name
    picture = slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w), height=Inches(h))
    from PIL import Image
    with Image.open(path) as image:
        image_ratio = image.width / image.height
    box_ratio = w / h
    if image_ratio > box_ratio:
        visible = box_ratio / image_ratio
        picture.crop_left = (1 - visible) / 2
        picture.crop_right = (1 - visible) / 2
    else:
        visible = image_ratio / box_ratio
        picture.crop_top = (1 - visible) / 2
        picture.crop_bottom = (1 - visible) / 2
    return picture


def add_clickable_text(slide, text: str, url: str, x: float, y: float, w: float, h: float, *, color=EMERALD_700, size=10.5):
    box = add_text(slide, text, x, y, w, h, size=size, color=color, bold=True)
    run = box.text_frame.paragraphs[0].runs[0]
    run.hyperlink.address = url
    return box


def add_bullet(slide, title: str, body: str, x: float, y: float, w: float, *, accent=EMERALD_600):
    add_round_rect(slide, x, y + 0.04, 0.12, 0.12, fill=accent, line=accent)
    add_text(slide, title, x + 0.25, y, w - 0.25, 0.3, size=14, color=STONE_950, bold=True)
    add_text(slide, body, x + 0.25, y + 0.33, w - 0.25, 0.48, size=11, color=STONE_600)


def add_notes(slide, text: str):
    frame = slide.notes_slide.notes_text_frame
    frame.text = text
    for p in frame.paragraphs:
        for run in p.runs:
            run.font.name = FONT
            run.font.size = Pt(12)


# 1. 표지
slide = prs.slides.add_slide(blank)
set_background(slide, EMERALD_900)
add_label(slide, "KIROTHON 2026 · TEAM 015 깜자조와", 0.7, 0.55, 2.85, fill=EMERALD_800, color=EMERALD_100)
add_text(slide, "나만의\n냉장고", 0.72, 1.35, 5.2, 1.75, size=44, color=WHITE, bold=True)
add_text(slide, "재료를 넣는 순간부터\n요리해 빼는 순간까지", 0.75, 3.35, 5.1, 1.05, size=25, color=EMERALD_100, bold=True)
add_text(slide, "영수증·주문내역 인식  →  임박 재료 추천  →  요리 후 자동 차감", 0.75, 4.65, 5.25, 0.65,
         size=13, color=STONE_200)
add_round_rect(slide, 0.75, 5.65, 3.6, 0.62, fill=EMERALD_600, line=EMERALD_600)
add_text(slide, "정확한 재고가 다음 추천의 시작입니다", 0.75, 5.66, 3.6, 0.6, size=13.5, color=WHITE,
         bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
add_phone(slide, "03-inventory.png", 7.28, 0.86, 3.05, 4.82)
add_phone(slide, "05-deduction.png", 9.82, 1.63, 2.72, 4.29)
add_footer(slide, 1, 15, dark=True)
add_notes(slide, "[00:00–00:15]\n나만의 냉장고는 혼자 사는 직장인과 대학생을 위한 냉장고 재고 관리 서비스입니다. 영수증이나 주문내역을 찍으면 재고가 채워지고, 추천받은 메뉴를 요리하면 사용한 재료가 자동으로 빠집니다.")

# 2. 문제
slide = prs.slides.add_slide(blank)
set_background(slide, STONE_50)
add_title(slide, "PROBLEM", "냉장고 목록이 틀리면, 추천도 쓸 수 없습니다", "기존 앱이 줄인 것은 ‘넣는 일’이었습니다. ‘빼는 일’은 여전히 사용자 몫입니다.")
add_card(slide, 0.68, 2.12, 3.35, 3.48, fill=WHITE)
add_text(slide, "36.1%", 0.98, 2.47, 2.8, 0.8, size=40, color=EMERALD_700, bold=True)
add_text(slide, "2024년 전체 가구 중\n1인 가구 비중", 0.98, 3.3, 2.6, 0.9, size=17, color=STONE_800, bold=True)
add_text(slide, "804만 5천 가구", 0.98, 4.55, 2.7, 0.4, size=16, color=STONE_600)
for i, (num, title, body) in enumerate([
    ("01", "혼자 먹기엔 큰 판매 단위", "양파 한 망과 대파 한 단은\n한 끼로 다 쓰기 어렵습니다."),
    ("02", "온라인 장보기에는 종이 영수증이 없음", "스크린샷의 품목을 다시\n손으로 입력해야 합니다."),
    ("03", "먹은 재료를 직접 지우지 않음", "재고가 실제 냉장고와 달라져\n추천을 믿을 수 없게 됩니다."),
]):
    x = 4.35 + i * 2.78
    add_card(slide, x, 2.12, 2.48, 3.48, fill=WHITE)
    add_text(slide, num, x + 0.25, 2.4, 0.7, 0.4, size=13, color=EMERALD_700, bold=True)
    add_text(slide, title, x + 0.25, 2.95, 2.0, 0.9, size=16, color=STONE_950, bold=True)
    add_text(slide, body, x + 0.25, 4.15, 2.0, 0.85, size=11.5, color=STONE_600)
add_round_rect(slide, 4.35, 5.88, 8.03, 0.65, fill=AMBER_100, line=AMBER_100)
add_text(slide, "핵심 관찰  ·  등록보다 ‘사용 후 차감’이 재고 신뢰도를 결정합니다", 4.65, 5.97, 7.45, 0.42,
         size=15, color=AMBER_800, bold=True, valign=MSO_ANCHOR.MIDDLE)
add_footer(slide, 2, 30, "출처: 국가데이터처, 「2025 통계로 보는 1인가구」")
add_notes(slide, "[00:15–00:45]\n1인 가구는 양파 한 망이나 대파 한 단을 한 번에 쓰기 어렵습니다. 온라인 장보기에는 종이 영수증도 없습니다. 무엇보다 먹은 재료를 사용자가 직접 지우지 않으면 앱의 재고가 실제 냉장고와 달라집니다. 이 상태에서는 남은 재료 추천도 믿을 수 없습니다.")

# 3. 해결 흐름
slide = prs.slides.add_slide(blank)
set_background(slide, WHITE)
add_title(slide, "SOLUTION", "등록부터 차감까지 닫힌 흐름으로 연결했습니다", "정확한 재고가 유지되어야 다음 추천도 실제로 만들 수 있습니다.")
steps = [
    ("1", "장보기", "영수증·주문내역"),
    ("2", "등록", "확인 후 저장"),
    ("3", "추천", "임박 재료 우선"),
    ("4", "요리", "1인분 레시피"),
    ("5", "차감", "사용자 확인"),
]
for i, (num, title, body) in enumerate(steps):
    x = 0.72 + i * 2.48
    fill = EMERALD_900 if i == 4 else EMERALD_50
    tc = WHITE if i == 4 else EMERALD_900
    add_card(slide, x, 2.35, 2.05, 1.75, fill=fill, line=EMERALD_100 if i != 4 else EMERALD_900)
    add_text(slide, num, x + 0.18, 2.55, 0.35, 0.32, size=11, color=EMERALD_500 if i == 4 else EMERALD_700, bold=True)
    add_text(slide, title, x + 0.18, 2.95, 1.65, 0.4, size=19, color=tc, bold=True)
    add_text(slide, body, x + 0.18, 3.48, 1.65, 0.3, size=10.5, color=EMERALD_100 if i == 4 else STONE_600)
    if i < 4:
        add_text(slide, "→", x + 2.1, 2.91, 0.36, 0.4, size=19, color=STONE_300, bold=True,
                 align=PP_ALIGN.CENTER)
add_round_rect(slide, 1.08, 4.73, 11.15, 0.88, fill=STONE_950, line=STONE_950)
add_text(slide, "실제 냉장고와 맞는 목록", 1.32, 4.93, 2.75, 0.35, size=17, color=WHITE, bold=True)
add_text(slide, "→", 4.0, 4.9, 0.5, 0.35, size=17, color=EMERALD_500, bold=True, align=PP_ALIGN.CENTER)
add_text(slide, "더 정확한 다음 추천", 4.6, 4.93, 2.85, 0.35, size=17, color=WHITE, bold=True)
add_text(slide, "대표 차별점", 9.28, 4.93, 1.2, 0.35, size=10.5, color=EMERALD_100, bold=True)
add_text(slide, "요리 후 자동 차감", 10.15, 4.93, 1.72, 0.35, size=14, color=EMERALD_500, bold=True)
add_text(slide, "① 요리 후 차감   ② 주문내역 캡처 인식   ③ 3일 동안 대용량 재료 소진", 2.0, 6.13, 9.3, 0.4,
         size=16, color=STONE_700, bold=True, align=PP_ALIGN.CENTER)
add_footer(slide, 3, 25, "근거: .kiro/steering/product.md · README.md")
add_notes(slide, "[00:45–01:10]\n해결 방법은 기능을 따로 제공하는 것이 아니라 하나의 흐름으로 연결하는 것입니다. 등록한 재료로 메뉴를 추천하고, 요리가 끝나면 사용량을 확인한 뒤 재고를 줄입니다. 이 흐름이 다시 정확한 추천의 기반이 됩니다.")

# 4. 자동 차감
slide = prs.slides.add_slide(blank)
set_background(slide, STONE_50)
add_title(slide, "CORE DIFFERENTIATOR", "“요리했어요”를 누르면 재고가 줄어듭니다", "추천 수량을 그대로 믿지 않고, 사용자가 실제 사용량을 확인한 뒤 반영합니다.")
add_phone(slide, "04-recipe.png", 0.78, 2.02, 3.0, 4.73, caption="① 추천 레시피")
add_text(slide, "→", 3.95, 4.1, 0.55, 0.5, size=30, color=EMERALD_600, bold=True,
         align=PP_ALIGN.CENTER)
add_phone(slide, "05-deduction.png", 4.62, 2.02, 3.0, 4.73, caption="② 차감 전 확인")
add_card(slide, 8.0, 2.02, 4.6, 4.73, fill=WHITE)
add_label(slide, "대표 가치", 8.38, 2.4, 1.0)
add_rich_text(slide, [("양파 ", STONE_950, True), ("8개", STONE_950, True), ("  →  ", EMERALD_600, True), ("7개", EMERALD_600, True)],
              8.38, 3.0, 3.85, 0.65, size=29)
add_bullet(slide, "0.5개 단위 수정", "반 개를 쓴 실제 요리도 재고와 같은 단위로 처리", 8.42, 3.93, 3.7)
add_bullet(slide, "확인 후에만 반영", "추천은 추정값이므로 사용자가 고친 뒤 차감", 8.42, 4.78, 3.7)
add_bullet(slide, "중복 차감 방지", "DynamoDB 트랜잭션과 요청 ID로 한 번만 적용", 8.42, 5.63, 3.7)
add_footer(slide, 4, 45, "실제 구현 화면 · frontend/src/features/deduction/DeductionModal.tsx")
add_notes(slide, "[01:10–01:55]\n대표 차별점은 요리 후 자동 차감입니다. 추천 레시피에는 사용할 재료와 수량이 개수 단위로 들어 있습니다. 요리했어요를 누르면 양파 8개가 7개로 바뀌는 것처럼 차감 전후를 보여줍니다. 사용량은 0.5개 단위로 고칠 수 있고, 사용자가 확인해야만 재고에 반영됩니다. 같은 요청이 두 번 들어와도 요청 ID와 DynamoDB 트랜잭션으로 한 번만 차감합니다.")

# 5. 등록
slide = prs.slides.add_slide(blank)
set_background(slide, WHITE)
add_title(slide, "REGISTRATION", "종이 영수증도, 주문내역 캡처도 같은 버튼 하나로", "Bedrock이 품목명·개수·보관 위치·예상 소비기한을 추출하고, 사용자가 수정합니다.")
add_phone(slide, "01-registration-upload.png", 0.84, 2.02, 3.05, 4.81, caption="① 사진 선택")
add_text(slide, "+", 4.12, 4.0, 0.45, 0.55, size=28, color=STONE_300, bold=True, align=PP_ALIGN.CENTER)
add_phone(slide, "02-registration-result.png", 4.74, 2.02, 3.05, 4.81, caption="② 인식 결과 확인")
add_card(slide, 8.22, 2.02, 4.25, 4.81, fill=EMERALD_50, line=EMERALD_100)
add_text(slide, "입력은 간단하게", 8.62, 2.46, 3.45, 0.42, size=20, color=EMERALD_900, bold=True)
add_text(slide, "영수증 / 주문내역을\n구분하는 단계가 없습니다", 8.62, 3.05, 3.45, 0.85, size=18, color=STONE_950, bold=True)
add_bullet(slide, "모든 LLM 값 수정 가능", "수정·삭제·직접 추가 후 저장", 8.62, 4.2, 3.15)
add_bullet(slide, "단위를 ‘개’로 통일", "kg·g·L 표기를 0.5개 단위 재고로 변환", 8.62, 5.05, 3.15)
add_bullet(slide, "이미지는 브라우저에서 축소", "긴 변 1568px 이하 JPEG로 전처리", 8.62, 5.9, 3.15)
add_footer(slide, 5, 30, "실제 구현 화면 · Amazon Bedrock Claude Haiku 4.5")
add_notes(slide, "[01:55–02:25]\n마트 영수증뿐 아니라 온라인 주문내역 캡처도 같은 버튼으로 등록합니다. Bedrock이 품목명, 개수, 보관 위치와 예상 소비기한을 추출합니다. 결과는 추정값이므로 사용자가 수정하거나 삭제하고 품목을 추가한 뒤 저장합니다. 중량 단위는 개수로 바꾸고, 큰 이미지는 브라우저에서 줄여 전송합니다.")

# 6. 3일 식단
slide = prs.slides.add_slide(blank)
set_background(slide, STONE_50)
add_title(slide, "MEAL PLAN", "한 끼가 아니라, 3일 뒤 남을 재료까지 계산합니다", "임박 재료를 점심·저녁 6끼에 나누고 각 끼니에서 같은 레시피·차감 흐름을 씁니다.")
add_phone(slide, "06-meal-plan.png", 0.9, 1.92, 2.22, 4.85, caption="실제 3일 식단 화면")
add_card(slide, 3.55, 1.92, 8.86, 1.25, fill=EMERALD_900, line=EMERALD_900)
add_text(slide, "양파", 3.92, 2.2, 1.0, 0.38, size=16, color=EMERALD_100, bold=True)
add_text(slide, "3개", 5.05, 2.13, 1.25, 0.55, size=27, color=WHITE, bold=True)
add_text(slide, "→", 6.43, 2.15, 0.7, 0.5, size=24, color=EMERALD_500, bold=True, align=PP_ALIGN.CENTER)
add_text(slide, "0개", 7.28, 2.13, 1.25, 0.55, size=27, color=EMERALD_500, bold=True)
add_text(slide, "3일 뒤 예상 잔여", 9.03, 2.2, 2.55, 0.4, size=15, color=EMERALD_100, bold=True)
for i, (n, title, body) in enumerate([
    ("01", "임박 재료 우선", "소비기한이 가까운 재료부터\n끼니별 사용량을 배정합니다."),
    ("02", "점심·저녁 6끼", "대용량 재료를 한 끼가 아닌\n여러 끼로 나누어 소진합니다."),
    ("03", "예상 잔여량 표시", "지금 수량과 3일 뒤 수량을\n한 화면에서 비교합니다."),
]):
    x = 3.55 + i * 2.95
    add_card(slide, x, 3.52, 2.65, 2.27, fill=WHITE)
    add_text(slide, n, x + 0.25, 3.78, 0.5, 0.32, size=11, color=EMERALD_700, bold=True)
    add_text(slide, title, x + 0.25, 4.22, 2.1, 0.42, size=16, color=STONE_950, bold=True)
    add_text(slide, body, x + 0.25, 4.88, 2.1, 0.68, size=11, color=STONE_600)
add_round_rect(slide, 3.55, 6.13, 8.86, 0.54, fill=AMBER_100, line=AMBER_100)
add_text(slide, "식단의 각 메뉴를 열면 같은 ‘요리했어요 → 차감’ 흐름을 재사용합니다", 3.83, 6.22, 8.3, 0.31,
         size=13, color=AMBER_800, bold=True)
add_footer(slide, 6, 30, "실제 구현 화면 · frontend/src/features/meal-plan/")
add_notes(slide, "[02:25–02:55]\n한 끼 추천만으로는 양파 한 망 같은 대용량 재료를 다 쓰기 어렵습니다. 3일 식단은 점심과 저녁, 총 6끼에 재료를 나눠 사용합니다. 화면에서는 메뉴뿐 아니라 지금 수량과 3일 뒤 예상 잔여 수량을 보여줍니다. 각 끼니에서도 같은 레시피와 차감 흐름을 사용합니다.")

# 7. 아키텍처
slide = prs.slides.add_slide(blank)
set_background(slide, WHITE)
# AWS 아이콘 기반 PNG를 한 장 전체에 배치해 작은 서비스 라벨도 선명하게 유지합니다.
slide.shapes.add_picture(
    str(SCREENSHOTS / "10-aws-architecture.png"),
    0,
    0,
    width=SLIDE_W,
    height=SLIDE_H,
)
add_notes(slide, "[02:55–03:20]\n프론트엔드는 React 정적 SPA로 만들어 S3와 CloudFront에 배포했습니다. 브라우저의 API 요청은 CloudFront를 거치지 않고 API Gateway로 직접 가며, Python Lambda가 FastAPI와 Mangum으로 처리합니다. 재고는 DynamoDB에 저장하고 이미지 인식과 추천은 Bedrock의 Claude Haiku 4.5가 담당합니다. 아래 배포 흐름은 GitHub OIDC 단기 자격 증명으로 SAM과 프론트엔드를 배포하는 구조입니다.")

# 8. Kiro 기획/설계
slide = prs.slides.add_slide(blank)
set_background(slide, EMERALD_900)
add_title(slide, "KIRO 1/2 · FIGMA MCP", "Designer와 Planner가 Figma에서 설계를 이어 갔습니다", "디자인 시스템 → 구현 화면 → 화면 명세 → 클릭 가능한 프로토타입", dark=True)
# 세 개의 Figma MCP 캡처를 역할과 함께 보여줍니다.
for x, y, w, h in [(0.66, 2.02, 3.0, 4.1), (3.95, 2.02, 3.0, 4.1), (7.24, 2.02, 5.42, 4.1)]:
    add_round_rect(slide, x - 0.035, y - 0.035, w + 0.07, h + 0.07, fill=WHITE, line=WHITE)
add_picture_cover(slide, "07-figma-design.png", 0.66, 2.02, 3.0, 4.1)
add_picture_cover(slide, "08-figma-screen-spec.png", 3.95, 2.02, 3.0, 4.1)
add_picture_cover(slide, "09-figma-prototype.png", 7.24, 2.02, 5.42, 4.1)
add_label(slide, "DESIGNER", 0.87, 2.21, 1.0, fill=EMERALD_900, color=WHITE)
add_round_rect(slide, 0.83, 5.42, 2.66, 0.5, fill=STONE_950, line=STONE_950)
add_text(slide, "00–03 · Foundations / Components / Design", 0.89, 5.53, 2.54, 0.24, size=8.4, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER)
add_label(slide, "PLANNER", 4.16, 2.21, 0.9, fill=EMERALD_900, color=WHITE)
add_round_rect(slide, 4.12, 5.42, 2.66, 0.5, fill=STONE_950, line=STONE_950)
add_text(slide, "04 · Screen Spec 7개 보드", 4.18, 5.53, 2.54, 0.24, size=9.2, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER)
add_label(slide, "PLANNER", 7.47, 2.21, 0.9, fill=EMERALD_900, color=WHITE)
add_round_rect(slide, 7.42, 5.42, 5.06, 0.5, fill=STONE_950, line=STONE_950)
add_text(slide, "05 · Prototype 30 frames / 25 reactions", 7.52, 5.53, 4.86, 0.24, size=9.8, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER)
add_round_rect(slide, 0.66, 6.35, 11.98, 0.48, fill=EMERALD_800, line=EMERALD_700)
add_text(slide, "31 color variables  ·  15 size variables  ·  10 text styles  ·  상태별 variant와 오류 복구 흐름까지 MCP로 검증", 0.9, 6.44, 11.48, 0.25,
         size=10.5, color=EMERALD_100, bold=True, align=PP_ALIGN.CENTER)
add_clickable_text(slide, "Figma 원본 열기 ↗", "https://www.figma.com/design/E4LmR5L4WsyD8Knn7zZl6X/%EB%82%98%EB%A7%8C%EC%9D%98-%EB%83%89%EC%9E%A5%EA%B3%A0---Kirothon?node-id=24-147", 10.83, 0.48, 1.8, 0.3, color=EMERALD_100, size=9.5)
add_footer(slide, 8, 35, "Figma MCP 실제 캡처 · docs/design/figma-handoff.md", dark=True)
add_notes(slide, "[03:20–03:55]\nKiro 안에서 Designer와 Planner가 같은 Figma 파일을 역할별로 이어서 작업했습니다. Designer는 Figma MCP로 색상과 크기 변수, 공통 컴포넌트와 9단계 구현 화면을 만들었습니다. Planner는 그 화면 인스턴스를 재사용해 Screen Spec 7개 보드와 정상·오류 복구 프로토타입을 연결했습니다. 결과는 30개 프레임과 25개 reaction이며, get_screenshot으로 잘림과 연결 상태까지 검증했습니다. 화면 오른쪽 위 링크로 Figma 원본도 확인할 수 있습니다.")

# 9. Kiro 구현/검증
slide = prs.slides.add_slide(blank)
set_background(slide, STONE_50)
add_title(slide, "KIRO 2/2 · SPEC TO DEPLOY", "Kiro가 구현, 검증, 배포 기록까지 이어 갔습니다", "역할별 agent와 Spec task가 같은 steering과 인수 조건을 따라 움직였습니다.")
agents = [
    ("PLANNER", "문제·화면·데모 흐름"),
    ("DESIGNER", "Figma MCP·화면 검증"),
    ("DEVELOPER", "React·FastAPI·테스트"),
    ("INFRA", "SAM·AWS·배포 안전장치"),
]
for i, (name, body) in enumerate(agents):
    x = 0.7 + i * 3.08
    fill = EMERALD_900 if i == 2 else WHITE
    tc = WHITE if i == 2 else STONE_950
    bc = EMERALD_100 if i == 2 else STONE_600
    add_card(slide, x, 2.02, 2.78, 1.25, fill=fill, line=EMERALD_900 if i == 2 else STONE_200)
    add_text(slide, name, x + 0.22, 2.3, 2.34, 0.3, size=11, color=EMERALD_500 if i == 2 else EMERALD_700,
             bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, body, x + 0.2, 2.72, 2.38, 0.3, size=10.5, color=bc, bold=True,
             align=PP_ALIGN.CENTER)
add_card(slide, 0.7, 3.67, 5.92, 2.18, fill=WHITE)
add_text(slide, "MVP Spec 실행 기록", 1.02, 4.0, 2.5, 0.35, size=17, color=STONE_950, bold=True)
add_text(slide, "28", 1.02, 4.5, 1.3, 0.65, size=34, color=EMERALD_700, bold=True)
add_text(slide, "완료 작업", 1.03, 5.12, 1.3, 0.3, size=10.5, color=STONE_600, bold=True)
add_text(slide, "68", 3.0, 4.5, 1.3, 0.65, size=34, color=EMERALD_700, bold=True)
add_text(slide, "실행 기록", 3.02, 5.12, 1.3, 0.3, size=10.5, color=STONE_600, bold=True)
add_text(slide, "tasks.meta.json에 작업별\n구현·검증 이력 보존", 4.55, 4.47, 1.7, 0.85, size=11, color=STONE_600, bold=True)
add_card(slide, 6.92, 3.67, 5.7, 2.18, fill=STONE_950, line=STONE_950)
add_text(slide, "별도 Quick Spec으로 CI/CD", 7.28, 4.0, 4.85, 0.35, size=17, color=WHITE, bold=True)
add_text(slide, "GitHub OIDC", 7.28, 4.5, 1.42, 0.35, size=12, color=EMERALD_500, bold=True)
add_text(slide, "장기 Access Key 없이 AWS 역할 수임", 8.78, 4.5, 3.2, 0.35, size=11, color=STONE_300)
add_text(slide, "배포 대상 검사", 7.28, 5.02, 1.42, 0.35, size=12, color=EMERALD_500, bold=True)
add_text(slide, "계정·리전·저장소·브랜치 확인 후 실행", 8.78, 5.02, 3.2, 0.35, size=11, color=STONE_300)
add_round_rect(slide, 0.7, 6.2, 11.92, 0.5, fill=AMBER_100, line=AMBER_100)
add_text(slide, "13 requirements  ·  156 SHALL 인수 조건  ·  23 correctness properties  ·  345분 작업 계획", 0.95, 6.29, 11.42, 0.28,
         size=11, color=AMBER_800, bold=True, align=PP_ALIGN.CENTER)
add_footer(slide, 9, 35, "근거: BUILD_REPORT.md · tasks.meta.json · .kiro/specs/aws-deployment-cicd/")
add_notes(slide, "[03:55–04:30]\nKiro는 먼저 steering에 문제, 규칙과 범위를 고정하고 Requirements-First Spec으로 13개 요구사항, 156개 인수 조건과 23개 정확성 속성을 만들었습니다. 이후 Planner, Designer, Developer, Infrastructure 네 역할로 나눠 실행했습니다. MVP 기록에는 완료 작업 28개와 실행 68회가 남아 있습니다. 배포도 별도 Quick Spec으로 만들고 GitHub OIDC, 계정·리전·저장소·브랜치 검사까지 구현했습니다.")

# 10. 검증과 마무리
slide = prs.slides.add_slide(blank)
set_background(slide, WHITE)
add_title(slide, "VALIDATION", "데모의 처음부터 끝까지 자동으로 검증했습니다", "사진 등록 → 수정 → 저장 → 추천 → 레시피 → 차감 → 목록 반영")
checks = [
    ("3", "핵심 데모 E2E", "통과"),
    ("81 + 11", "백엔드 + 식단", "통과"),
    ("48 + 4", "프론트엔드 + 식단", "통과"),
    ("✓", "TypeScript · Build", "통과"),
]
for i, (value, label, status) in enumerate(checks):
    x = 0.72 + i * 3.07
    add_card(slide, x, 2.15, 2.75, 1.55, fill=STONE_50)
    add_text(slide, value, x + 0.2, 2.42, 2.35, 0.53, size=27, color=EMERALD_700, bold=True,
             align=PP_ALIGN.CENTER)
    add_text(slide, label, x + 0.2, 3.0, 2.35, 0.3, size=10.5, color=STONE_700, bold=True,
             align=PP_ALIGN.CENTER)
    add_label(slide, status, x + 0.92, 3.4, 0.9)
add_round_rect(slide, 0.72, 4.2, 11.96, 0.57, fill=EMERALD_50, line=EMERALD_100)
add_text(slide, "로컬 smoke  ✓     SAM validate/build  ✓     AWS 배포 및 API health  ✓     GitHub Actions CI/CD  ✓", 1.02, 4.31, 11.36, 0.3,
         size=12.5, color=EMERALD_900, bold=True, align=PP_ALIGN.CENTER)
add_text(slide, "재고를 정확하게 유지해야,", 1.2, 5.28, 10.93, 0.55, size=29, color=STONE_950, bold=True,
         align=PP_ALIGN.CENTER)
add_text(slide, "남은 재료 추천도 실제로 사용할 수 있습니다.", 1.2, 5.91, 10.93, 0.55, size=29, color=EMERALD_700, bold=True,
         align=PP_ALIGN.CENTER)
add_text(slide, "나만의 냉장고", 5.1, 6.62, 3.13, 0.35, size=13, color=STONE_500, bold=True,
         align=PP_ALIGN.CENTER)
add_footer(slide, 10, 30, "2026-11-14 현재 ./scripts/verify-all.sh 직접 재검증 · docs/aws-deployment-validation.md")
add_notes(slide, "[04:30–05:00]\n데모의 영수증 업로드, 결과 수정, 저장, 메뉴 추천, 레시피 확인, 재고 차감과 목록 반영을 종단 간 테스트로 검증했습니다. 핵심 데모 테스트 3개, 백엔드 81개와 식단 11개, 프론트엔드 48개와 식단 4개가 통과했습니다. TypeScript 검사와 프로덕션 빌드, SAM 검증, 실제 AWS 배포도 완료했습니다. 나만의 냉장고는 재료를 등록하는 데서 끝나지 않고, 요리 후에도 실제 냉장고와 맞는 재고를 유지합니다.")

# 문서 속성
prs.core_properties.title = "나만의 냉장고 - KIROTHON 2026 발표자료"
prs.core_properties.subject = "TEAM 015 깜자조와 5분 발표"
prs.core_properties.author = "송하람"
prs.core_properties.keywords = "KIROTHON,Kiro,나만의 냉장고,AWS,Bedrock"
prs.core_properties.comments = "PRESENTATION.pdf로 내보내기 위한 편집 원본"

prs.save(OUTPUT)
print(OUTPUT)
