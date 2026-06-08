# 📄 PDF 압축기 (PDF Compressor)

브라우저에서 바로 동작하는 무료 PDF 압축 도구입니다.
여러 파일을 한 번에 압축할 수 있고, **파일이 서버로 업로드되지 않습니다** (모든 처리는 브라우저 안에서 이루어집니다).

## ✨ 기능

- 드래그&드롭으로 **여러 PDF 한꺼번에** 압축
- 압축 강도 선택 (낮음 / 보통 / 높음)
- 파일별 진행 상황 및 절감률 표시
- **ZIP 일괄 다운로드** 또는 파일별 개별 다운로드
- 100% 클라이언트 처리 — 개인정보 안전

## 🚀 사용법

### 웹에서 (GitHub Pages)
배포된 링크에 접속해서 PDF를 끌어다 놓으면 끝.

### 로컬에서
`index.html` 파일을 더블클릭하면 브라우저에서 열립니다.
(라이브러리를 CDN에서 불러오므로 첫 실행 시 인터넷 연결 필요)

## ⚙️ 동작 원리

각 페이지를 [PDF.js](https://mozilla.github.io/pdf.js/)로 렌더링한 뒤,
JPEG로 재압축하여 [jsPDF](https://github.com/parallax/jsPDF)로 새 PDF를 만듭니다.
여러 파일은 [JSZip](https://stuk.github.io/jszip/)으로 묶어 받을 수 있습니다.

> ⚠️ 페이지를 이미지로 변환하는 방식이라, 압축 후에는 텍스트 선택/검색 기능이 사라집니다.
> 텍스트를 유지하면서 압축하려면 함께 들어있는 Python 버전(`pdf_compressor.py`)을 사용하세요.

## 🐍 Python 버전 (텍스트 유지형)

```bash
pip install pikepdf Pillow
python pdf_compressor.py
```

`pikepdf` + `Pillow`로 내부 이미지만 재압축하여 텍스트는 그대로 둡니다. 여러 파일 일괄 처리를 지원하는 GUI 앱입니다.
