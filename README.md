# Gemini 이미지 생성 로컬 환경

## 처음 한 번 설정

1. 프로젝트 폴더에 `env` 또는 `.env` 파일을 만듭니다.
2. `GEMINI_API_KEY=본인의_API_키`를 입력합니다.
3. API 키가 들어간 파일은 공유하거나 업로드하지 마세요. Git에서 제외되어 있습니다.

## 실행

`start_server.command`를 실행한 다음 브라우저에서 <http://127.0.0.1:8765/image.html>을 엽니다. macOS에서 실행이 차단되면 터미널에서 다음을 실행하세요.

```sh
cd ~/Desktop/design_html
python3 server.py
```

페이지에서 항목을 열고 **Gemini 생성**을 누르면 원본 이미지와 기본 프롬프트를 Gemini 이미지 모델로 보내 AI 생성 결과에 표시합니다. 결과 이미지는 480KB 미만으로 압축되며, **최종 HTML 저장**을 누르면 HTML에 포함됩니다. 생성 요청은 Google Gemini API로 전송되며 API 사용량이나 과금이 발생할 수 있습니다.

기본 모델은 `gemini-nano-banana-2.1`입니다. 다른 사용 가능한 이미지 모델을 쓰려면 `.env`에 `GEMINI_IMAGE_MODEL=모델명`을 지정하고 서버를 다시 시작하세요.
