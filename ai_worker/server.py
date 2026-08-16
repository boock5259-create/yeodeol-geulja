#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
여덟 글자 · AI 심층분석 로컬 헤드리스 브리지
================================================
웹(index.html)이 만든 '완성 프롬프트'를 POST 받아 `claude -p`(헤드리스)로 실행하고
생성문을 돌려준다. 프롬프트 로직은 전부 웹에 있고 이 워커는 단순 브리지다.

실행 (Git Bash 또는 PowerShell, claude 로그인 되어 있어야 함):
    python ai_worker/server.py
    # 옵션: 포트/토큰/모의(mock) 모드
    #   YG_AI_PORT=8788  YG_AI_TOKEN=선택   YG_CLAUDE_CMD="claude -p"
    #   python ai_worker/server.py --mock     # claude 안 부르고 에코(플러밍 테스트용)

웹에서 가리키는 기본 엔드포인트: http://127.0.0.1:8788/deep
배포(https) 페이지에서 쓰려면 cloudflared/ngrok 터널 URL을
브라우저 콘솔에서: localStorage.setItem('yg_ai_endpoint','https://<터널>/deep')
"""
import json, os, sys, subprocess, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT   = int(os.environ.get("YG_AI_PORT", "8788"))
TOKEN  = os.environ.get("YG_AI_TOKEN", "")          # 비우면 토큰 검사 안 함(로컬 전용이라 OK)
_HERE = os.path.dirname(os.path.abspath(__file__))
_EMPTY_MCP = os.path.join(_HERE, "empty-mcp.json")  # 빈 MCP 설정 = 사용자 MCP서버(Canva·Figma·Notion 등) 로딩 스킵
# 모델: Sonnet5(품질/속도 균형). 빠르게 하려면 YG_CLAUDE_CMD로 haiku 지정.
# --strict-mcp-config + 빈 mcp-config = 콜드스타트 ~11s→~4.5s (워커는 MCP 도구 안 씀)
# --disallowedTools: 순수 텍스트생성만 시킴(에이전트 툴 왕복·임시파일 생성 방지 → ~55s→~37s + 출력 깨끗)
_NO_TOOLS = "Bash Write Edit Read Glob Grep WebFetch WebSearch NotebookEdit TodoWrite Task"
CLAUDE = os.environ.get("YG_CLAUDE_CMD", f'claude -p --model claude-sonnet-5 --strict-mcp-config --mcp-config "{_EMPTY_MCP}" --disallowedTools {_NO_TOOLS}')
MOCK   = "--mock" in sys.argv
TIMEOUT= int(os.environ.get("YG_AI_TIMEOUT", "120"))
# ── 터널로 외부 노출 시 남용 방지 ──
SIGNATURE = os.environ.get("YG_AI_SIG", '여덟 글자')  # 앱이 만든 프롬프트에만 있는 서명(없으면 거부)
MAXLEN    = int(os.environ.get("YG_AI_MAXLEN", "12000"))
MAXCONC   = int(os.environ.get("YG_AI_MAXCONC", "3"))
_sema     = threading.BoundedSemaphore(MAXCONC)

def run_claude(prompt: str) -> str:
    """프롬프트를 stdin으로 claude -p 에 넣고 stdout 반환."""
    if MOCK:
        # 플러밍 테스트: 실제 생성 없이 그럴듯한 JSON 에코
        return json.dumps({"title": "🧪 (mock) 심층 리포트",
                           "body": "모의 응답이에요. 브리지 연결은 정상입니다.\n\n프롬프트 길이 %d자 수신." % len(prompt)},
                          ensure_ascii=False)
    # shell=True 로 PATH에서 claude(.cmd) 해석, 프롬프트는 stdin(따옴표/길이 문제 회피)
    p = subprocess.run(CLAUDE, input=prompt, shell=True, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "claude 실행 실패").strip()[:400])
    return (p.stdout or "").strip()

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        # 헬스체크
        self.send_response(200); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8"); self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "mock": MOCK}).encode("utf-8"))

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "bad json"})
        if TOKEN and data.get("token") != TOKEN:
            return self._json(401, {"ok": False, "error": "unauthorized"})
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return self._json(400, {"ok": False, "error": "empty prompt"})
        if len(prompt) > MAXLEN:
            return self._json(413, {"ok": False, "error": "prompt too long"})
        if SIGNATURE and SIGNATURE not in prompt:          # 앱이 만든 프롬프트가 아니면 거부
            return self._json(403, {"ok": False, "error": "bad signature"})
        if not _sema.acquire(blocking=False):              # 동시 실행 제한
            return self._json(429, {"ok": False, "error": "busy"})
        try:
            text = run_claude(prompt)
            self._json(200, {"ok": True, "text": text})
        except subprocess.TimeoutExpired:
            self._json(504, {"ok": False, "error": "claude timeout"})
        except Exception as e:
            self._json(500, {"ok": False, "error": str(e)[:400]})
        finally:
            _sema.release()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("[worker] " + (fmt % args) + "\n")

if __name__ == "__main__":
    print(f"[여덟글자 AI 워커] http://127.0.0.1:{PORT}/deep  (mock={MOCK}, cmd='{CLAUDE}')")
    print("  종료: Ctrl+C")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
