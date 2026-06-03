# 監控戰情室一鍵安裝腳本
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  企業級 IT 監控戰情室 - 安裝程式" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 確認 Docker 是否運行
Write-Host "[ 1/3 ] 確認 Docker Desktop 是否運行..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "        Docker 運行正常" -ForegroundColor Green
} catch {
    Write-Host "        [錯誤] Docker Desktop 未啟動，請先開啟 Docker Desktop 再執行本腳本。" -ForegroundColor Red
    exit 1
}

# 處理 alertmanager.yml
Write-Host ""
Write-Host "[ 2/3 ] 設定 Alertmanager..." -ForegroundColor Yellow

$alertmanagerConfig = "alertmanager\alertmanager.yml"
$alertmanagerExample = "alertmanager\alertmanager.yml.example"

if (Test-Path $alertmanagerConfig) {
    Write-Host "        alertmanager.yml 已存在，跳過建立。" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "        請輸入 Telegram Bot Token（從 @BotFather 取得）" -ForegroundColor Cyan
    Write-Host "        直接按 Enter 跳過（之後可手動填入）：" -ForegroundColor Gray
    $botToken = Read-Host "        Bot Token"

    Write-Host ""
    Write-Host "        請輸入你的 Telegram Chat ID（從 @userinfobot 取得）" -ForegroundColor Cyan
    Write-Host "        直接按 Enter 跳過（之後可手動填入）：" -ForegroundColor Gray
    $chatId = Read-Host "        Chat ID"

    # 複製範本
    Copy-Item $alertmanagerExample $alertmanagerConfig

    # 填入 token 和 chat_id（如果有輸入）
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $content = (Get-Content $alertmanagerConfig -Raw -Encoding UTF8)
    if ($botToken -ne "") {
        $content = $content -replace "YOUR_BOT_TOKEN_HERE", $botToken
    }
    if ($chatId -ne "" -and $chatId -match '^\d+$') {
        $content = $content -replace "chat_id: 0", "chat_id: $chatId"
    }
    [System.IO.File]::WriteAllText((Resolve-Path $alertmanagerConfig), $content, $utf8NoBom)

    if ($botToken -ne "" -and $chatId -ne "") {
        Write-Host "        Telegram 設定完成！" -ForegroundColor Green
    } else {
        Write-Host "        alertmanager.yml 已建立（Telegram 設定待填入）。" -ForegroundColor Yellow
    }
}

# 啟動所有服務
Write-Host ""
Write-Host "[ 3/3 ] 啟動所有監控服務..." -ForegroundColor Yellow
docker-compose up -d

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  安裝完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Grafana         : http://localhost:3000  (admin / admin)" -ForegroundColor Cyan
Write-Host "  Prometheus      : http://localhost:9090" -ForegroundColor Cyan
Write-Host "  Alertmanager    : http://localhost:9093" -ForegroundColor Cyan
Write-Host ""
