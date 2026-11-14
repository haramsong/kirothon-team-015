from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SHOT = Path(__file__).resolve().parent / "screenshots"
RENDERED = Path(__file__).resolve().parent / "rendered"
OUTPUT = ROOT / "PRESENTATION.pdf"
RENDERED.mkdir(parents=True, exist_ok=True)

W, H = 1600, 900
STONE_950 = "#1c1917"
STONE_800 = "#292524"
STONE_700 = "#44403c"
STONE_600 = "#57534e"
STONE_500 = "#78716c"
STONE_300 = "#d6d3d1"
STONE_200 = "#e7e5e4"
STONE_100 = "#f5f5f4"
STONE_50 = "#fafaf9"
WHITE = "#ffffff"
EMERALD_900 = "#064e3b"
EMERALD_800 = "#065f46"
EMERALD_700 = "#047857"
EMERALD_600 = "#059669"
EMERALD_500 = "#10b981"
EMERALD_100 = "#d1fae5"
EMERALD_50 = "#ecfdf5"
AMBER_800 = "#92400e"
AMBER_100 = "#fef3c7"

FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


def font(size: int, bold: bool = False):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size=size, index=8 if bold and path.endswith(".ttc") else 0)
        except OSError:
            continue
    return ImageFont.load_default()


def canvas(color=STONE_50):
    return Image.new("RGB", (W, H), color)


def rounded(draw, box, fill, outline=None, width=2, radius=28):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, size, color=STONE_950, bold=False, anchor="la", spacing=8, align="left"):
    draw.multiline_text(xy, value, font=font(size, bold), fill=color, anchor=anchor, spacing=spacing, align=align)


def center_text(draw, box, value, size, color=STONE_950, bold=False):
    x1, y1, x2, y2 = box
    text(draw, ((x1+x2)//2, (y1+y2)//2), value, size, color, bold, anchor="mm", align="center")


def title(draw, eyebrow, heading, subtitle=None, dark=False):
    text(draw, (78, 48), eyebrow, 18, EMERALD_100 if dark else EMERALD_700, True)
    text(draw, (78, 94), heading, 41, WHITE if dark else STONE_950, True)
    if subtitle:
        text(draw, (78, 158), subtitle, 21, STONE_300 if dark else STONE_600)


def footer(draw, number, seconds, source=None, dark=False):
    color = STONE_300 if dark else STONE_500
    if source:
        text(draw, (78, 868), source, 12, color)
    text(draw, (1525, 864), f"{number:02d} · {seconds}초", 13, color, anchor="ra")


def label(draw, box, value, fill=EMERALD_100, color=EMERALD_800):
    rounded(draw, box, fill, fill, radius=16)
    center_text(draw, box, value, 14, color, True)


def paste_image(base, path, box, mode="contain", radius=20, background=WHITE, border=STONE_200):
    x1, y1, x2, y2 = map(int, box)
    bw, bh = x2-x1, y2-y1
    src = Image.open(path).convert("RGB")
    if mode == "cover":
        fitted = ImageOps.fit(src, (bw, bh), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    else:
        fitted = ImageOps.contain(src, (bw, bh), method=Image.Resampling.LANCZOS)
        layer = Image.new("RGB", (bw, bh), background)
        layer.paste(fitted, ((bw-fitted.width)//2, (bh-fitted.height)//2))
        fitted = layer
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw-1, bh-1), radius=radius, fill=255)
    base.paste(fitted, (x1, y1), mask)
    if border:
        ImageDraw.Draw(base).rounded_rectangle((x1, y1, x2, y2), radius=radius, outline=border, width=2)


def card(draw, box, fill=WHITE, outline=STONE_200):
    rounded(draw, box, fill, outline, radius=25)


def bullet(draw, x, y, heading, body, width=420):
    draw.ellipse((x, y+4, x+15, y+19), fill=EMERALD_600)
    text(draw, (x+30, y), heading, 21, STONE_950, True)
    text(draw, (x+30, y+36), body, 16, STONE_600, spacing=5)


slides: list[Image.Image] = []

# 1 표지
im = canvas(EMERALD_900); d = ImageDraw.Draw(im)
label(d, (82, 62, 465, 106), "KIROTHON 2026 · TEAM 015 깜자조와", EMERALD_800, EMERALD_100)
text(d, (85, 170), "나만의\n냉장고", 78, WHITE, True, spacing=2)
text(d, (85, 430), "재료를 넣는 순간부터\n요리해 빼는 순간까지", 38, EMERALD_100, True)
text(d, (85, 595), "영수증·주문내역 인식  →  임박 재료 추천  →  요리 후 자동 차감", 19, STONE_200)
rounded(d, (85, 690, 560, 758), EMERALD_600, EMERALD_600, radius=22)
center_text(d, (85, 690, 560, 758), "정확한 재고가 다음 추천의 시작입니다", 20, WHITE, True)
paste_image(im, SHOT/"03-inventory.png", (840, 105, 1215, 695), "cover", 28, border=STONE_950)
paste_image(im, SHOT/"05-deduction.png", (1165, 205, 1510, 748), "cover", 28, border=STONE_950)
footer(d, 1, 15, dark=True); slides.append(im)

# 2 문제
im = canvas(); d = ImageDraw.Draw(im); title(d, "PROBLEM", "냉장고 목록이 틀리면, 추천도 쓸 수 없습니다", "기존 방식은 ‘넣는 일’을 줄였지만, ‘빼는 일’은 사용자에게 남겼습니다.")
card(d, (80, 250, 470, 680)); text(d, (120, 300), "36.1%", 63, EMERALD_700, True)
text(d, (120, 400), "2024년 전체 가구 중\n1인 가구 비중", 27, STONE_800, True)
text(d, (120, 580), "804만 5천 가구", 24, STONE_600)
problems=[("01","혼자 먹기엔 큰 판매 단위","양파 한 망과 대파 한 단은\n한 끼로 다 쓰기 어렵습니다."),("02","온라인 장보기에는\n종이 영수증이 없음","스크린샷 품목을 다시\n손으로 입력해야 합니다."),("03","먹은 재료를\n직접 지우지 않음","재고가 실제 냉장고와 달라져\n추천을 믿을 수 없습니다.")]
for i,(n,h,b) in enumerate(problems):
    x=515+i*330; card(d,(x,250,x+295,680)); text(d,(x+28,290),n,17,EMERALD_700,True); text(d,(x+28,350),h,24,STONE_950,True); text(d,(x+28,510),b,17,STONE_600)
rounded(d,(515,710,1500,780),AMBER_100,AMBER_100,radius=20); center_text(d,(515,710,1500,780),"핵심 관찰 · 등록보다 ‘사용 후 차감’이 재고 신뢰도를 결정합니다",22,AMBER_800,True)
footer(d,2,30,"출처: 국가데이터처, 「2025 통계로 보는 1인가구」"); slides.append(im)

# 3 해결 흐름
im=canvas(WHITE); d=ImageDraw.Draw(im); title(d,"SOLUTION","등록부터 차감까지 닫힌 흐름으로 연결했습니다","정확한 재고가 유지되어야 다음 추천도 실제로 만들 수 있습니다.")
steps=[("1","장보기","영수증·주문내역"),("2","등록","확인 후 저장"),("3","추천","임박 재료 우선"),("4","요리","1인분 레시피"),("5","차감","사용자 확인")]
for i,(n,h,b) in enumerate(steps):
    x=82+i*300; fill=EMERALD_900 if i==4 else EMERALD_50; tc=WHITE if i==4 else EMERALD_900
    card(d,(x,275,x+245,475),fill,EMERALD_900 if i==4 else EMERALD_100); text(d,(x+25,300),n,16,EMERALD_500 if i==4 else EMERALD_700,True); text(d,(x+25,350),h,30,tc,True); text(d,(x+25,410),b,16,EMERALD_100 if i==4 else STONE_600)
    if i<4: text(d,(x+268,375),"→",28,STONE_300,True,anchor="mm")
rounded(d,(130,565,1470,675),STONE_950,STONE_950,radius=24)
text(d,(175,620),"실제 냉장고와 맞는 목록",27,WHITE,True,anchor="lm"); text(d,(545,620),"→",29,EMERALD_500,True,anchor="mm"); text(d,(595,620),"더 정확한 다음 추천",27,WHITE,True,anchor="lm"); text(d,(1260,620),"요리 후 자동 차감",22,EMERALD_500,True,anchor="mm")
text(d,(800,760),"① 요리 후 차감     ② 주문내역 캡처 인식     ③ 3일 동안 대용량 재료 소진",23,STONE_700,True,anchor="mm")
footer(d,3,25,"근거: .kiro/steering/product.md · README.md"); slides.append(im)

# 4 차감
im=canvas(); d=ImageDraw.Draw(im); title(d,"CORE DIFFERENTIATOR","“요리했어요”를 누르면 재고가 줄어듭니다","추천 수량을 그대로 믿지 않고, 실제 사용량을 확인한 뒤 반영합니다.")
paste_image(im,SHOT/"04-recipe.png",(85,240,440,800),"cover",26,border=STONE_950); label(d,(155,748,370,790),"① 추천 레시피",STONE_950,WHITE)
text(d,(475,520),"→",42,EMERALD_600,True,anchor="mm")
paste_image(im,SHOT/"05-deduction.png",(520,240,875,800),"cover",26,border=STONE_950); label(d,(590,748,805,790),"② 차감 전 확인",STONE_950,WHITE)
card(d,(930,240,1510,800)); label(d,(980,285,1105,330),"대표 가치"); text(d,(980,375),"양파 8개  →  7개",39,EMERALD_700,True)
bullet(d,985,475,"0.5개 단위 수정","반 개를 쓴 실제 요리도 같은 단위로 처리")
bullet(d,985,575,"확인 후에만 반영","사용자가 고친 뒤에만 재고를 차감")
bullet(d,985,675,"중복 차감 방지","트랜잭션과 요청 ID로 한 번만 적용")
footer(d,4,45,"실제 구현 화면 · DeductionModal.tsx"); slides.append(im)

# 5 등록
im=canvas(WHITE); d=ImageDraw.Draw(im); title(d,"REGISTRATION","종이 영수증도, 주문내역 캡처도 같은 버튼 하나로","Bedrock이 품목·개수·보관 위치·예상 소비기한을 추출하고, 사용자가 수정합니다.")
paste_image(im,SHOT/"01-registration-upload.png",(85,235,445,803),"cover",26,border=STONE_950); label(d,(150,750,380,792),"① 사진 선택",STONE_950,WHITE)
text(d,(485,520),"+",42,STONE_300,True,anchor="mm")
paste_image(im,SHOT/"02-registration-result.png",(525,235,885,803),"cover",26,border=STONE_950); label(d,(590,750,820,792),"② 인식 결과 확인",STONE_950,WHITE)
card(d,(935,235,1510,803),EMERALD_50,EMERALD_100); text(d,(985,285),"입력은 간단하게",29,EMERALD_900,True); text(d,(985,355),"영수증 / 주문내역을\n구분하는 단계가 없습니다",28,STONE_950,True)
bullet(d,990,490,"모든 LLM 값 수정 가능","수정·삭제·직접 추가 후 저장")
bullet(d,990,590,"단위를 ‘개’로 통일","kg·g·L 표기를 0.5개 단위로 변환")
bullet(d,990,690,"브라우저에서 이미지 축소","긴 변 1568px 이하 JPEG로 전처리")
footer(d,5,30,"실제 구현 화면 · Amazon Bedrock Claude Haiku 4.5"); slides.append(im)

# 6 식단
im=canvas(); d=ImageDraw.Draw(im); title(d,"MEAL PLAN","한 끼가 아니라, 3일 뒤 남을 재료까지 계산합니다","임박 재료를 점심·저녁 6끼에 나누고 같은 레시피·차감 흐름을 씁니다.")
paste_image(im,SHOT/"06-meal-plan.png",(90,225,390,800),"cover",26,border=STONE_950)
rounded(d,(440,225,1510,365),EMERALD_900,EMERALD_900,radius=25); text(d,(490,295),"양파",24,EMERALD_100,True,anchor="lm"); text(d,(650,295),"3개",42,WHITE,True,anchor="mm"); text(d,(785,295),"→",35,EMERALD_500,True,anchor="mm"); text(d,(920,295),"0개",42,EMERALD_500,True,anchor="mm"); text(d,(1240,295),"3일 뒤 예상 잔여",24,EMERALD_100,True,anchor="mm")
items=[("01","임박 재료 우선","소비기한이 가까운 재료부터\n끼니별 사용량을 배정합니다."),("02","점심·저녁 6끼","대용량 재료를 한 끼가 아닌\n여러 끼로 나누어 씁니다."),("03","예상 잔여량 표시","지금 수량과 3일 뒤 수량을\n한 화면에서 비교합니다.")]
for i,(n,h,b) in enumerate(items):
    x=440+i*365; card(d,(x,410,x+330,675)); text(d,(x+28,445),n,16,EMERALD_700,True); text(d,(x+28,505),h,24,STONE_950,True); text(d,(x+28,575),b,17,STONE_600)
rounded(d,(440,720,1510,790),AMBER_100,AMBER_100,radius=20); center_text(d,(440,720,1510,790),"각 끼니에서 같은 ‘요리했어요 → 차감’ 흐름을 재사용합니다",20,AMBER_800,True)
footer(d,6,30,"실제 구현 화면 · frontend/src/features/meal-plan/"); slides.append(im)

# 7 AWS 아키텍처 PNG
arch=Image.open(SHOT/"10-aws-architecture.png").convert("RGB").resize((W,H),Image.Resampling.LANCZOS); slides.append(arch)

# 8 Figma MCP
im=canvas(EMERALD_900); d=ImageDraw.Draw(im); title(d,"KIRO 1/2 · FIGMA MCP","Designer와 Planner가 Figma에서 설계를 이어 갔습니다","디자인 시스템 → 구현 화면 → 화면 명세 → 클릭 가능한 프로토타입",True)
boxes=[(70,235,430,735),(465,235,825,735),(860,235,1530,735)]
for b in boxes: rounded(d,(b[0]-4,b[1]-4,b[2]+4,b[3]+4),WHITE,WHITE,radius=24)
paste_image(im,SHOT/"07-figma-design.png",boxes[0],"cover",22,border=None); paste_image(im,SHOT/"08-figma-screen-spec.png",boxes[1],"cover",22,border=None); paste_image(im,SHOT/"09-figma-prototype.png",boxes[2],"cover",22,border=None)
label(d,(92,255,215,295),"DESIGNER",EMERALD_900,WHITE); label(d,(487,255,600,295),"PLANNER",EMERALD_900,WHITE); label(d,(882,255,995,295),"PLANNER",EMERALD_900,WHITE)
rounded(d,(90,665,410,715),STONE_950,STONE_950,radius=15); center_text(d,(90,665,410,715),"00–03 · Design system / Screens",14,WHITE,True)
rounded(d,(485,665,805,715),STONE_950,STONE_950,radius=15); center_text(d,(485,665,805,715),"04 · Screen Spec 7개 보드",14,WHITE,True)
rounded(d,(885,665,1505,715),STONE_950,STONE_950,radius=15); center_text(d,(885,665,1505,715),"05 · Prototype 30 frames / 25 reactions",15,WHITE,True)
rounded(d,(70,780,1530,835),EMERALD_800,EMERALD_700,radius=18); center_text(d,(70,780,1530,835),"31 color variables · 15 size variables · 10 text styles · 상태 variant와 오류 복구까지 MCP로 검증",16,EMERALD_100,True)
text(d,(1525,55),"Figma: E4LmR5L4WsyD8Knn7zZl6X",14,EMERALD_100,True,anchor="ra"); footer(d,8,35,"Figma MCP 실제 캡처 · docs/design/figma-handoff.md",True); slides.append(im)

# 9 Kiro 작업 방식
im=canvas(); d=ImageDraw.Draw(im); title(d,"KIRO 2/2 · SPEC TO DEPLOY","Kiro가 구현, 검증, 배포 기록까지 이어 갔습니다","역할별 agent와 Spec task가 같은 steering과 인수 조건을 따라 움직였습니다.")
agents=[("PLANNER","문제·화면·데모 흐름"),("DESIGNER","Figma MCP·화면 검증"),("DEVELOPER","React·FastAPI·테스트"),("INFRA","SAM·AWS·배포 안전장치")]
for i,(h,b) in enumerate(agents):
    x=80+i*365; fill=EMERALD_900 if i==2 else WHITE; card(d,(x,235,x+330,360),fill,EMERALD_900 if i==2 else STONE_200); center_text(d,(x+15,250,x+315,295),h,18,EMERALD_500 if i==2 else EMERALD_700,True); center_text(d,(x+15,300,x+315,345),b,15,EMERALD_100 if i==2 else STONE_600,True)
card(d,(80,415,765,700)); text(d,(120,460),"MVP Spec 실행 기록",26,STONE_950,True); text(d,(125,550),"28",55,EMERALD_700,True,anchor="mm"); text(d,(125,620),"완료 작업",16,STONE_600,True,anchor="mm"); text(d,(340,550),"68",55,EMERALD_700,True,anchor="mm"); text(d,(340,620),"실행 기록",16,STONE_600,True,anchor="mm"); text(d,(500,535),"tasks.meta.json에\n작업별 구현·검증\n이력을 보존",19,STONE_600,True)
card(d,(825,415,1520,700),STONE_950,STONE_950); text(d,(875,460),"별도 Quick Spec으로 CI/CD",26,WHITE,True); text(d,(875,535),"GitHub OIDC",19,EMERALD_500,True); text(d,(1065,535),"장기 Access Key 없이 역할 수임",17,STONE_300); text(d,(875,590),"배포 대상 검사",19,EMERALD_500,True); text(d,(1065,590),"계정·리전·저장소·브랜치 확인",17,STONE_300)
rounded(d,(80,750,1520,815),AMBER_100,AMBER_100,radius=20); center_text(d,(80,750,1520,815),"13 requirements · 156 SHALL 인수 조건 · 23 correctness properties · 345분 작업 계획",18,AMBER_800,True)
footer(d,9,35,"근거: BUILD_REPORT.md · tasks.meta.json · .kiro/specs/"); slides.append(im)

# 10 검증
im=canvas(WHITE); d=ImageDraw.Draw(im); title(d,"VALIDATION","데모의 처음부터 끝까지 자동으로 검증했습니다","사진 등록 → 수정 → 저장 → 추천 → 레시피 → 차감 → 목록 반영")
checks=[("3","핵심 데모 E2E"),("81 + 11","백엔드 + 식단"),("48 + 4","프론트엔드 + 식단"),("✓","TypeScript · Build")]
for i,(v,l) in enumerate(checks):
    x=80+i*365; card(d,(x,250,x+330,430),STONE_50); center_text(d,(x+15,275,x+315,340),v,42,EMERALD_700,True); center_text(d,(x+15,345,x+315,390),l,17,STONE_700,True); label(d,(x+115,395,x+215,430),"통과")
rounded(d,(80,485,1520,555),EMERALD_50,EMERALD_100,radius=20); center_text(d,(80,485,1520,555),"로컬 smoke ✓   SAM validate/build ✓   AWS 배포·API health ✓   GitHub Actions CI/CD ✓",20,EMERALD_900,True)
text(d,(800,670),"재고를 정확하게 유지해야,",42,STONE_950,True,anchor="mm"); text(d,(800,735),"남은 재료 추천도 실제로 사용할 수 있습니다.",42,EMERALD_700,True,anchor="mm"); text(d,(800,815),"나만의 냉장고",19,STONE_500,True,anchor="mm")
footer(d,10,30,"2026-11-14 ./scripts/verify-all.sh 재검증 · docs/aws-deployment-validation.md"); slides.append(im)

# 각 슬라이드 PNG와 멀티페이지 PDF를 만듭니다.
for i, slide in enumerate(slides, 1):
    slide.save(RENDERED / f"slide-{i:02d}.png", optimize=True)
slides[0].save(OUTPUT, "PDF", save_all=True, append_images=slides[1:], resolution=150.0, quality=95)

# 전체 흐름을 빠르게 확인할 수 있는 contact sheet도 만듭니다.
thumbs=[]
for slide in slides:
    thumbs.append(slide.resize((480,270),Image.Resampling.LANCZOS))
sheet=Image.new("RGB",(960,1350),"#e7e5e4")
for i,thumb in enumerate(thumbs):
    sheet.paste(thumb,((i%2)*480,(i//2)*270))
sheet.save(RENDERED/"contact-sheet.jpg",quality=88)
print(OUTPUT)
