# 여덟 글자 · AI 워커 + cloudflared 터널 한 번에 (PowerShell)
# 사용: 저장소 루트에서  →  ./ai_worker/start.ps1
# 끝내기: 이 창에서 Ctrl+C (워커/터널 함께 종료)

$ErrorActionPreference = "Stop"
$env:YG_AI_TOKEN = "yg8glp-2026-k9f3a7q"   # index.html AI_TOKEN 과 반드시 일치

Write-Host "▶ 워커 시작 (127.0.0.1:8788)..." -ForegroundColor Cyan
$worker = Start-Process python -ArgumentList "ai_worker/server.py" -PassThru -NoNewWindow

Start-Sleep -Seconds 2
Write-Host "▶ cloudflared 터널 시작 (아래 https URL 을 확인하세요)..." -ForegroundColor Cyan
Write-Host "  ※ URL 이 지난번과 다르면, 그 주소를 저(Claude)에게 알려주면 배포에 반영합니다." -ForegroundColor Yellow
try {
    cloudflared tunnel --url http://127.0.0.1:8788 --protocol http2
} finally {
    Write-Host "■ 종료 중: 워커도 함께 종료합니다." -ForegroundColor DarkGray
    if ($worker -and !$worker.HasExited) { Stop-Process -Id $worker.Id -Force }
}
