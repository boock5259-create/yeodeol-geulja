# 여덟 글자 · AI 심층분석 로컬 헤드리스 워커

웹앱의 "AI 심층 분석" 카드를 **진짜 AI**로 채우는 로컬 브리지.
웹(index.html)이 만든 완성 프롬프트(확정 사주 데이터 + 주제 지시)를 받아
`claude -p`(Claude Code 헤드리스)로 실행하고 생성문을 돌려준다.

```
[웹] 그라운딩 컨텍스트 + 주제 프롬프트 만들기
   └─POST /deep {prompt}──▶ [이 워커] ──stdin──▶ claude -p ──▶ 생성문
                          ◀──{ok,text}──┘
[웹] JSON 파싱 → 렌더 + 입력해시 캐싱. 워커 없으면 조용히 템플릿 폴백.
```

## 실행 (전제: `claude` 로그인 되어 있어야 함)
```bash
# 저장소 루트에서
python ai_worker/server.py
#  → http://127.0.0.1:8788/deep 에서 대기
```
그 상태로 웹을 **localhost에서** 열면(예: `python -m http.server 8931`) AI가 자동 작동한다.
(웹은 기본 엔드포인트 `http://127.0.0.1:8788/deep` 를 부른다.)

### 옵션
| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `YG_AI_PORT` | 8788 | 포트 |
| `YG_AI_TOKEN` | (없음) | 있으면 요청의 `token` 과 일치해야 처리 |
| `YG_CLAUDE_CMD` | `claude -p` | 실행 명령 |
| `YG_AI_TIMEOUT` | 120 | 초 |

```bash
python ai_worker/server.py --mock   # claude 안 부르고 에코(플러밍 테스트)
```

## 중요한 특성
- **안전 폴백**: 워커가 꺼져 있거나 못 미치면 웹은 기존 템플릿을 그대로 보여준다(에러 없음).
  → 배포본(Vercel https)을 낯선 사람이 열면 이 로컬 워커에 못 닿아 **자동으로 템플릿**.
  AI는 워커가 도는 **내 로컬(localhost)** 에서만 켜진다 = 안전한 실험 롤아웃.
- **캐싱**: 같은 입력(이름·생년시·MBTI·관계)은 브라우저 localStorage에 캐시 → 재생성·편차 없음.
- 프롬프트 로직은 전부 `index.html`(`buildDeepPrompt`/`buildFusionPrompt`)에 있다. 이 워커는 손댈 일이 거의 없다.

## 배포본에서 AI를 쓰려면 (선택, 소규모 시딩용)
1. 워커를 켠 채 터널을 연다: `cloudflared tunnel --url http://127.0.0.1:8788`
2. 배포된 페이지 브라우저 콘솔에서:
   ```js
   localStorage.setItem('yg_ai_endpoint','https://<터널주소>/deep')
   ```
   (PC가 켜져 있는 동안만 작동. 공개 확장은 Vercel serverless + Claude API 로 승격 권장.)

## AI 끄기 (템플릿만)
```js
localStorage.setItem('yg_ai_off','1')   // 다시 켜기: localStorage.removeItem('yg_ai_off')
```
