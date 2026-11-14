from __future__ import annotations

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.management import Cloudformation
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import IAM
from diagrams.aws.storage import S3
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import Users
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME = OUT_DIR / "_runtime-architecture"
DEPLOY = OUT_DIR / "_deployment-architecture"
OUTPUT = OUT_DIR / "10-aws-architecture.png"

GRAPH = {
    "bgcolor": "transparent",
    "pad": "0.22",
    "nodesep": "0.55",
    "ranksep": "0.75",
    "splines": "spline",
    "fontname": "Apple SD Gothic Neo",
    "fontsize": "18",
    "dpi": "170",
}
NODE = {
    "fontname": "Apple SD Gothic Neo",
    "fontsize": "12",
    "fontcolor": "#292524",
    "color": "#d6d3d1",
    "penwidth": "1.2",
}
EDGE = {
    "fontname": "Apple SD Gothic Neo",
    "fontsize": "9.5",
    "fontcolor": "#57534e",
    "color": "#059669",
    "penwidth": "1.6",
    "arrowsize": "0.75",
}

# 실제 template.yaml의 런타임 요청 흐름입니다.
with Diagram(
    "",
    filename=str(RUNTIME),
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=GRAPH,
    node_attr=NODE,
    edge_attr=EDGE,
):
    browser = Users("사용자 브라우저\nReact SPA")
    with Cluster("AWS 계정 462747820533 · ap-northeast-2", graph_attr={"color": "#a7f3d0", "penwidth": "1.6", "style": "rounded", "fontname": "Apple SD Gothic Neo", "fontsize": "13"}):
        cloudfront = CloudFront("WebDistribution\nAmazon CloudFront")
        static_bucket = S3("StaticBucket\n비공개 S3")
        http_api = APIGateway("HttpApi\nHTTP API")
        api_function = Lambda("ApiFunction\nPython 3.13\nFastAPI + Mangum")
        inventory = Dynamodb("InventoryTable\nPAY_PER_REQUEST")
        bedrock = Bedrock("Amazon Bedrock\nClaude Haiku 4.5")

    browser >> Edge(label="HTTPS · 정적 SPA", **EDGE) >> cloudfront
    cloudfront >> Edge(label="OAC SigV4 · GetObject", **EDGE) >> static_bucket
    browser >> Edge(label="HTTPS · /api/*\nX-Device-Id", **EDGE) >> http_api
    http_api >> Edge(label="ANY /api/{proxy+}", **EDGE) >> api_function
    api_function >> Edge(label="재고 조회·원자 차감", **EDGE) >> inventory
    api_function >> Edge(label="Converse · strict tool use", **EDGE) >> bedrock

# 실제 cd.yml과 OIDC bootstrap의 배포 흐름입니다.
with Diagram(
    "",
    filename=str(DEPLOY),
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=GRAPH,
    node_attr=NODE,
    edge_attr={**EDGE, "color": "#d97706"},
):
    actions = GithubActions("GitHub Actions CD\nmain push / dispatch")
    with Cluster("단기 자격 증명", graph_attr={"color": "#fde68a", "penwidth": "1.6", "style": "rounded", "fontname": "Apple SD Gothic Neo", "fontsize": "13"}):
        oidc = IAM("GitHub OIDC\n+ AWS STS")
        role = IAM("IAM Role\nmy-own-fridge-\ngithub-deploy")
    artifact = S3("SamArtifactBucket\n암호화·버전 관리")
    stack = Cloudformation("SAM · CloudFormation\nStack: my-own-fridge")
    runtime = Lambda("런타임 리소스\n생성·갱신")

    actions >> Edge(label="OIDC token", color="#d97706", **{k:v for k,v in EDGE.items() if k != 'color'}) >> oidc
    oidc >> Edge(label="AssumeRoleWithWebIdentity", color="#d97706", **{k:v for k,v in EDGE.items() if k != 'color'}) >> role
    role >> Edge(label="SAM artifact", color="#d97706", **{k:v for k,v in EDGE.items() if k != 'color'}) >> artifact
    role >> Edge(label="sam deploy", color="#d97706", **{k:v for k,v in EDGE.items() if k != 'color'}) >> stack
    stack >> Edge(label="배포", style="dashed", color="#d97706", **{k:v for k,v in EDGE.items() if k != 'color'}) >> runtime


def crop_whitespace(image: Image.Image, margin: int = 24) -> Image.Image:
    # Graphviz는 투명 설정에서도 큰 배경 캔버스를 만들 수 있어 배경색 차이로 실제 내용을 찾습니다.
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    difference = ImageChops.difference(rgb, background).convert("L")
    mask = difference.point(lambda value: 255 if value > 8 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return rgba
    left, top, right, bottom = bbox
    return rgba.crop((max(0, left - margin), max(0, top - margin), min(rgba.width, right + margin), min(rgba.height, bottom + margin)))


def font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size, index=8 if bold and candidate.endswith(".ttc") else 0)
        except OSError:
            continue
    return ImageFont.load_default()


runtime = crop_whitespace(Image.open(f"{RUNTIME}.png"))
deploy = crop_whitespace(Image.open(f"{DEPLOY}.png"))
print(f"cropped runtime={runtime.size}, deploy={deploy.size}")
canvas = Image.new("RGB", (2800, 1575), "#fafaf9")
draw = ImageDraw.Draw(canvas)

# 제목과 설명
left = 110
draw.text((left, 70), "나만의 냉장고 · 구현 아키텍처", fill="#1c1917", font=font(62, True))
draw.text((left, 145), "template.yaml과 GitHub Actions CD를 기준으로 그린 실제 배포 구조", fill="#57534e", font=font(29))

# 섹션 카드
runtime_box = (90, 220, 2710, 1005)
deploy_box = (90, 1040, 2710, 1430)
for box, outline in [(runtime_box, "#a7f3d0"), (deploy_box, "#fde68a")]:
    draw.rounded_rectangle(box, radius=32, fill="#ffffff", outline=outline, width=4)

draw.rounded_rectangle((130, 252, 505, 314), radius=18, fill="#d1fae5")
draw.text((165, 265), "RUNTIME · 사용자 요청", fill="#065f46", font=font(27, True))
draw.rounded_rectangle((130, 1070, 565, 1132), radius=18, fill="#fef3c7")
draw.text((165, 1083), "DEPLOYMENT · OIDC CI/CD", fill="#92400e", font=font(27, True))

# 다이어그램을 카드에 맞게 축소합니다.
def place_contain(source: Image.Image, box, top_padding=76):
    x1, y1, x2, y2 = box
    max_w = x2 - x1 - 70
    max_h = y2 - y1 - top_padding - 34
    ratio = min(max_w / source.width, max_h / source.height)
    resized = source.resize((int(source.width * ratio), int(source.height * ratio)), Image.Resampling.LANCZOS)
    x = x1 + (x2 - x1 - resized.width) // 2
    y = y1 + top_padding + (max_h - resized.height) // 2
    canvas.paste(resized, (x, y), resized)

place_contain(runtime, runtime_box, 86)
place_contain(deploy, deploy_box, 76)

# 보안 경계 요약
security = "S3 공개 차단  ·  CloudFront OAC 전용 읽기  ·  Lambda 최소 권한  ·  GitHub OIDC 단기 자격 증명"
draw.rounded_rectangle((240, 1462, 2560, 1535), radius=22, fill="#064e3b")
text_bbox = draw.textbbox((0, 0), security, font=font(25, True))
draw.text(((2800 - (text_bbox[2] - text_bbox[0])) / 2, 1482), security, fill="#ecfdf5", font=font(25, True))

canvas.save(OUTPUT, quality=95)
print(OUTPUT)

# 중간 생성물은 발표 산출물에 포함하지 않습니다.
Path(f"{RUNTIME}.png").unlink(missing_ok=True)
Path(f"{DEPLOY}.png").unlink(missing_ok=True)
