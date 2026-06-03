# 企業級 IT 營運戰情室 — 使用手冊

> 基於 Prometheus + Grafana + cAdvisor + Node Exporter + Alertmanager 的伺服器監控與自動告警系統

---

## 🔐 安全聲明

本專案採用業界標準的**機密分離原則 (Separation of Secrets)**：

- 凡是包含 API Token、密碼等機密的設定檔（如 `alertmanager.yml`），**一律不納入版本控制**，僅以範本檔 (`*.example`) 形式提供。
- 使用者需自行依範本建立本機設定檔並填入個人憑證，確保即使 repo 公開，敏感資訊也不會外洩。
- 詳見 `.gitignore` 與第 8 章 Telegram 告警設定。

---

## 目錄

1. [系統介紹](#1-系統介紹)
2. [系統架構](#2-系統架構)
3. [環境需求](#3-環境需求)
4. [安裝與啟動](#4-安裝與啟動)
5. [服務存取網址](#5-服務存取網址)
6. [Grafana 初始設定](#6-grafana-初始設定)
7. [匯入監控儀表板](#7-匯入監控儀表板)
8. [設定 Telegram 自動告警](#8-設定-telegram-自動告警)
9. [Demo 操作流程](#9-demo-操作流程)
10. [常見問題排解 (Troubleshooting)](#10-常見問題排解-troubleshooting)
11. [日常維運指令](#11-日常維運指令)

---

## 1. 系統介紹

本系統透過 Docker 貨櫃化技術，以零硬體成本建構一套主動式 IT 營運監控平台。目標：

- **即時監控**：CPU、記憶體、磁碟、網路、Docker 容器狀態
- **視覺化呈現**：透過 Grafana 提供企業級戰情儀表板
- **自動告警**：當系統異常時自動推播訊息至 Telegram
- **被動 → 主動**：從「系統掛掉才知道」轉為「預先告警，即時處理」

---

## 2. 系統架構

```
┌─────────────────────────────────────────────────────────┐
│                  使用者瀏覽器 / Telegram                  │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
               ▼                      ▼
       ┌──────────────┐       ┌──────────────┐
       │   Grafana    │       │ Alertmanager │
       │ (戰情儀表板) │       │ (告警分派)   │
       │  port:3000   │       │  port:9093   │
       └──────┬───────┘       └──────▲───────┘
              │                      │
              │  查詢數據            │  告警觸發
              ▼                      │
       ┌─────────────────────────────┴────────────┐
       │            Prometheus                     │
       │      (時序資料庫 + 告警規則引擎)          │
       │              port:9090                    │
       └────┬───────────────────────────────┬─────┘
            │                               │
            │  抓取主機指標                 │  抓取容器指標
            ▼                               ▼
     ┌──────────────┐               ┌──────────────┐
     │ Node Exporter│               │   cAdvisor   │
     │  (主機監控)  │               │ (容器監控)   │
     │  port:9100   │               │  port:8080   │
     └──────────────┘               └──────────────┘
```

### 各元件職責

| 元件 | 功能 |
|------|------|
| **Prometheus** | 時序資料庫，定期抓取各 Exporter 的指標並依規則觸發告警 |
| **Grafana** | 視覺化儀表板，呈現各種圖表 |
| **Node Exporter** | 收集主機的 CPU / 記憶體 / 磁碟 / 網路指標 |
| **cAdvisor** | 收集所有 Docker 容器的資源使用狀況 |
| **Alertmanager** | 接收 Prometheus 觸發的告警，分派到 Telegram / Email |

---

## 3. 環境需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Windows 10 / 11、macOS、Linux |
| Docker Desktop | 已安裝且正在執行（右下角小鯨魚圖示為綠色） |
| 可用記憶體 | 至少 4 GB |
| 可用磁碟 | 至少 5 GB（存放映像檔與監控數據） |
| 網際網路 | 第一次安裝需下載約 1.5 GB 的映像檔 |
| Port 占用檢查 | 確保 3000、8080、9090、9093、9100 未被其他服務占用 |

---

## 4. 安裝與啟動

### 4-1. 確認 Docker Desktop 已啟動

按 Windows 鍵 → 搜尋「Docker Desktop」→ 點開 → 等右下角鯨魚圖示變綠色。

驗證指令：

```powershell
docker --version
docker ps
```

若 `docker ps` 跳出空表頭而不是錯誤，代表 Docker 引擎已就緒。

### 4-2. 進入專案資料夾

```powershell
cd 你的專案路徑\Linux_project
```

### 4-3. 一鍵安裝（建議）

執行安裝腳本，它會自動建立設定檔並啟動所有服務：

```powershell
.\setup.ps1
```

腳本會引導你輸入 Telegram Bot Token 與 Chat ID（可以先跳過，之後再填）。

> ⚠️ **重要：下載期間請勿用滑鼠點擊 PowerShell 視窗內部**，否則會進入「選取模式」導致下載暫停。若標題列出現「**選取** Windows PowerShell」，按 `Enter` 或 `Esc` 即可恢復。

### 4-4. 確認所有容器都已啟動

```powershell
docker-compose ps
```

應該看到 5 個服務的狀態欄都顯示 `Up` 或 `running`：

```
NAME            STATUS    PORTS
prometheus      Up        0.0.0.0:9090->9090/tcp
grafana         Up        0.0.0.0:3000->3000/tcp
node-exporter   Up        0.0.0.0:9100->9100/tcp
cadvisor        Up        0.0.0.0:8080->8080/tcp
alertmanager    Up        0.0.0.0:9093->9093/tcp
```

---

## 5. 服務存取網址

| 服務 | 網址 | 帳密 |
|------|------|------|
| **Grafana 戰情儀表板** | http://localhost:3000 | admin / admin |
| Prometheus 控制台 | http://localhost:9090 | 無 |
| Alertmanager | http://localhost:9093 | 無 |
| cAdvisor 容器面板 | http://localhost:8080 | 無 |
| Node Exporter 指標 | http://localhost:9100/metrics | 無 |

---

## 6. Grafana 初始設定

### 6-1. 登入

打開 http://localhost:3000，輸入：

- **Email or username**：`admin`
- **Password**：`admin`

> ❗ 不要輸入 Email，預設帳號就是 `admin`。

### 6-2. 變更密碼

首次登入會強制要求改密碼。設定一個你記得住的密碼，或按 **Skip** 跳過。

### 6-3. 確認資料源

由於設定檔已自動掛載資料源（datasource provisioning），開啟 Grafana 後 Prometheus 已自動連上，無需手動新增。

驗證方法：左側選單 → **Connections** → **Data sources** → 應該看到 `Prometheus` 已存在且綠色勾勾。

---

## 7. 匯入監控儀表板

### 推薦儀表板 ID

| Dashboard ID | 用途 | 說明 |
|--------------|------|------|
| **1860** | Node Exporter Full | 最完整的主機監控（30+ 個圖表） |
| **893** | Docker and Host Monitoring | 主機 + Docker 綜合面板 |

> ⚠️ Dashboard 193 與新版 cAdvisor 不相容，匯入後會全部顯示 N/A，請勿使用。

### 匯入步驟

1. 左側選單 → **Dashboards**
2. 右上角點 **New** → **Import**
3. 在「**Import via grafana.com**」欄位輸入：`1860`
4. 點 **Load**
5. 在底下「Prometheus」資料源選擇：`Prometheus`
6. 點 **Import**

完成後立刻出現一張高科技儀表板，包含 CPU 使用率、記憶體、磁碟 I/O、網路流量等指標。

---

## 8. 設定 Telegram 自動警告

### 8-1. 建立 Telegram Bot

1. 在 Telegram 搜尋 `@BotFather`，開啟對話
2. 輸入指令 `/newbot`
3. 依提示輸入 Bot 名稱（例：`my-monitor-bot`）
4. 完成後 BotFather 會回傳一段 **Token**（例：`123456789:ABCdefGhIJK...`）
5. **複製這段 Token 並妥善保存**

### 8-2. 取得個人 Chat ID

1. 在 Telegram 搜尋 `@userinfobot`，開啟對話
2. 按 Start，它會回傳你的 Chat ID（一串數字，例：`987654321`）
3. **跟剛建立的 Bot 對話一次**（隨便傳一句 "hi"），否則 Bot 無法主動發訊息給你

### 8-3. 修改 Alertmanager 設定

開啟檔案：`alertmanager\alertmanager.yml`

把以下兩個值換成你自己的：

```yaml
bot_token: 'YOUR_BOT_TOKEN_HERE'   ← 換成 BotFather 給你的 Token
chat_id: 0                          ← 換成 userinfobot 給你的數字 ID
```

### 8-4. 重啟 Alertmanager 套用設定

```powershell
docker-compose restart alertmanager
```

### 8-5. 驗證

可在 Alertmanager 介面 (http://localhost:9093) 手動觸發測試告警，或等待 Demo 階段壓測觸發。

---

## 9. Demo 操作流程

### 9-1. 展示正常狀態

打開 Grafana 戰情儀表板（http://localhost:3000），向觀眾介紹：

> 「這是我們建構的 IT 營運戰情室，主管可以隨時掌握公司伺服器的健康狀況。」

### 9-2. 製造事故（壓力測試）

在新的 PowerShell 視窗執行：

```powershell
docker run --rm -it --name stress polinux/stress stress --cpu 8 --timeout 120s
```

此指令會啟動一個容器，持續壓滿 CPU 120 秒。

> **注意：** `--cpu` 後面的數字要大於等於你電腦的 CPU 核心數，才能讓使用率突破 80% 的告警門檻。
> 查看你的核心數：工作管理員 → 效能 → CPU → 邏輯處理器數量。
> 例如 16 核心的電腦就下 `--cpu 16`。

### 9-3. 觀察戰情室反應

切回 Grafana 畫面，觀眾會看到：

- CPU 使用率圖表瞬間飆升至接近 100%
- 圖表顏色由綠變紅（若設定了閾值）
- 約 30 秒後手機 Telegram 跳出告警訊息：
  > 警告！生產環境伺服器 CPU 負載過高 — production-vm CPU 使用率已達 99.2%，請資管人員盡速處理！

### 9-4. 完美收尾

壓測結束（60 秒）後，圖表會逐漸恢復綠色，Telegram 也會收到「告警解除」通知。

### 9-5. 收尾話術

> 「本系統透過 Docker 貨櫃化技術，以零硬體成本幫中小企業建構主動式運維監控平台。將傳統『系統掛掉才知道』的被動管理，轉化為『預先告警、即時處理』的主動管理，有效提升企業 IT 營運彈性與商業連續性。」

---

## 10. 常見問題排解 (Troubleshooting)

### Q1：`localhost:3000` 顯示「無法連上這個網站」

**原因**：Grafana 容器沒啟動，或 Docker Desktop 沒開。

**排解**：
```powershell
docker-compose ps                # 看容器狀態
docker-compose logs grafana      # 看 Grafana 錯誤訊息
docker-compose up -d             # 重新啟動
```

### Q2：PowerShell 視窗下載卡住不動

**原因**：滑鼠不小心點到 PowerShell 視窗內部，進入「選取模式」。

**排解**：視窗標題若出現「**選取** Windows PowerShell」，按 `Enter` 或 `Esc` 即可恢復。

### Q3：登入 Grafana 顯示 "Invalid username or password"

**原因**：輸入了 Email 而非預設帳號。

**排解**：username 欄輸入 `admin`（不是 Email），密碼也是 `admin`。

### Q4：壓測指令觸發後 Telegram 沒收到告警

**檢查清單**：
1. `alertmanager.yml` 的 `bot_token` 跟 `chat_id` 是否正確填寫？
2. 是否曾經主動跟 Bot 對話過？（必要步驟）
3. 重啟過 Alertmanager 嗎？(`docker-compose restart alertmanager`)
4. 查 Alertmanager 日誌：`docker-compose logs alertmanager`
5. 在 http://localhost:9093 看告警是否有進來

### Q5：Port 已被占用 (port is already allocated)

**原因**：本機其他程式占用了 3000 / 9090 等 port。

**排解**：找出並關閉占用程式，或修改 `docker-compose.yml` 改用其他 port（例：`"3001:3000"`）。

```powershell
netstat -ano | findstr :3000     # 找出占用 port 3000 的程式 PID
```

### Q6：磁碟空間爆掉

**原因**：Prometheus 持續累積監控資料。

**排解**：
```powershell
docker-compose down -v           # 停止並刪除所有資料卷
docker system prune -a           # 清理無用映像檔
```

---

## 11. 日常維運指令

| 指令 | 用途 |
|------|------|
| `docker-compose up -d` | 啟動所有服務（背景執行） |
| `docker-compose down` | 停止並移除所有容器（保留資料） |
| `docker-compose down -v` | 停止並移除所有容器與資料卷（資料會清空） |
| `docker-compose ps` | 查看所有容器狀態 |
| `docker-compose logs -f grafana` | 即時查看 Grafana 日誌 |
| `docker-compose restart prometheus` | 重啟單一服務 |
| `docker-compose pull` | 更新映像檔到最新版 |

---

## 附錄：專案資料夾結構

```
monitoring-stack/
├── docker-compose.yml              ← 主編排檔案（5 個服務的定義）
├── 使用手冊.md                     ← 本檔案
├── prometheus/
│   ├── prometheus.yml              ← Prometheus 抓取設定
│   └── alert.rules.yml             ← 告警規則（CPU/記憶體/磁碟/離線）
├── alertmanager/
│   └── alertmanager.yml            ← Telegram 通知設定
└── grafana/
    └── provisioning/
        └── datasources/
            └── prometheus.yml      ← 自動掛載 Prometheus 為資料源
```
