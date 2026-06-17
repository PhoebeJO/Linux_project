# 企業級 IT 營運戰情室

> 用 Prometheus + Grafana + Docker 打造的監控平台，同時整合學生生活工具與兩個量化實驗。
> Linux 與邊緣運算 期末專題

---

## 30 秒看懂這個專案

| 問題 | 回答 |
|------|------|
| **這是什麼？** | 一套跑在 Docker 上的伺服器監控系統，能即時偵測 CPU / 記憶體 / 容器異常，自動推播 Telegram 告警 |
| **跟學生有什麼關係？** | 我們把同一套監控架構延伸成學生工具：番茄鐘、作業倒數、股價追蹤、天氣、AI 新聞、深夜提醒 |
| **實驗做了什麼？** | 兩個量化實驗：① 告警端到端延遲測量（12 組參數 × 3 次）② cgroups CPU 限制對 API 效能的影響 |
| **技術核心？** | Docker Compose 編排 8 個容器、Prometheus 時序資料庫、Grafana 視覺化、Alertmanager 告警、自製 Python Exporter |

---

## 快速開始（3 步驟）

```powershell
# 1. 確認 Docker Desktop 正在跑（右下角鯨魚圖示為綠色）
docker --version

# 2. 進入專案 → 一鍵啟動
cd C:\Users\phoeb\Documents\monitoring-stack
docker-compose up -d

# 3. 打開瀏覽器
#    入口頁面：http://localhost:8888
#    Grafana：  http://localhost:3000（帳密 admin / admin）
```

第一次執行會下載約 1.5 GB 映像檔，需要 2~5 分鐘。

> **Windows 使用者注意**：下載期間不要點擊 PowerShell 視窗內部，否則會進入「選取模式」導致暫停。若標題出現「**選取**」字樣，按 `Enter` 即可恢復。

---

## 目錄

1. [系統架構](#系統架構)
2. [所有服務一覽](#所有服務一覽)
3. [環境需求](#環境需求)
4. [安裝與啟動](#安裝與啟動)
5. [功能說明](#功能說明)
   - [監控戰情室](#監控戰情室)
   - [學生工具](#學生工具)
   - [遊戲專區](#遊戲專區)
6. [實驗設計](#實驗設計)
   - [實驗一：告警延遲測量](#實驗一告警端到端延遲測量)
   - [實驗二：cgroups CPU 限制](#實驗二cgroups-cpu-限制實驗)
7. [Telegram 告警設定](#telegram-告警設定)
8. [Grafana 使用指南](#grafana-使用指南)
9. [常見問題排解](#常見問題排解)
10. [日常維運指令](#日常維運指令)
11. [專案結構](#專案結構)
12. [安全聲明](#安全聲明)
13. [技術選型理由](#技術選型理由)

---

## 系統架構

```
                         使用者
                    ┌──────┴──────┐
                    ▼             ▼
              瀏覽器入口      Telegram
             (localhost)      (手機告警)
                    │             ▲
    ┌───────────────┼─────────────┤
    │               │             │
    ▼               ▼             │
┌────────┐   ┌──────────┐   ┌────┴───────┐
│ Portal │   │ Grafana  │   │Alertmanager│
│ :8888  │   │  :3000   │   │   :9093    │
└────────┘   └────┬─────┘   └────▲───────┘
                  │              │ 告警觸發
                  │ 查詢資料     │
                  ▼              │
            ┌────────────────────┴───┐
            │      Prometheus        │
            │    :9090 時序資料庫     │
            │    + 告警規則引擎      │
            └──┬─────┬─────┬─────┬──┘
               │     │     │     │  抓取指標(每15s)
               ▼     ▼     ▼     ▼
           ┌──────┐┌───┐┌─────┐┌────────┐
           │ Node ││cAd││Stud-││ Snake  │
           │ Exp. ││vis││ent  ││Backend │
           │:9100 ││or ││Exp. ││ :5000  │
           │主機  ││:80││:8001││ Flask  │
           │監控  ││80 ││學生 ││ 遊戲   │
           └──────┘└───┘│工具 │└────────┘
                        └─────┘
```

### 元件職責

| 元件 | Port | 功能 |
|------|------|------|
| **Prometheus** | 9090 | 時序資料庫，每 15 秒抓取所有 Exporter 的指標，依規則觸發告警 |
| **Grafana** | 3000 | 視覺化儀表板，呈現監控圖表、學生工具、遊戲 |
| **Alertmanager** | 9093 | 接收 Prometheus 告警，分派到 Telegram，支援靜音、分組 |
| **Node Exporter** | 9100 | 收集主機 CPU / 記憶體 / 磁碟 / 網路指標 |
| **cAdvisor** | 8080 | 收集 Docker 容器的資源使用狀況（含 cgroups 指標） |
| **Student Exporter** | 8001 | 自製 Python 服務：番茄鐘、作業管理、股價、天氣、新聞、深夜提醒 |
| **Snake (Nginx)** | 8888 | 入口頁面 + 貪吃蛇遊戲前端 |
| **Snake Backend** | 5000 | 貪吃蛇排行榜 API + 問題回報 + Prometheus 指標 |

---

## 所有服務一覽

| 服務 | 網址 | 帳密 | 說明 |
|------|------|------|------|
| **入口頁面** | http://localhost:8888 | 無 | 所有功能的導覽入口 |
| **Grafana** | http://localhost:3000 | admin / admin | 監控儀表板、學生工具、遊戲 |
| **番茄鐘** | http://localhost:8001 | 無 | 25 分鐘專注計時 + Telegram 通知 |
| **作業管理** | http://localhost:8001/admin | 無 | 新增/編輯作業截止日 + 深夜提醒設定 |
| **股價監控** | http://localhost:8001/stocks | 無 | 台股/美股即時追蹤 |
| **天氣預報** | http://localhost:8001/weather | 無 | 即時天氣 + 6 小時預報 |
| **AI 新聞** | http://localhost:8001/news | 無 | AI 科技新聞 + 一鍵推送 Telegram |
| Prometheus | http://localhost:9090 | 無 | 原始指標查詢（進階用） |
| Alertmanager | http://localhost:9093 | 無 | 告警狀態管理（進階用） |
| cAdvisor | http://localhost:8080 | 無 | 容器監控原始介面（進階用） |

---

## 環境需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Windows 10/11、macOS、Linux |
| Docker Desktop | 已安裝且正在執行 |
| 記憶體 | 至少 4 GB |
| 磁碟 | 至少 5 GB |
| 網路 | 首次啟動需下載映像檔 |
| Port | 3000、5000、8001、8080、8888、9090、9093、9100 需空閒 |

---

## 安裝與啟動

### 1. 安裝 Docker Desktop

Windows 使用者到 [Docker 官網](https://www.docker.com/products/docker-desktop/) 下載安裝，安裝完需重開機。

驗證：
```powershell
docker --version
docker ps            # 看到空表頭（不是錯誤）= Docker 就緒
```

### 2. Clone 專案

```powershell
git clone https://github.com/PhoebeJO/Linux_project.git
cd Linux_project
```

### 3. 設定 Telegram（可選，跳過也能用）

複製範本並填入你的 Bot Token 和 Chat ID（詳見 [Telegram 告警設定](#telegram-告警設定)）：

```powershell
copy alertmanager\alertmanager.yml.example alertmanager\alertmanager.yml
# 用文字編輯器打開 alertmanager\alertmanager.yml，填入 bot_token 和 chat_id
```

同樣設定 Student Exporter 的環境變數：
```powershell
copy student_tools\.env.example student_tools\.env
# 填入 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID
```

### 4. 啟動所有服務

```powershell
docker-compose up -d
```

### 5. 確認容器狀態

```powershell
docker-compose ps
```

應看到 8 個服務都是 `Up` 狀態：

```
NAME               STATUS    PORTS
prometheus         Up        0.0.0.0:9090->9090/tcp
grafana            Up        0.0.0.0:3000->3000/tcp
node-exporter      Up        0.0.0.0:9100->9100/tcp
cadvisor           Up        0.0.0.0:8080->8080/tcp
alertmanager       Up        0.0.0.0:9093->9093/tcp
student-exporter   Up        0.0.0.0:8001->8001/tcp
snake              Up        0.0.0.0:8888->80/tcp
snake-backend      Up        0.0.0.0:5000->5000/tcp
```

### 6. 開始使用

打開 http://localhost:8888 — 這是入口頁面，所有功能都能從這裡進入。

---

## 功能說明

### 監控戰情室

企業級 IT 基礎設施監控，使用業界標準工具鏈：

| 功能 | 說明 |
|------|------|
| CPU / 記憶體 / 磁碟監控 | Node Exporter 收集主機指標，Grafana 即時呈現 |
| Docker 容器監控 | cAdvisor 追蹤每個容器的 CPU、記憶體、網路 I/O |
| 自動告警 | CPU > 5%、記憶體 > 85%、磁碟 > 85%、服務離線 → Telegram 通知 |
| 告警解除通知 | 問題恢復後自動發送「已解除」通知 |
| 靜音功能 | 在 Alertmanager (:9093) 設定特定告警暫時靜音 |

#### 告警規則一覽

| 告警名稱 | 觸發條件 | 等待時間 | 嚴重度 |
|----------|----------|----------|--------|
| HighCpuUsage | CPU > 5% | 30s | critical |
| HighMemoryUsage | 記憶體 > 85% | 1m | warning |
| LowDiskSpace | 磁碟 > 85% | 1m | warning |
| InstanceDown | 服務離線 | 30s | critical |
| HomeworkDeadlineSoon | 作業 < 24h | 0s | warning |
| HomeworkDeadlineUrgent | 作業 < 3h | 0s | critical |
| StockPriceDrop | 股價跌幅 > 閾值 | 2m | warning |
| StockPriceRise | 股價漲幅 > 5% | 2m | info |
| LateNightUsage | 在設定的深夜時段使用電腦 | 1m | info |

### 學生工具

把 Prometheus 監控架構延伸到學生日常生活，所有工具的指標都進入同一條 Prometheus → Alertmanager → Telegram 的告警管線：

| 工具 | 網址 | 功能 |
|------|------|------|
| **番茄鐘** | :8001 | 25 分鐘專注 → 5 分鐘休息自動循環，每 4 輪長休息。完成時 Telegram 通知，自動記錄學習時數 |
| **作業管理** | :8001/admin | 新增/編輯/刪除作業截止日，設定深夜使用提醒時段。到期前自動告警 |
| **股價監控** | :8001/stocks | 追蹤台股（2330.TW 台積電）、美股（AAPL、TSLA），台灣慣例紅漲綠跌，大漲大跌 Telegram 通知 |
| **天氣預報** | :8001/weather | 即時溫度/濕度/風速，6 小時預報卡片，降雨 > 30% 自動提醒帶傘。可切換城市 |
| **AI 新聞** | :8001/news | 自動抓取 Google News AI、TechCrunch AI 的 RSS，一鍵推送到 Telegram |
| **深夜提醒** | 自動觸發 | 在設定時段（預設 0:00~3:00）瀏覽器跳出全螢幕提醒 + 音效 + 系統通知 |

#### 學生工具的 Prometheus 指標

所有工具都輸出標準 Prometheus 指標，可在 Grafana 查詢或設定告警：

```
pomodoro_today_count                        今日完成的番茄鐘數
pomodoro_today_minutes                      今日專注分鐘數
pomodoro_week_total                         本週總番茄鐘數
homework_deadline_hours_remaining{task="…"} 作業剩餘小時數
late_night_active                           是否在深夜時段 (0/1)
stock_price{symbol="2330.TW"}               即時股價
stock_change_pct{symbol="…"}                股價漲跌幅 %
```

### 遊戲專區

| 功能 | 網址 | 說明 |
|------|------|------|
| 貪吃蛇 | :8888/snake.html | 經典遊戲，分數自動存入排行榜 |
| 問題回報 | :8888/report.html | 填寫 Bug 回報，自動推送 Telegram 通知管理員 |

遊戲也有 Prometheus 指標（`snake_games_total`、`snake_high_score`、`snake_avg_score`），可在 Grafana 查看遊戲數據分析。

---

## 實驗設計

本專案不只是「裝得起來」的實作，我們把監控平台當作實驗儀器，量化研究了兩個維運問題。

### 實驗一：告警端到端延遲測量

#### 研究問題

從「事故發生」到「手機收到 Telegram 通知」要多久？延遲由哪些環節組成？調整哪個參數影響最大？

#### 延遲分解

```
T0 ──────→ T1 ──────→ T2 ──────→ T3
壓測啟動    Prometheus   告警進入    Telegram
(事故發生)  第一次偵測到  firing 狀態  訊息送達

偵測延遲     確認延遲     通知延遲
(scrape      (for 決定)   (Alertmanager
 interval                  + Telegram API)
 決定)

端到端延遲 = T3 - T0（使用者真正在乎的數字）
```

#### 變因設計

| 類型 | 變因 | 取值 |
|------|------|------|
| **操縱變因** | scrape_interval | 5s / 15s / 30s / 60s |
| **操縱變因** | for（告警確認等待時間） | 0s / 30s / 1m |
| **控制變因** | 壓測指令 | `stress --cpu 4 --timeout 90s`（固定） |
| **控制變因** | CPU 告警閾值 | 5%（固定，保證觸發） |
| **控制變因** | Alertmanager group_wait | 10s（固定） |

→ 4 × 3 = **12 組設定**，每組重複 3 次取平均 = **36 次測量**

#### 時間戳取得方式

| 時間戳 | 取得方式 |
|--------|---------|
| T0（壓測啟動） | `docker inspect stress --format '{{.State.StartedAt}}'` |
| T1（首次偵測） | Prometheus query API 回查 CPU 時序資料，找第一次超標的時間點 |
| T2（告警 firing） | Prometheus `/api/v1/alerts` 的 `activeAt` 欄位 |
| T3（Telegram 送達） | Telegram 訊息時間戳 |

#### 實驗步驟（單次流程）

```powershell
# 1. 修改 prometheus.yml 的 scrape_interval 和 alert.rules.yml 的 for
# 2. 熱重載 Prometheus（不重啟容器）
curl -X POST http://localhost:9090/-/reload

# 3. 確認設定生效
curl http://localhost:9090/api/v1/status/config

# 4. 記錄 T0 並啟動壓測
docker run --rm -d --name stress polinux/stress stress --cpu 4 --timeout 90s
docker inspect stress --format '{{.State.StartedAt}}'

# 5. 輪詢告警狀態，等待 firing
docker exec prometheus wget -qO- localhost:9090/api/v1/alerts

# 6. 回查 Prometheus 時序資料找 T1
# 7. 從 Telegram 訊息記錄 T3
# 8. 冷卻 2 分鐘，跑下一組
```

#### 預期結果

**表 1：偵測延遲 vs scrape_interval（固定 for=30s）**

| scrape_interval | 平均偵測延遲 (T1-T0) | 理論值 (interval/2) |
|-----------------|----------------------|---------------------|
| 5s  | 待測 | ~2.5s  |
| 15s | 待測 | ~7.5s  |
| 30s | 待測 | ~15s   |
| 60s | 待測 | ~30s   |

**表 2：端到端延遲全矩陣（12 組）**

| scrape \ for | 0s | 30s | 1m |
|---|---|---|---|
| 5s | 待測 | 待測 | 待測 |
| 15s | 待測 | 待測 | 待測 |
| 30s | 待測 | 待測 | 待測 |
| 60s | 待測 | 待測 | 待測 |

**表 3：誤報率（正常使用 30 分鐘）**

| scrape × for | 誤報次數 |
|---|---|
| 5s × 0s | 預期最多 |
| 60s × 1m | 預期為 0 |

#### 預期結論

- 端到端延遲的最大組成是 `for` 時間，其次是 `scrape_interval`
- 最佳平衡點預期在 **15s × 30s**（業界預設值），我們用實驗驗證其合理性
- `scrape 5s + for 0s` 反應最快但誤報嚴重（開個 Chrome 就告警），不可用於生產

#### Docker / Linux 技術清單

| 步驟 | 使用的技術 |
|------|-----------|
| 故障注入 | `docker run polinux/stress` — 容器化壓測，主機零污染 |
| 設定變更 | Prometheus HTTP 熱重載 `POST /-/reload`，不重啟容器 |
| 時間戳取得 | `docker inspect --format '{{.State.StartedAt}}'` |
| 容器內查詢 | `docker exec prometheus wget` 進容器打 API |
| 日誌驗證 | `docker-compose logs --timestamps alertmanager` |

---

### 實驗二：cgroups CPU 限制實驗

#### 研究問題

Docker 的 CPU 限制底層是 Linux cgroups 的 CFS quota 機制。當容器被限制 CPU 時，對應用程式的效能代價是什麼？

#### 背景知識：CFS Quota 原理

```
Linux CFS（Completely Fair Scheduler）以 100ms 為一個週期

cpus: 0.5 = 每 100ms 只給容器 50ms 的 CPU 時間
            → 配額用完 → 核心強制凍結容器所有執行緒 → 等下個週期

這就是為什麼被限制的容器「卡卡的」——不是慢，是週期性被凍結
```

對應的 cAdvisor 指標：

| 指標 | 意義 |
|------|------|
| `container_cpu_cfs_throttled_seconds_total` | 被凍結的累計秒數 |
| `container_cpu_cfs_throttled_periods_total` | 被凍結的週期數 |
| `container_cpu_cfs_periods_total` | 總週期數 |
| throttle 比例 | = throttled_periods / periods |

#### 變因設計

| 類型 | 變因 | 取值 |
|------|------|------|
| **操縱變因** | snake-backend 的 cpus 限制 | 0.25 / 0.5 / 1.0 / 不限制（對照組） |
| **控制變因** | 負載測試參數 | `hey -z 60s -c 50`（固定 50 併發、60 秒） |
| **控制變因** | 測試端點 | `/api/leaderboard`（固定） |

#### 測量指標

| 指標 | 來源 |
|------|------|
| API 平均延遲 / p50 / p95 / p99 | hey 負載測試工具輸出 |
| 每秒請求數 (RPS) | hey 輸出 |
| throttle 比例 | cAdvisor → Prometheus → Grafana |
| 容器實際 CPU 用量 | `docker stats` + cAdvisor 交叉驗證 |

#### 實驗步驟（單組流程）

```powershell
# 1. 改 docker-compose.yml 加 cpus 限制，重建容器
docker-compose up -d --force-recreate snake-backend

# 2. 確認限制生效（讀 Linux cgroups 實際值）
docker inspect snake-backend --format '{{.HostConfig.NanoCpus}}'

# 3. 跑負載測試（用容器跑 hey，接同一個 Docker 網路）
docker run --rm --network monitoring williamyeh/hey -z 60s -c 50 http://snake-backend:5000/api/leaderboard

# 4. 同時在 Grafana 看 throttling 指標即時飆升（截圖）

# 5. 記錄 hey 的延遲分布 + Grafana 的 throttle 比例

# 6. 換下一組限制值，重複
```

#### 預期結果

**表 4：CPU 限制 vs API 效能**

| cpus 限制 | RPS | p50 延遲 | p99 延遲 | throttle % |
|-----------|-----|----------|----------|------------|
| 0.25 | 預期最低 | 待測 | 預期暴增 | 預期 >80% |
| 0.5 | 待測 | 待測 | 待測 | 待測 |
| 1.0 | 待測 | 待測 | 待測 | 預期 <10% |
| 不限制 | 預期最高 | 待測 | 預期最低 | 0% |

核心視覺：Grafana throttling 指標的時序圖，四組疊在一起比較。

#### 預期結論

- CPU 限制不是「線性變慢」，而是「週期性凍結」—— **p99 延遲的惡化遠比 p50 嚴重**
- throttle 比例與 p99 延遲高度相關
- 連結真實世界：這就是 Kubernetes 資源限制設太低時服務變卡的原因，我們用實驗重現並量化了這個現象

#### Docker / Linux 技術清單

| 步驟 | 使用的技術 |
|------|-----------|
| 資源限制 | `docker-compose cpus:` → 底層寫入 Linux cgroups `cfs_quota_us` |
| 限制驗證 | `docker inspect --format '{{.HostConfig.NanoCpus}}'` |
| 負載測試 | `docker run williamyeh/hey` — 容器化壓測，接同一個 Docker 網路 |
| 數據收集 | cAdvisor 讀 cgroups → Prometheus → Grafana |
| 雙重驗證 | `docker stats`（CLI 直讀 cgroups）vs cAdvisor（走監控管線）交叉比對 |

#### 重要補充：WSL2 架構

Windows + Docker Desktop 是跑在 WSL2 裡，cgroups 由 WSL2 的 Linux 核心管理。這代表我們的實驗確實是在操作 Linux 核心的 cgroups 機制，只是透過 WSL2 虛擬化層運行。

---

## Telegram 告警設定

### 步驟 1：建立 Telegram Bot

1. 在 Telegram 搜尋 `@BotFather` → 開啟對話
2. 輸入 `/newbot` → 依提示命名
3. 複製回傳的 **Token**（格式：`123456789:ABCdefGhIJK...`）

### 步驟 2：取得 Chat ID

1. 搜尋 `@userinfobot` → 按 Start → 取得你的數字 ID
2. **重要**：回去跟你的 Bot 傳一句話（否則 Bot 無法主動發訊息給你）

### 步驟 3：填入設定檔

```powershell
# 複製範本
copy alertmanager\alertmanager.yml.example alertmanager\alertmanager.yml
copy student_tools\.env.example student_tools\.env
```

編輯 `alertmanager\alertmanager.yml`，把 `YOUR_BOT_TOKEN` 和 `YOUR_CHAT_ID` 換成真實值。

編輯 `student_tools\.env`，同樣填入 Token 和 Chat ID。

> **注意**：用 VS Code 或 Notepad++ 編輯，**不要用 Windows 記事本**（會破壞 UTF-8 編碼）。

### 步驟 4：重啟服務

```powershell
docker-compose restart alertmanager student-exporter
```

---

## Grafana 使用指南

### 登入

打開 http://localhost:3000

| 欄位 | 填入 |
|------|------|
| Email or username | `admin`（不要填 Email） |
| Password | `admin` |

首次登入會要求改密碼，可以按 **Skip** 跳過。

### 預設儀表板

系統已自動載入以下儀表板（不需手動匯入）：

| 資料夾 | 儀表板 | 內容 |
|--------|--------|------|
| 根目錄 | Docker War Room | 容器監控總覽 |
| 學生工具 | 學生工具總覽 | 番茄鐘、作業倒數、深夜提醒狀態 |
| 學生工具 | 番茄鐘 | 今日/本週專注時間統計 |
| 學生工具 | 作業管理 | 作業截止倒數 |
| 學生工具 | 學習統計 | 每日/每週學習時數圖表 |
| 學生工具 | 股價監控 | 股價走勢 + 漲跌幅 |
| 學生工具 | 天氣預報 | 即時天氣資訊 |
| 學生工具 | AI 新聞 | 最新 AI 科技新聞 |
| 遊戲 | 貪吃蛇 | 遊戲嵌入 + 排行榜 |
| 遊戲 | 問題回報 | Bug 回報介面 |

### 匯入社群儀表板（可選）

如果想要更完整的主機監控：

1. 左側 → **Dashboards** → **New** → **Import**
2. 輸入 ID `1860`（Node Exporter Full，30+ 個圖表）
3. 資料源選 `Prometheus` → Import

---

## 常見問題排解

| 症狀 | 原因 | 解決方法 |
|------|------|----------|
| `localhost:3000` 連不上 | Grafana 容器沒跑 | `docker-compose ps` 檢查 → `docker-compose up -d` 重啟 |
| 登入失敗 "Invalid password" | 輸入了 Email 而非帳號 | username 填 `admin`，密碼也是 `admin` |
| 壓測後 Telegram 沒告警 | Token/ChatID 錯誤或沒跟 Bot 對話過 | 檢查 `alertmanager.yml` → 跟 Bot 傳訊 → `docker-compose restart alertmanager` |
| 深夜提醒白天觸發 | 容器時區是 UTC | 確認 `docker-compose.yml` 有 `TZ=Asia/Taipei` |
| 股價新增失敗 | `stocks.yml` 編碼問題 | 用 VS Code 以 UTF-8 重新儲存 |
| PowerShell 下載卡住 | 點到視窗進入選取模式 | 按 `Enter` 或 `Esc` 恢復 |
| Port 被占用 | 其他程式占了同一個 port | `netstat -ano \| findstr :3000` 找出 PID → 改 compose 的 port 對映 |
| 磁碟空間不足 | Prometheus 累積資料 | `docker-compose down -v` + `docker system prune -a` |
| Grafana 儀表板消失 / 404 | datasource UID 衝突 | 確認 dashboard JSON 用 datasource name `"Prometheus"` 而非 UID |
| Git merge 衝突 | 多人同時改 docker-compose.yml | 手動逐行比對，保留雙方 services 定義 |

---

## 日常維運指令

| 指令 | 用途 |
|------|------|
| `docker-compose up -d` | 啟動所有服務（背景執行） |
| `docker-compose down` | 停止並移除所有容器（保留資料） |
| `docker-compose down -v` | 停止並移除容器和資料卷（資料清空） |
| `docker-compose ps` | 查看容器狀態 |
| `docker-compose logs -f grafana` | 即時查看特定服務日誌 |
| `docker-compose restart prometheus` | 重啟單一服務 |
| `docker-compose up -d --build student-exporter` | 重建並重啟（改了程式碼後） |
| `curl -X POST http://localhost:9090/-/reload` | 熱重載 Prometheus 設定（不重啟容器） |

---

## 專案結構

```
monitoring-stack/
├── docker-compose.yml                    # 主編排檔：8 個服務定義
├── README.md                             # 本文件
├── 使用手冊.md                            # 詳細操作手冊（原版）
├── .gitignore                            # 排除機密檔案
│
├── prometheus/
│   ├── prometheus.yml                    # 抓取設定（scrape_interval: 15s）
│   ├── alert.rules.yml                   # 系統告警（CPU/記憶體/磁碟/離線）
│   └── student_alert.rules.yml           # 學生工具告警（作業/股價/深夜）
│
├── alertmanager/
│   ├── alertmanager.yml                  # Telegram 設定（不上傳，在 .gitignore）
│   └── alertmanager.yml.example          # 範本檔（安全，可上傳）
│
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml            # 自動掛載 Prometheus
│       └── dashboards/
│           ├── dashboards.yml            # Provider 設定（3 個資料夾）
│           ├── docker-war-room.json      # Docker 監控儀表板
│           ├── json/                     # 學生工具儀表板（7 個 JSON）
│           └── games/                    # 遊戲儀表板（2 個 JSON）
│
├── student_tools/
│   ├── Dockerfile                        # Python 3.11 容器建置
│   ├── student_exporter.py               # 主程式：HTTP 伺服器 + Prometheus 指標
│   ├── features.py                       # 天氣 / 學習統計 / 新聞模組
│   ├── pomodoro.html                     # 番茄鐘介面
│   ├── admin.html                        # 作業管理 + 深夜提醒設定
│   ├── stocks.html                       # 股價監控介面
│   ├── weather.html                      # 天氣預報介面
│   ├── news.html                         # AI 新聞介面
│   ├── late-night-alert.js               # 深夜提醒（全螢幕+音效+系統通知）
│   ├── deadlines.yml                     # 作業資料（持久化）
│   ├── settings.yml                      # 深夜提醒設定（持久化）
│   ├── stocks.yml                        # 股票清單（持久化）
│   ├── study_log.json                    # 學習紀錄（持久化）
│   ├── .env                              # 環境變數（不上傳）
│   └── .env.example                      # 環境變數範本
│
├── snake/
│   ├── index.html                        # 入口頁面（localhost:8888）
│   ├── snake.html                        # 貪吃蛇遊戲
│   └── report.html                       # 問題回報
│
├── backend/
│   ├── app.py                            # Flask API（排行榜+回報+指標）
│   └── requirements.txt                  # Python 依賴
│
└── experiments/                          # 實驗腳本與數據
    ├── run_latency_exp.ps1               # 實驗一自動化腳本
    ├── run_cgroups_exp.ps1               # 實驗二自動化腳本
    ├── latency_results.csv               # 實驗一結果
    └── cgroups_results.csv               # 實驗二結果
```

---

## 安全聲明

本專案採用**機密分離原則 (Separation of Secrets)**：

- `alertmanager/alertmanager.yml`（含 Telegram Bot Token）**不納入版本控制**
- `student_tools/.env`（含環境變數）**不納入版本控制**
- 以上檔案均在 `.gitignore` 中，僅提供 `.example` 範本檔
- 使用者需自行複製範本並填入個人憑證

---

## 技術選型理由

| 選擇 | 為什麼？ |
|------|---------|
| **Docker Compose** | 8 個服務手動安裝太複雜，Compose 一個指令全部啟動，方便在不同電腦重現 |
| **Prometheus** | 業界雲原生監控標準，pull-based 架構天然適合容器，與 Grafana 整合最好 |
| **Grafana** | 最成熟的開源視覺化平台，支援 provisioning 自動載入儀表板 |
| **自製 Python Exporter** | 市面上沒有「學生生活指標」的 Exporter，自己寫讓所有工具統一進入 Prometheus 告警管線 |
| **Windows + WSL2** | 課程環境限制，但 Docker Desktop 透過 WSL2 運行 Linux 核心，cgroups 實驗有效 |
| **Telegram** | 免費、API 簡單、同學都有帳號，最低摩擦力的告警管道 |
