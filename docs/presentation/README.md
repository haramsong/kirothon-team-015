# 발표자료 편집 원본

## 산출물

- `../../PRESENTATION.pdf`: 제출 가능한 10쪽 PDF
- `../../PRESENTATION_SOURCE.pptx`: 16:9 편집 원본, 10장, 발표자 노트 포함
- `generate_presentation_pdf.py`: PowerPoint 앱 없이 PDF와 슬라이드 PNG를 다시 만드는 스크립트
- `PRESENTATION_SCRIPT.md`: 5분 발표 대본과 시간 배분
- `screenshots/01-*.png`~`06-*.png`: 실제 구현 화면 캡처
- `screenshots/07-figma-design.png`: Designer가 Figma MCP로 만든 `03 Design` 보드
- `screenshots/08-figma-screen-spec.png`: Planner가 Figma MCP로 만든 `04 Screen Spec` 보드
- `screenshots/09-figma-prototype.png`: Planner가 연결한 `05 Prototype` 흐름
- `screenshots/10-aws-architecture.png`: `template.yaml`과 GitHub Actions CD 기준 AWS 구현 아키텍처

## 원본 링크

- Figma: https://www.figma.com/design/E4LmR5L4WsyD8Knn7zZl6X/%EB%82%98%EB%A7%8C%EC%9D%98-%EB%83%89%EC%9E%A5%EA%B3%A0---Kirothon?node-id=24-147
- Figma file key: `E4LmR5L4WsyD8Knn7zZl6X`

## 재생성

생성된 PPTX를 바로 편집해도 됩니다. 코드로 다시 만들려면 임시 가상환경에 아래 패키지가 필요합니다.

```bash
python3 -m venv /tmp/kirothon-presentation-venv
/tmp/kirothon-presentation-venv/bin/pip install python-pptx==1.0.2 diagrams==0.25.1
/tmp/kirothon-presentation-venv/bin/python docs/presentation/generate_architecture_diagram.py
/tmp/kirothon-presentation-venv/bin/python docs/presentation/generate_presentation.py
/tmp/kirothon-presentation-venv/bin/python docs/presentation/generate_presentation_pdf.py
```

Graphviz의 `dot` 실행 파일도 필요합니다.

## 제출용 PDF

1. `PRESENTATION_SOURCE.pptx`를 PowerPoint, Keynote 또는 Google Slides로 엽니다.
2. 한글 줄바꿈과 이미지 선명도를 확인합니다.
3. 16:9 비율로 PDF를 내보냅니다.
4. 저장소 최상단에 `PRESENTATION.pdf`라는 정확한 이름으로 저장합니다.
