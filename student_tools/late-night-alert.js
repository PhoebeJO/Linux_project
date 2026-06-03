/**
 * 🌙 深夜使用提醒系統
 * 瀏覽器通知 + 全螢幕警告 + 聲音提醒
 */
(function() {
    let alertShown = false;
    let overlay = null;
    let audioCtx = null;

    // ── 聲音提醒 ──
    function playAlertSound() {
        try {
            audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
            // 柔和的提示音（三個音階）
            const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
            notes.forEach((freq, i) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime + i * 0.3);
                gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + i * 0.3 + 0.5);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(audioCtx.currentTime + i * 0.3);
                osc.stop(audioCtx.currentTime + i * 0.3 + 0.5);
            });
        } catch (e) {
            console.log('無法播放聲音:', e);
        }
    }

    // ── 瀏覽器通知 ──
    function sendBrowserNotification(message) {
        if (!('Notification' in window)) return;
        if (Notification.permission === 'granted') {
            new Notification('🌙 深夜提醒', {
                body: message,
                icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🌙</text></svg>',
                tag: 'late-night',
                requireInteraction: true
            });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(p => {
                if (p === 'granted') sendBrowserNotification(message);
            });
        }
    }

    // ── 全螢幕警告覆蓋 ──
    function showFullScreenAlert(message) {
        if (overlay) return;
        overlay = document.createElement('div');
        overlay.id = 'late-night-overlay';
        overlay.innerHTML = `
            <div style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.92);
                display: flex; flex-direction: column;
                justify-content: center; align-items: center;
                z-index: 99999;
                animation: fadeIn 0.5s ease;
            ">
                <div style="font-size: 80px; margin-bottom: 20px;">🌙</div>
                <div style="
                    font-size: 2.5em; color: #fff; font-weight: bold;
                    text-align: center; margin-bottom: 15px;
                ">深夜了！該去休息了</div>
                <div style="
                    font-size: 1.2em; color: rgba(255,255,255,0.7);
                    text-align: center; max-width: 500px; line-height: 1.8;
                    margin-bottom: 40px;
                ">${message}</div>
                <div style="display: flex; gap: 15px;">
                    <button onclick="document.getElementById('late-night-overlay').remove(); window._lateNightOverlay = null;"
                        style="
                            padding: 15px 40px; font-size: 1.1em;
                            border: 2px solid rgba(255,255,255,0.3); border-radius: 50px;
                            background: transparent; color: #fff; cursor: pointer;
                            transition: all 0.3s;
                        "
                        onmouseover="this.style.background='rgba(255,255,255,0.1)'"
                        onmouseout="this.style.background='transparent'"
                    >我知道了，再用一下</button>
                    <button onclick="window.close(); window.location='about:blank';"
                        style="
                            padding: 15px 40px; font-size: 1.1em;
                            border: none; border-radius: 50px;
                            background: #2ecc71; color: #fff; cursor: pointer;
                            font-weight: bold; transition: all 0.3s;
                        "
                        onmouseover="this.style.background='#27ae60'"
                        onmouseout="this.style.background='#2ecc71'"
                    >🛏️ 去睡覺</button>
                </div>
                <div style="
                    margin-top: 30px; font-size: 0.85em;
                    color: rgba(255,255,255,0.3);
                ">早睡早起身體好 💪 明天繼續加油</div>
            </div>
        `;
        document.body.appendChild(overlay);
        window._lateNightOverlay = overlay;
    }

    function removeOverlay() {
        if (overlay) {
            overlay.remove();
            overlay = null;
        }
    }

    // ── 定時檢查 ──
    async function checkLateNight() {
        try {
            const resp = await fetch('/api/settings');
            const settings = await resp.json();
            const ln = settings.late_night || {};
            const startH = ln.start_hour ?? 1;
            const endH = ln.end_hour ?? 6;
            const msg = ln.message || '建議停止使用電腦，保持良好作息！';
            const now = new Date().getHours();

            let isLate;
            if (startH <= endH) {
                isLate = now >= startH && now < endH;
            } else {
                isLate = now >= startH || now < endH;
            }

            if (isLate && !alertShown) {
                alertShown = true;
                playAlertSound();
                sendBrowserNotification(msg);
                setTimeout(() => showFullScreenAlert(msg), 500);
            } else if (!isLate) {
                alertShown = false;
                removeOverlay();
            }
        } catch (e) {
            // 靜默失敗
        }
    }

    // 請求瀏覽器通知權限
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }

    // 啟動：立即檢查一次，之後每 60 秒檢查
    checkLateNight();
    setInterval(checkLateNight, 60000);

    // CSS 動畫
    const style = document.createElement('style');
    style.textContent = '@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }';
    document.head.appendChild(style);
})();
