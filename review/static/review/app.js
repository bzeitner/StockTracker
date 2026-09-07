(function () {
  const ranges = JSON.parse(document.getElementById("ranges-data").textContent || "{}");
  const symbolEl = document.getElementById("symbol");
  const startEl = document.getElementById("start");
  const endEl = document.getElementById("end");
  const intervalEl = document.getElementById("interval");
  const orbEl = document.getElementById("orb");
  const loadBtn = document.getElementById("load");
  const statusEl = document.getElementById("status");

  const LEVEL_KEYS = [
    "onh", "onl", "rth_high", "rth_low",
    "full_session_high", "full_session_low", "orb_high", "orb_low",
  ];
  const DEFAULT_COLORS = {
    onh: "#d62728", onl: "#d62728",
    rth_high: "#1f77b4", rth_low: "#1f77b4",
    full_session_high: "#7f7f7f", full_session_low: "#7f7f7f",
    orb_high: "#2ca02c", orb_low: "#2ca02c",
  };

  function loadColors() {
    try {
      return { ...DEFAULT_COLORS, ...JSON.parse(localStorage.getItem("review-level-colors") || "{}") };
    } catch (e) {
      return { ...DEFAULT_COLORS };
    }
  }

  function saveColors(colors) {
    localStorage.setItem("review-level-colors", JSON.stringify(colors));
  }

  const colors = loadColors();

  document.querySelectorAll("input[data-color]").forEach((input) => {
    const key = input.dataset.color;
    input.value = colors[key] || "#000000";
    input.addEventListener("input", () => {
      colors[key] = input.value;
      saveColors(colors);
      render();
    });
  });

  function applyDefaultRange() {
    const symbol = symbolEl.value;
    const range = ranges[symbol];
    if (!range) return;
    endEl.value = range.end;
    startEl.value = range.start;
    endEl.min = range.start;
    endEl.max = range.end;
    startEl.min = range.start;
    startEl.max = range.end;
  }

  symbolEl.addEventListener("change", applyDefaultRange);
  applyDefaultRange();

  const chart = LightweightCharts.createChart(document.getElementById("chart"), {
    height: 460,
    timeScale: { timeVisible: true, secondsVisible: false },
  });
  const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries);

  const volumeChart = LightweightCharts.createChart(document.getElementById("volume"), {
    height: 140,
    timeScale: { timeVisible: true, secondsVisible: false, visible: true },
  });
  const volumeSeries = volumeChart.addSeries(LightweightCharts.HistogramSeries, {
    color: "#999",
    priceFormat: { type: "volume" },
  });

  chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (range) volumeChart.timeScale().setVisibleLogicalRange(range);
  });
  volumeChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (range) chart.timeScale().setVisibleLogicalRange(range);
  });

  let priceLines = [];

  function clearPriceLines() {
    priceLines.forEach((line) => candleSeries.removePriceLine(line));
    priceLines = [];
  }

  function drawLevels(levels, orbMinutes) {
    clearPriceLines();
    const enabled = new Set(
      Array.from(document.querySelectorAll("input[data-level]:checked")).map((el) => el.dataset.level)
    );
    const specs = [
      ["onh", "ONH", levels.onh],
      ["onl", "ONL", levels.onl],
      ["rth_high", "PDH (RTH)", levels.rth_high],
      ["rth_low", "PDL (RTH)", levels.rth_low],
      ["full_session_high", "PDH (full)", levels.full_session_high],
      ["full_session_low", "PDL (full)", levels.full_session_low],
      ["orb_high", `ORB${orbMinutes} H`, levels[`orb${orbMinutes}_high`]],
      ["orb_low", `ORB${orbMinutes} L`, levels[`orb${orbMinutes}_low`]],
    ];
    for (const [key, label, value] of specs) {
      if (value === null || value === undefined || !enabled.has(key)) continue;
      priceLines.push(
        candleSeries.createPriceLine({
          price: value,
          color: colors[key],
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: true,
          title: label,
        })
      );
    }
  }

  let lastPayload = null;

  function render() {
    if (lastPayload) drawLevels(lastPayload.levels, lastPayload.orbMinutes);
  }

  document.querySelectorAll("input[data-level]").forEach((el) => el.addEventListener("change", render));

  async function load() {
    statusEl.textContent = "";
    const params = new URLSearchParams({
      symbol: symbolEl.value,
      start: startEl.value,
      end: endEl.value,
      interval: intervalEl.value,
      orb: orbEl.value,
    });
    const resp = await fetch(`/api/chart-data?${params}`);
    const payload = await resp.json();
    if (!resp.ok) {
      statusEl.textContent = payload.error || "Request failed";
      return;
    }
    candleSeries.setData(
      payload.bars.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close }))
    );
    volumeSeries.setData(
      payload.bars.map((b) => ({
        time: b.time,
        value: b.volume,
        color: b.close >= b.open ? "#26a69a" : "#ef5350",
      }))
    );
    lastPayload = { levels: payload.levels, orbMinutes: orbEl.value };
    drawLevels(payload.levels, orbEl.value);
    chart.timeScale().fitContent();
    volumeChart.timeScale().fitContent();
  }

  loadBtn.addEventListener("click", load);
  if (symbolEl.value) load();
})();
