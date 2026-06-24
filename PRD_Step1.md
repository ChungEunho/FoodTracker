# PRD Step 1 — 음식 이미지 인식

## 목적
사용자가 촬영한 음식 사진을 입력받아 `nvidia/nemotron-nano-12b-v2-vl:free` 모델로 이미지를 분석하고, 사진에 담긴 음식의 구성 요소를 텍스트로 추출한다.

## 입력
| 항목 | 형식 | 설명 |
|------|------|------|
| 음식 사진 | JPEG / PNG | 로컬 파일 경로를 CLI 인수로 전달 |

## 처리 흐름

```
[이미지 파일] → base64 인코딩 → Gemma Vision API 호출 → 인식 결과(텍스트)
```

1. 지정 경로의 이미지를 읽어 base64로 인코딩한다.
2. `nvidia/nemotron-nano-12b-v2-vl:free` 모델에 이미지와 시스템 프롬프트를 함께 전송한다.
3. 모델이 반환한 음식 구성 정보를 구조화된 텍스트(JSON)로 파싱한다.

## 시스템 프롬프트 방향
- 사진 속 음식 항목을 모두 열거하도록 지시
- 각 항목에 대해 음식명(한국어 포함), 예상 조리법(구이/볶음/생식 등), 재료 특이사항을 기술하도록 요청
- 출력 형식을 JSON 배열로 고정하여 Step 2로 안정적으로 전달

## 출력 (Step 2로 전달되는 구조체)

```json
{
  "items": [
    {
      "name": "닭가슴살 샐러드",
      "cooking_method": "삶음",
      "notes": "드레싱 별도"
    },
    {
      "name": "현미밥",
      "cooking_method": "증기",
      "notes": "약 1공기 추정"
    }
  ],
  "raw_description": "모델 원문 응답"
}
```

## 에러 처리
| 상황 | 처리 방식 |
|------|-----------|
| 파일 미존재 | 즉시 종료 후 경로 오류 메시지 출력 |
| 지원하지 않는 형식 | JPEG/PNG만 허용, 그 외 거부 |
| 모델 응답 파싱 실패 | `raw_description`만 보존하고 Step 2에 전달 |
| API 오류 (4xx/5xx) | 오류 코드와 메시지 출력 후 종료 |

## 구현 범위
- `step1_recognize.py` 단일 파일
- CLI: `python step1_recognize.py <이미지_경로>`
- 단독 실행 시 결과를 stdout에 JSON으로 출력
- Step 2에서 import하여 함수로도 호출 가능하도록 `recognize(image_path) -> dict` 함수 노출
