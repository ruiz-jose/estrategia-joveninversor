document.addEventListener("DOMContentLoaded", () => {
    const configForm = document.getElementById("configForm");
    const btnRunBacktest = document.getElementById("btnRunBacktest");
    const btnTabChart = document.getElementById("btnTabChart");
    const btnTabEquity = document.getElementById("btnTabEquity");

    const tvChartContainer = document.getElementById("tvChartContainer");
    const equityChartContainer = document.getElementById("equityChartContainer");

    let mainChart = null;
    let rsiChart = null;
    let macdChart = null;
    let equityChart = null;

    let lastBacktestData = null;

    // Tab switching
    btnTabChart.addEventListener("click", () => {
        btnTabChart.classList.add("active");
        btnTabEquity.classList.remove("active");
        tvChartContainer.classList.remove("hidden");
        equityChartContainer.classList.add("hidden");
    });

    btnTabEquity.addEventListener("click", () => {
        btnTabEquity.classList.add("active");
        btnTabChart.classList.remove("active");
        equityChartContainer.classList.remove("hidden");
        tvChartContainer.classList.add("hidden");
        if (lastBacktestData) {
            renderEquityChart(lastBacktestData.equity_curve);
        }
    });

    // Form submit
    configForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        await runBacktest();
    });

    async function runBacktest() {
        btnRunBacktest.disabled = true;
        btnRunBacktest.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Ejecutando Backtest...`;

        const payload = {
            symbol: document.getElementById("symbol").value,
            timeframe: document.getElementById("timeframe").value,
            initial_capital: parseFloat(document.getElementById("capital").value),
            risk_per_trade_pct: parseFloat(document.getElementById("riskPct").value),
            ema_fast: parseInt(document.getElementById("emaFast").value),
            ema_medium: parseInt(document.getElementById("emaMedium").value),
            ema_slow: parseInt(document.getElementById("emaSlow").value),
            risk_reward_ratio: parseFloat(document.getElementById("rrRatio").value),
            adx_threshold: parseFloat(document.getElementById("adxThresh").value)
        };

        try {
            const res = await fetch("/api/backtest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (data.status === "success") {
                lastBacktestData = data.result;
                updateStats(data.result.summary);
                renderTradingViewCharts(data.result.candles, data.result.trades, payload.symbol, payload.timeframe);
                renderTradeTable(data.result.trades);
                if (!equityChartContainer.classList.contains("hidden")) {
                    renderEquityChart(data.result.equity_curve);
                }
                updateLastSync();
            } else {
                alert("Error ejecutando backtest: " + (data.message || "Error desconocido"));
            }
        } catch (err) {
            console.error(err);
            alert("Error de conexión con el servidor del bot.");
        } finally {
            btnRunBacktest.disabled = false;
            btnRunBacktest.innerHTML = `<i class="fa-solid fa-play"></i> Ejecutar Backtest & Simulación`;
        }
    }

    function updateStats(summary) {
        document.getElementById("statBalance").textContent = `$${summary.final_balance.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        
        const isPos = summary.total_net_pnl >= 0;
        const netEl = document.getElementById("statNetPnl");
        netEl.textContent = `${isPos ? '+' : ''}$${summary.total_net_pnl.toFixed(2)} (${isPos ? '+' : ''}${summary.total_return_pct.toFixed(2)}%)`;
        netEl.className = `stat-sub ${isPos ? '' : 'negative'}`;

        document.getElementById("statWinRate").textContent = `${summary.win_rate.toFixed(1)}%`;
        document.getElementById("statTradesCount").textContent = `${summary.total_trades} Trades (${summary.winning_trades} Ganados / ${summary.losing_trades} Perdidos)`;

        document.getElementById("statProfitFactor").textContent = summary.profit_factor.toFixed(2);
        document.getElementById("statSharpe").textContent = `Sharpe: ${summary.sharpe_ratio.toFixed(2)}`;
        document.getElementById("statMaxDD").textContent = `${summary.max_drawdown.toFixed(2)}%`;
    }

    function parseTimestamp(ts) {
        const d = new Date(ts);
        return Math.floor(d.getTime() / 1000);
    }

    function getCommonChartOptions(height) {
        return {
            height: height,
            layout: {
                background: { type: 'solid', color: '#0b0e14' },
                textColor: '#9ca3af',
                fontSize: 12,
                fontFamily: 'Outfit, sans-serif'
            },
            grid: {
                vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                horzLines: { color: 'rgba(255, 255, 255, 0.05)' }
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: 'rgba(255, 255, 255, 0.1)',
            },
            timeScale: {
                borderColor: 'rgba(255, 255, 255, 0.1)',
                timeVisible: true,
                secondsVisible: false,
            }
        };
    }

    function renderTradingViewCharts(candles, trades, symbol, timeframe) {
        document.getElementById("chartSymbolTitle").textContent = `${symbol} - ${timeframe.toUpperCase()}`;
        document.getElementById("chartCandlesCount").textContent = `${candles.length} Velas Analizadas`;

        // Clear previous charts
        const mainContainer = document.getElementById("tvMainChart");
        const rsiContainer = document.getElementById("tvRsiChart");
        const macdContainer = document.getElementById("tvMacdChart");

        mainContainer.innerHTML = "";
        rsiContainer.innerHTML = "";
        macdContainer.innerHTML = "";

        // 1. Create Main Candlestick Chart
        mainChart = LightweightCharts.createChart(mainContainer, getCommonChartOptions(380));

        const candleSeries = mainChart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        });

        const candleData = candles.map(c => ({
            time: parseTimestamp(c.timestamp),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close
        }));

        candleSeries.setData(candleData);

        // EMAs
        const ema20Series = mainChart.addLineSeries({ color: '#06b6d4', lineWidth: 2, title: 'EMA 20' });
        const ema50Series = mainChart.addLineSeries({ color: '#eab308', lineWidth: 2, title: 'EMA 50' });
        const ema200Series = mainChart.addLineSeries({ color: '#ec4899', lineWidth: 2, title: 'EMA 200' });

        ema20Series.setData(candles.filter(c => c.ema_20 !== null).map(c => ({ time: parseTimestamp(c.timestamp), value: c.ema_20 })));
        ema50Series.setData(candles.filter(c => c.ema_50 !== null).map(c => ({ time: parseTimestamp(c.timestamp), value: c.ema_50 })));
        ema200Series.setData(candles.filter(c => c.ema_200 !== null).map(c => ({ time: parseTimestamp(c.timestamp), value: c.ema_200 })));

        // Trade Markers
        const markers = [];
        trades.forEach(t => {
            const timeSec = parseTimestamp(t.entry_time);
            if (t.type === "LONG") {
                markers.push({
                    time: timeSec,
                    position: 'belowBar',
                    color: '#10b981',
                    shape: 'arrowUp',
                    text: `BUY LONG @ $${t.entry_price}`
                });
            } else {
                markers.push({
                    time: timeSec,
                    position: 'aboveBar',
                    color: '#ef4444',
                    shape: 'arrowDown',
                    text: `SELL SHORT @ $${t.entry_price}`
                });
            }
        });
        markers.sort((a, b) => a.time - b.time);
        candleSeries.setMarkers(markers);

        // 2. Create RSI Subchart
        rsiChart = LightweightCharts.createChart(rsiContainer, getCommonChartOptions(120));
        const rsiSeries = rsiChart.addLineSeries({ color: '#8b5cf6', lineWidth: 2, title: 'RSI (14)' });
        rsiSeries.setData(candles.filter(c => c.rsi !== null).map(c => ({ time: parseTimestamp(c.timestamp), value: c.rsi })));

        // Overbought / Oversold Bounds
        const rsi70Series = rsiChart.addLineSeries({ color: 'rgba(239, 68, 68, 0.4)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed });
        const rsi30Series = rsiChart.addLineSeries({ color: 'rgba(16, 185, 129, 0.4)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed });
        rsi70Series.setData(candleData.map(c => ({ time: c.time, value: 70 })));
        rsi30Series.setData(candleData.map(c => ({ time: c.time, value: 30 })));

        // 3. Create MACD Subchart
        macdChart = LightweightCharts.createChart(macdContainer, getCommonChartOptions(120));
        const macdHistSeries = macdChart.addHistogramSeries({ title: 'MACD Hist' });
        const macdLineSeries = macdChart.addLineSeries({ color: '#3b82f6', lineWidth: 1.5, title: 'MACD' });
        const macdSigSeries = macdChart.addLineSeries({ color: '#f59e0b', lineWidth: 1.5, title: 'Signal' });

        macdHistSeries.setData(candles.filter(c => c.macd_hist !== null).map(c => ({
            time: parseTimestamp(c.timestamp),
            value: c.macd_hist,
            color: c.macd_hist >= 0 ? '#10b981' : '#ef4444'
        })));
        macdLineSeries.setData(candles.filter(c => c.macd !== null).map(c => ({ time: parseTimestamp(c.timestamp), value: c.macd })));
        macdSigSeries.setData(candles.filter(c => c.macd_signal !== null).map(c => ({ time: parseTimestamp(c.timestamp), value: c.macd_signal })));

        // Synchronize TimeScales of all subcharts
        mainChart.timeScale().subscribeVisibleTimeRangeChange(range => {
            if (range) {
                rsiChart.timeScale().setVisibleTimeRange(range);
                macdChart.timeScale().setVisibleTimeRange(range);
            }
        });

        mainChart.timeScale().fitContent();
    }

    function renderEquityChart(equityCurve) {
        if (!equityCurve || equityCurve.length === 0) return;

        const equityContainer = document.getElementById("tvEquityChart");
        equityContainer.innerHTML = "";

        equityChart = LightweightCharts.createChart(equityContainer, getCommonChartOptions(520));
        const areaSeries = equityChart.addAreaSeries({
            topColor: 'rgba(59, 130, 246, 0.4)',
            bottomColor: 'rgba(59, 130, 246, 0.0)',
            lineColor: '#3b82f6',
            lineWidth: 2,
            title: 'Equity ($)'
        });

        const data = equityCurve.map(e => ({
            time: parseTimestamp(e.timestamp),
            value: e.equity
        }));

        areaSeries.setData(data);
        equityChart.timeScale().fitContent();
    }

    function renderTradeTable(trades) {
        const tbody = document.getElementById("tradesTableBody");
        document.getElementById("tradesTableCount").textContent = `${trades.length} Operaciones`;

        if (!trades || trades.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="empty-state">No se generaron operaciones en el período analizado.</td></tr>`;
            return;
        }

        tbody.innerHTML = trades.map(t => {
            const isWin = t.pnl_usd >= 0;
            return `
                <tr>
                    <td>#${t.id}</td>
                    <td><span class="trade-badge ${t.type.toLowerCase()}">${t.type}</span></td>
                    <td>${t.entry_time.split(" ")[1] || t.entry_time}</td>
                    <td>$${t.entry_price.toLocaleString()}</td>
                    <td>$${t.exit_price.toLocaleString()}</td>
                    <td>$${t.stop_loss.toLocaleString()}</td>
                    <td>$${t.take_profit.toLocaleString()}</td>
                    <td class="${isWin ? 'pnl-positive' : 'pnl-negative'}">${isWin ? '+' : ''}$${t.pnl_usd.toFixed(2)}</td>
                    <td class="${isWin ? 'pnl-positive' : 'pnl-negative'}">${isWin ? '+' : ''}${t.pnl_pct.toFixed(2)}%</td>
                    <td>${t.exit_reason}</td>
                </tr>
            `;
        }).join('');
    }

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

    // Initial run
    runBacktest();
    loadScanner();
    setInterval(loadScanner, 30000);
});
