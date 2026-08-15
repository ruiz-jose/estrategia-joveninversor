document.addEventListener("DOMContentLoaded", () => {

    function updateLastSync() {
        const now = new Date();
        document.getElementById("lastSync").textContent = `Sincronizado: ${now.toLocaleTimeString()}`;
    }

    async function loadScanner() {
        const scannerList = document.getElementById("scannerList");
        try {
            const res = await fetch("/api/scanner");
            const data = await res.json();
            if (data.status === "success" && data.signals) {
                scannerList.innerHTML = data.signals.map(s => {
                    const sigClass = s.signal === 1 ? 'long' : (s.signal === -1 ? 'short' : 'neutral');
                    const sigText = s.signal === 1 ? 'BUY LONG' : (s.signal === -1 ? 'SELL SHORT' : 'NEUTRAL');
                    return `
                        <div class="scanner-item">
                            <span>${s.symbol}</span>
                            <span class="scanner-signal ${sigClass}">${sigText}</span>
                        </div>
                    `;
                }).join('');
            }
        } catch (e) {
            console.error("Error loading scanner signals:", e);
        }
    }

    async function loadLiveBotState() {
        try {
            const res = await fetch("/api/testnet");
            const data = await res.json();
            if (data.status === "success") {
                renderLiveBotState(data.state);
                renderEnvironmentBadge(data.environment);
                updateLastSync();
            }
        } catch (e) {
            console.error("Error loading live bot state:", e);
        }
    }

    function renderEnvironmentBadge(env) {
        const badge = document.getElementById("envBadge");
        const text = document.getElementById("envBadgeText");
        if (!env) {
            badge.className = "status-badge env-badge";
            text.textContent = "Entorno desconocido";
            return;
        }

        const marketLabel = env.market_type === "futures" ? "Futures" : "Spot";
        const leverageLabel = env.leverage ? ` ${env.leverage}x` : "";

        if (!env.live_trading_enabled) {
            // No valid API keys loaded: nothing is ever sent to Binance, every
            // trade is a local-only simulation regardless of the TESTNET flag.
            badge.className = "status-badge env-badge env-simulated";
            text.textContent = `📝 SIMULACIÓN LOCAL (${marketLabel}, sin conexión a Binance)`;
        } else if (env.testnet) {
            badge.className = "status-badge env-badge env-testnet";
            text.textContent = `🧪 BINANCE TESTNET — Dinero Ficticio (${marketLabel}${leverageLabel})`;
        } else {
            badge.className = "status-badge env-badge env-real";
            text.textContent = `💵 BINANCE REAL — DINERO REAL (${marketLabel}${leverageLabel})`;
        }
    }

    function renderLiveBotState(state) {
        const statusBadge = document.getElementById("liveBotStatusBadge");
        const statusText = document.getElementById("liveBotStatusText");
        if (state.trading_halted) {
            statusBadge.classList.add("halted");
            statusText.textContent = "Pausado (Kill-Switch)";
        } else {
            statusBadge.classList.remove("halted");
            statusText.textContent = "Activo";
        }

        document.getElementById("liveBalance").textContent = `$${state.account_balance.toFixed(2)}`;
        document.getElementById("livePeak").textContent = `Pico: $${state.peak_balance.toFixed(2)}`;

        const trades = state.completed_trades || [];
        const totalPnl = trades.reduce((sum, t) => sum + t.pnl_usd, 0);
        document.getElementById("liveTradesCount").textContent = trades.length;
        const netPnlEl = document.getElementById("liveNetPnl");
        netPnlEl.textContent = `PnL Total: ${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`;
        netPnlEl.className = `stat-sub ${totalPnl >= 0 ? '' : 'negative'}`;

        const posBox = document.getElementById("livePositionBox");
        const positions = state.active_positions
            ? Object.values(state.active_positions)
            : (state.active_position ? [state.active_position] : []);
        if (positions.length > 0) {
            posBox.innerHTML = positions.map(pos => `
                <div class="live-position-card ${pos.type.toLowerCase()}">
                    <span class="trade-badge ${pos.type.toLowerCase()}">${pos.type}</span>
                    <div class="live-position-details">
                        <span><strong>${pos.symbol}</strong> · Entrada ${pos.entry_time} ${originBadge(pos.live)}</span>
                        <span>Precio entrada: $${pos.entry_price.toLocaleString()} &nbsp;|&nbsp; SL: $${pos.stop_loss.toLocaleString()} &nbsp;|&nbsp; TP: $${pos.take_profit.toLocaleString()}</span>
                        <span>Tamaño: $${pos.position_size_usd.toFixed(2)} · Fuerza señal: ${pos.strength} · ${pos.reason}</span>
                    </div>
                </div>
            `).join('');
        } else {
            posBox.innerHTML = `<div class="empty-state-card">Sin posición abierta en este momento.</div>`;
        }

        const tbody = document.getElementById("liveTradesTableBody");
        if (trades.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Sin operaciones cerradas todavía.</td></tr>`;
        } else {
            tbody.innerHTML = trades.slice().reverse().map(t => {
                const isWin = t.pnl_usd >= 0;
                return `
                    <tr>
                        <td>#${t.id}</td>
                        <td>${t.symbol || 'N/A'}</td>
                        <td><span class="trade-badge ${t.type.toLowerCase()}">${t.type}</span></td>
                        <td>${t.entry_time}</td>
                        <td>$${t.entry_price.toLocaleString()}</td>
                        <td>$${t.exit_price.toLocaleString()}</td>
                        <td class="${isWin ? 'pnl-positive' : 'pnl-negative'}">${isWin ? '+' : ''}$${t.pnl_usd.toFixed(2)}</td>
                        <td class="${isWin ? 'pnl-positive' : 'pnl-negative'}">${isWin ? '+' : ''}${t.pnl_pct.toFixed(2)}%</td>
                        <td>${t.exit_reason}</td>
                    </tr>
                `;
            }).join('');
        }
    }

    function originBadge(isLive) {
        return isLive
            ? `<span class="origin-badge is-live" title="Orden real enviada a Binance"><i class="fa-solid fa-tower-broadcast"></i> Real</span>`
            : `<span class="origin-badge is-paper" title="Simulación local, no se envió ninguna orden a Binance"><i class="fa-solid fa-flask"></i> Simulado</span>`;
    }

    loadScanner();
    loadLiveBotState();
    setInterval(loadScanner, 30000);
    setInterval(loadLiveBotState, 15000);
});
