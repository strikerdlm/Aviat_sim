// Minimal D3 helpers from g3 (already bundled with g3)
/* global g3 */

(function () {
  const host = document.getElementById('gauges');
  // panel will create and set g3.activeController internally

  function createGauges() {
    // Robust creation: prefer contrib "T" panel, fallback to basic gauges if contrib unavailable
    const hasContrib = !!(g3 && g3.contrib && g3.contrib.nav && g3.contrib.nav.attitude && g3.contrib.nav.heading && g3.contrib.nav.VSI && g3.contrib.nav.altitude);
    const panel = g3.panel().width(1280).height(620).smooth(true).grid(false);

    const rowTopY = 210, rowBottomY = 470;

    // Shared torque gauges
    const tqScale = d3.scaleLinear().domain([0, 50]).range([210, 510]);
    const tq1 = g3.gauge()
      .metric('tq1').unit('percent')
      .measure(tqScale)
      .append(
        g3.gaugeFace(),
        g3.axisTicks().step(2),
        g3.axisTicks().step(10).size(15).style('stroke-width: 2'),
        g3.axisLabels().step(10).inset(30),
        g3.gaugeLabel('ENG 1 TQ').y(-33),
        g3.indicatePointer().shape('rondel')
      );
    const tq2 = g3.gauge()
      .metric('tq2').unit('percent')
      .measure(tqScale)
      .append(
        g3.gaugeFace(),
        g3.axisTicks().step(2),
        g3.axisTicks().step(10).size(15).style('stroke-width: 2'),
        g3.axisLabels().step(10).inset(30),
        g3.gaugeLabel('ENG 2 TQ').y(-33),
        g3.indicatePointer().shape('rondel')
      );

    let layout;
    if (hasContrib) {
      const gaugeAI = g3.contrib.nav.attitude.generic();
      const gaugeALT = g3.contrib.nav.altitude.generic().metric('altitude');
      const gaugeHDG = g3.contrib.nav.heading.generic();
      const gaugeVSI = g3.contrib.nav.VSI.generic().metric('vs');
      const gaugeASI = g3.gauge()
        .metric('tas')
        .unit('knot')
        .measure(d3.scaleLinear().domain([0, 200]).range([30, 350]))
        .append(
          g3.gaugeFace(),
          g3.axisTicks().step(10).size(12).style('stroke-width: 2'),
          g3.axisLabels().step(20).inset(30),
          g3.gaugeLabel('ASI (kt)').y(-33),
          g3.put().y(10).append(g3.indicateText().format(v => Math.round(v)).size(20)),
          g3.indicatePointer().shape('needle')
        );
      layout = g3.put().append(
        g3.put().x(320).y(rowTopY).scale(0.95).append(gaugeASI),
        g3.put().x(720).y(rowTopY).scale(0.95).append(gaugeAI),
        g3.put().x(1060).y(rowTopY).scale(0.9).append(gaugeALT),
        g3.put().x(520).y(rowBottomY).scale(0.95).append(gaugeVSI),
        g3.put().x(820).y(rowBottomY).scale(0.95).append(gaugeHDG),
        g3.put().x(1040).y(rowBottomY).scale(0.7).append(tq1),
        g3.put().x(1200).y(rowBottomY).scale(0.7).append(tq2)
      );
    } else {
      // Fallback: TAS, ALT, VSI + torques (no AI/HDG), to avoid blocking the rest of the dashboard
      const gaugeTAS = g3.gauge()
        .metric('tas').unit('knot')
        .measure(d3.scaleLinear().domain([0, 200]).range([30, 350]))
        .append(
          g3.gaugeFace(),
          g3.axisTicks().step(10).size(12).style('stroke-width: 2'),
          g3.axisLabels().step(20).inset(30),
          g3.gaugeLabel('TAS (kt)').y(-33),
          g3.put().y(10).append(g3.indicateText().format(v => Math.round(v)).size(20)),
          g3.indicatePointer().shape('needle')
        );
      const gaugeALTbasic = g3.gauge()
        .metric('altitude').unit('ft')
        .measure(d3.scaleLinear().domain([0, 1500]).range([0, 360]))
        .append(
          g3.gaugeFace(),
          g3.axisTicks().step(50),
          g3.axisTicks().step(250).size(15).style('stroke-width: 2'),
          g3.axisLabels().step(250).format(v => Math.round(v/100)).size(18),
          g3.gaugeLabel('ALT (ft)').y(-33),
          g3.put().y(10).append(g3.indicateText().format(v => Math.round(v)).size(20)),
          g3.indicatePointer().shape('needle')
        );
      const gaugeVSIbasic = g3.gauge()
        .metric('vs').unit('ft/min')
        .measure(d3.scaleLinear().domain([-2000, 2000]).range([90, 450]))
        .append(
          g3.gaugeFace(),
          g3.axisTicks().step(200).size(6),
          g3.axisTicks().step(1000).size(14).style('stroke-width: 2'),
          g3.axisLabels().step(1000).format(v => Math.abs(v/100)).size(16),
          g3.gaugeLabel('VSI').y(-25).size(12),
          g3.put().y(8).append(g3.indicateText().format(v => Math.round(v)).size(18)),
          g3.indicatePointer().shape('needle').clamp([-1950, 1950])
        );
      layout = g3.put().append(
        g3.put().x(360).y(rowTopY).scale(1.0).append(gaugeTAS),
        g3.put().x(860).y(rowTopY).scale(0.95).append(gaugeALTbasic),
        g3.put().x(620).y(rowBottomY).scale(0.95).append(gaugeVSIbasic),
        g3.put().x(1040).y(rowBottomY).scale(0.75).append(tq1),
        g3.put().x(1200).y(rowBottomY).scale(0.75).append(tq2)
      );
      // Attempt upgrade when contrib becomes available
      setTimeout(() => {
        try {
          if (g3 && g3.contrib && g3.contrib.nav) {
            d3.select(host).selectAll('*').remove();
            createGauges();
          }
        } catch {}
      }, 500);
    }

    d3.select(host).call(panel.append(layout));
  }

  // Controls/dom
  const playBtn = document.getElementById('btn-play');
  const speedSel = document.getElementById('speed');
  const slider = document.getElementById('time');
  const markers = document.getElementById('markers');
  const clock = document.getElementById('clock');
  const transcriptEl = document.getElementById('transcript-list');
  const eventBody = document.getElementById('event-body');
  // charts + stats DOM
  const yLeftSel = document.getElementById('yLeft');
  const yRightSel = document.getElementById('yRight');
  const legendEl = document.getElementById('chart-legend');
  const smoothEl = document.getElementById('smooth');
  const commsBubble = document.getElementById('comms-bubble');
  const riskBadgesEl = document.getElementById('risk-badges');
  const highlightsEl = document.getElementById('highlight-list');
  const stat = {
    time: document.getElementById('stat-time'),
    tas: document.getElementById('stat-tas'),
    alt: document.getElementById('stat-alt'),
    vs: document.getElementById('stat-vs'),
    gs: document.getElementById('stat-gs'),
    tq1: document.getElementById('stat-tq1'),
    tq2: document.getElementById('stat-tq2')
  };

  // Data holders
  let records = [];
  let timeline = [];
  let highlights = [];
  let tMin = 0, tMax = 0;
  let playing = false;
  let rafId = null;
  let lastTs = 0;

  // d3 is provided via script tag

  // CSV parsing with fallback if PapaParse is unavailable
  function loadCSV() {
    // Preferred: PapaParse (robust, handles quotes and edge-cases)
    if (window.Papa && typeof Papa.parse === 'function') {
      return new Promise((resolve, reject) => {
        Papa.parse('Data.csv', {
          header: true,
          dynamicTyping: true,
          skipEmptyLines: true,
          download: true,
          complete: (res) => resolve(res.data),
          error: reject
        });
      });
    }
    // Fallback: fetch + local CSV parser (handles quotes, embedded commas, escaped quotes)
    return fetch('Data.csv')
      .then(r => {
        if (!r.ok) throw new Error('Failed to load Data.csv');
        return r.text();
      })
      .then(txt => parseCsvTextToObjects(txt));
  }

  function parseCsvTextToObjects(text) {
    const rows = parseCsv(text);
    if (!rows.length) return [];
    const header = rows[0];
    const out = [];
    for (let i = 1; i < rows.length; i++) {
      const r = rows[i];
      if (!r || r.length === 0 || (r.length === 1 && r[0].trim() === '')) continue;
      const obj = {};
      for (let j = 0; j < header.length; j++) obj[header[j]] = r[j] ?? '';
      coerceKnownNumericFields(obj);
      out.push(obj);
    }
    return out;
  }

  function coerceKnownNumericFields(obj) {
    const numeric = new Set([
      'TAS','Air Pressure','Altitude Radar','Eng 1 Torque','Eng 2 Torque','Ground Speed',
      'Local Hour','Local Minute','Local Second','Vertical Speed','Ai Pressure'
    ]);
    for (const k of numeric) if (k in obj) obj[k] = toNum(obj[k]);
    return obj;
  }

  function toNum(v) {
    if (typeof v === 'number') return v;
    if (v == null) return NaN;
    const s = ('' + v).trim();
    if (s === '') return NaN;
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : NaN;
  }

  // Minimal CSV parser supporting quotes, embedded commas and escaped quotes
  function parseCsv(text) {
    const rows = [];
    let field = '';
    let row = [];
    let inQuotes = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (ch === '"') {
        if (inQuotes && text[i+1] === '"') { field += '"'; i++; }
        else { inQuotes = !inQuotes; }
      } else if (ch === ',' && !inQuotes) {
        row.push(field); field = '';
      } else if ((ch === '\n' || ch === '\r') && !inQuotes) {
        // finalize row at newline; skip bare \r (Windows) by peeking next char
        if (ch === '\r' && text[i+1] === '\n') { /* skip, will be handled by next loop */ }
        row.push(field); field = '';
        rows.push(row); row = [];
        // skip standalone \r sequences
        if (ch === '\r' && text[i+1] !== '\n') { /* already handled */ }
      } else {
        field += ch;
      }
    }
    // flush last field/row
    row.push(field);
    if (row.length && !(row.length === 1 && row[0].trim() === '')) rows.push(row);
    return rows.map(r => r.map(s => s));
  }

  // Lightweight timeline parser (from cached md already in project — we’ll fetch content if present)
  async function loadTimeline() {
    try {
      const resp = await fetch('Línea de tiempo.md');
      if (!resp.ok) return [];
      const txt = await resp.text();
      const lines = txt.split(/\n/).filter(l => /^-\s*\d\d:\d\d:\d\d/.test(l));
      return lines.map(l => {
        const m = l.match(/^(?:-\s*)(\d\d):(\d\d):(\d\d)\s+—\s*(.*)$/);
        if (!m) return null;
        const hh = +m[1], mm = +m[2], ss = +m[3];
        return { t: hh*3600 + mm*60 + ss, text: m[4] };
      }).filter(Boolean);
    } catch { return []; }
  }

  function timeToLabel(sec) {
    const h = Math.floor(sec/3600)%24, m = Math.floor(sec/60)%60, s = Math.floor(sec%60);
    const pad = (x) => x.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(s)}`;
  }

  function setClock(sec) { clock.textContent = timeToLabel(sec); }

  function renderMarkers() {
    markers.innerHTML = '';
    timeline.forEach(ev => {
      const x = ((ev.t - tMin) / (tMax - tMin)) * 100;
      const d = document.createElement('div');
      d.className = 'mark';
      d.style.left = `calc(${x}% - 1px)`;
      d.title = ev.text;
      markers.appendChild(d);
    });
  }

  function renderTranscript(nowSec) {
    // Show transcript lines within +- 10s window, highlight current second matches
    const near = records.filter(r => Math.abs(r._t - nowSec) <= 10 && r.Transcripts);
    transcriptEl.innerHTML = '';
    let latestSaid = null;
    near.forEach(r => {
      const div = document.createElement('div');
      div.className = 'line' + (r._t === nowSec ? ' now' : '');
      const time = `${r.Local_Hour?.toString().padStart(2,'0') ?? '--'}:${r.Local_Minute?.toString().padStart(2,'0') ?? '--'}:${r.Local_Second?.toString().padStart(2,'0') ?? '--'}`;
      div.innerHTML = `<div class="t">${time}</div><div class="crew">${r.Crew || ''}</div><div class="say">${(r.Transcripts||'').replace(/^"+|"+$/g,'')}</div>`;
      transcriptEl.appendChild(div);
      if (Math.abs((r._t||0) - nowSec) <= 1) latestSaid = r;
    });
    renderCommsBubble(latestSaid);
  }

  function renderCommsBubble(row) {
    if (!commsBubble) return;
    if (!row || !row.Transcripts) { commsBubble.classList.remove('show'); return; }
    const crew = (row.Crew||'').toString().trim();
    const said = (row.Transcripts||'').toString().replace(/^"+|"+$/g,'');
    commsBubble.innerHTML = `<div class="crew">${crew}</div><div class="text">${said}</div>`;
    commsBubble.classList.add('show');
  }

  function updateEvent(nowSec) {
    if (!timeline.length) { eventBody.textContent = '—'; return; }
    // find latest event <= now
    let best = null;
    for (const ev of timeline) if (ev.t <= nowSec) best = ev; else break;
    eventBody.textContent = best ? best.text : '—';
    // also pulse comms bubble subtly when new event
    if (best && commsBubble) {
      commsBubble.classList.remove('show');
      setTimeout(()=>{ commsBubble.classList.add('show'); }, 50);
    }
  }

  function sendMetrics(row) {
    const metrics = {
      latest: row._t,
      units: {
        tas: 'knot', altitude: 'ft', vs: 'ft/min', tq1: 'percent', tq2: 'percent', heading: 'deg', roll: 'deg', pitch: 'deg'
      },
      metrics: {
        tas: +row.TAS || 0,
        altitude: computeAltitude(row),
        vs: +row['Vertical Speed'] || 0,
        tq1: +row['Eng 1 Torque'] || 0,
        tq2: +row['Eng 2 Torque'] || 0,
        heading: headingAtTime(row._t || 0),
        roll: 0,
        pitch: 0
      }
    };
    if (g3.activeController) g3.activeController(metrics, sel => sel.transition().duration(180));
  }

  function computeAltitude(row) {
    // Use radio altimeter as the authoritative source
    const ar = row['Altitude Radar'];
    if (Number.isFinite(ar) && ar >= 0) return ar;
    // If unavailable or flagged negative, report 0 (do not fall back to pressure for the ALT gauge)
    return 0;
  }

  function fmt(num, digits = 0) {
    if (!Number.isFinite(num)) return '—';
    return num.toFixed(digits);
  }

  function updateStats(row, sec) {
    if (!row) return;
    stat.time.textContent = timeToLabel(sec ?? row._t ?? 0);
    stat.tas.textContent = fmt(+row.TAS || 0, 1);
    stat.alt.textContent = fmt(computeAltitude(row), 0);
    stat.vs.textContent = fmt(+row['Vertical Speed'] || 0, 0);
    stat.gs.textContent = fmt(+row['Ground Speed'] || 0, 1);
    stat.tq1.textContent = fmt(+row['Eng 1 Torque'] || 0, 1);
    stat.tq2.textContent = fmt(+row['Eng 2 Torque'] || 0, 1);
    renderRiskBadges(row);
  }

  function renderRiskBadges(row) {
    if (!riskBadgesEl) return;
    riskBadgesEl.innerHTML = '';
    const alt = computeAltitude(row);
    const gs = +row['Ground Speed'] || 0;
    const visBad = true; // from context (IMC/DVE)
    const lowAlt = alt > 0 && alt < 100;
    const highVS = Math.abs(+row['Vertical Speed']||0) > 1000;
    const items = [
      { key: 'IMC/DVE', on: visBad, danger: visBad },
      { key: 'Low Alt <100 ft', on: lowAlt, danger: lowAlt },
      { key: 'High |VS| > 1000', on: highVS, danger: highVS },
      { key: 'Over water', on: true, danger: false },
      { key: 'NVG', on: true, danger: false },
    ];
    for (const it of items) {
      const d = document.createElement('div');
      d.className = 'badge' + (it.on ? ' on' : '') + (it.danger ? ' danger' : '');
      d.textContent = it.key;
      riskBadgesEl.appendChild(d);
    }
  }

  function tickPlay() {
    if (!playing) return;
    const now = performance.now();
    const dt = (now - lastTs)/1000 * parseFloat(speedSel.value);
    lastTs = now;
    let t = +slider.value + dt;
    if (t >= tMax) { t = tMax; playing = false; playBtn.textContent = '▶'; }
    slider.value = Math.round(t);
    onSlider();
    rafId = requestAnimationFrame(tickPlay);
  }

  function onSlider() {
    const sec = +slider.value;
    setClock(sec);
    const row = recordsBySecond.get(sec) || nearestRow(sec);
    if (row) sendMetrics(row);
    renderTranscript(sec);
    updateEvent(sec);
    updateStats(row, sec);
    updateCursor(sec);
  }

  function nearestRow(sec) {
    // simple nearest by absolute difference
    let best = null, bestd = Infinity;
    for (const r of records) {
      const d = Math.abs(r._t - sec);
      if (d < bestd) { best = r; bestd = d; if (d === 0) break; }
    }
    return best;
  }

  const recordsBySecond = new Map();

  async function init() {
    const csv = await loadCSV();
    records = csv.map(r => {
      // normalize keys (remove spaces)
      const rr = Object.assign({}, r, {
        Local_Hour: r['Local Hour'],
        Local_Minute: r['Local Minute'],
        Local_Second: r['Local Second'],
      });
      rr._t = (rr.Local_Hour||0)*3600 + (rr.Local_Minute||0)*60 + (rr.Local_Second||0);
      return rr;
    }).sort((a,b)=>a._t-b._t);

    records.forEach(r => { recordsBySecond.set(r._t, r); });

    tMin = records[0]?._t || 0;
    tMax = records[records.length-1]?._t || tMin;
    slider.min = tMin; slider.max = tMax; slider.value = tMin;
    setClock(tMin);

    timeline = await loadTimeline();
    highlights = extractHighlightsFromMarkdown(timeline);
    window.highlights = highlights;
    renderMarkers();
    renderTranscript(tMin);
    updateEvent(tMin);
    renderHighlights();

    // expose for chart helpers
    window.__tMin = tMin; window.__tMax = tMax;
    window.__records = records;
    window.__recordsBySecond = recordsBySecond;
    window.__nearestRow = nearestRow;
    window.__computeAltitude = computeAltitude;

    // Map init
    setupMap();

    // bind controls
    slider.addEventListener('input', onSlider);
    playBtn.addEventListener('click', () => {
      playing = !playing;
      playBtn.textContent = playing ? '❚❚' : '▶';
      lastTs = performance.now();
      if (playing) rafId = requestAnimationFrame(tickPlay); else cancelAnimationFrame(rafId);
    });

    // keyboard shortcuts
    window.addEventListener('keydown', (e) => {
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : '';
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.code === 'Space') { e.preventDefault(); playBtn.click(); }
      if (e.code === 'ArrowRight') { e.preventDefault(); step(+ (e.shiftKey ? 10 : 1)); }
      if (e.code === 'ArrowLeft') { e.preventDefault(); step(- (e.shiftKey ? 10 : 1)); }
    });

    function step(delta) {
      const v = clamp(+slider.value + delta, tMin, tMax);
      slider.value = Math.round(v);
      slider.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // charts
    setupChart();
    drawChart();
    updateCursor(tMin);
    if (yLeftSel) yLeftSel.addEventListener('change', () => { drawChart(); updateCursor(+slider.value); });
    if (yRightSel) yRightSel.addEventListener('change', () => { drawChart(); updateCursor(+slider.value); });
    if (smoothEl) smoothEl.addEventListener('input', () => { drawChart(); updateCursor(+slider.value); });

    // initial draw with first record
    if (records.length) sendMetrics(records[0]);
    if (records.length) updateStats(records[0], tMin);
  }

  // Wait for libraries, then bring up gauges and the rest of UI
  function libsReady() { return !!(window.d3 && window.g3); }
  (function waitLibs(){
    if (libsReady()) { try { createGauges(); } catch(e) { console.error(e); } try { init(); } catch(e) { console.error(e); } syncLayoutSizes(); setupLayoutObservers(); }
    else setTimeout(waitLibs, 50);
  })();
})();

// Charting helpers (scopes variables inside closure)
(function(){
  // no-op shim if d3 not yet present; init() wires these later
})();

// Injected chart code inside main closure above
// We append concrete implementations below using function declarations

// Chart state
let _chart = {
  gMain: null,
  gXAxis: null,
  gYLeft: null,
  gYRight: null,
  pathLeft: null,
  pathRight: null,
  cursor: null,
  dotLeft: null,
  dotRight: null,
  margin: { top: 10, right: 54, bottom: 26, left: 54 },
  width: 0,
  height: 0,
  x: null,
  yL: null,
  yR: null,
  leftKey: 'altitude',
  rightKey: 'tas'
};

function setupChart() {
  if (!window.d3) return;
  const svg = d3.select('#chart');
  if (svg.select('g.g-main').node()) return; // already
  svg.attr('viewBox', '0 0 100 50'); // will be overridden by resize; helps initial paint

  _chart.gMain = svg.append('g').attr('class', 'g-main');
  _chart.gXAxis = _chart.gMain.append('g').attr('class', 'x-axis');
  _chart.gYLeft = _chart.gMain.append('g').attr('class', 'y-axis y-left');
  _chart.gYRight = _chart.gMain.append('g').attr('class', 'y-axis y-right');
  _chart.pathLeft = _chart.gMain.append('path').attr('class', 'line left').attr('fill', 'none').attr('stroke', getColor('left')).attr('stroke-width', 2);
  _chart.pathRight = _chart.gMain.append('path').attr('class', 'line right').attr('fill', 'none').attr('stroke', getColor('right')).attr('stroke-width', 2).attr('opacity', 0.9);
  _chart.cursor = _chart.gMain.append('line').attr('class', 'x-cursor').attr('stroke', '#8b949e').attr('stroke-width', 1).attr('stroke-dasharray', '3,3');
  _chart.dotLeft = _chart.gMain.append('circle').attr('r', 2.8).attr('fill', getColor('left')).attr('stroke', '#000').attr('stroke-width', 0.5);
  _chart.dotRight = _chart.gMain.append('circle').attr('r', 2.8).attr('fill', getColor('right')).attr('stroke', '#000').attr('stroke-width', 0.5);

  // overlay to capture pointer for seek
  _chart.gMain.append('rect').attr('class', 'overlay').attr('fill', 'transparent')
    .on('pointerdown', function(event) {
      const el = this;
      if (el.setPointerCapture) try { el.setPointerCapture(event.pointerId); } catch {}
      seekFromEvent(event, el);
    })
    .on('pointermove', function(event) {
      if (event.buttons !== 1) return;
      seekFromEvent(event, this);
    })
    .on('pointerup', function(event) {
      if (this.releasePointerCapture) try { this.releasePointerCapture(event.pointerId); } catch {}
    });

  function seekFromEvent(event, target) {
    const [mx] = d3.pointer(event, target);
    const sec = clamp(Math.round(_chart.x.invert(mx)), _chart.x.domain()[0], _chart.x.domain()[1]);
    const sliderEl = document.getElementById('time');
    if (sliderEl) {
      sliderEl.value = sec;
      sliderEl.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  // Responsive
  const ro = 'ResizeObserver' in window ? new ResizeObserver(()=>{ drawChart(); updateCursor(+document.getElementById('time').value || 0); }) : null;
  if (ro) ro.observe(d3.select('#chart').node()); else window.addEventListener('resize', ()=>{ drawChart(); updateCursor(+document.getElementById('time').value || 0); });
}

function getColor(which) {
  const style = getComputedStyle(document.documentElement);
  return which === 'left' ? style.getPropertyValue('--accent').trim() || '#58a6ff' : style.getPropertyValue('--good').trim() || '#3fb950';
}

function drawChart() {
  if (!window.d3) return;
  const svg = d3.select('#chart');
  if (!svg.node()) return;

  // read selected metrics
  const leftKey = document.getElementById('yLeft')?.value || 'altitude';
  const rightKey = document.getElementById('yRight')?.value || 'tas';
  _chart.leftKey = leftKey; _chart.rightKey = rightKey;

  // sizes
  const node = svg.node();
  const { width, height } = node.getBoundingClientRect();
  const m = _chart.margin;
  _chart.width = Math.max(320, Math.round(width));
  _chart.height = Math.max(160, Math.round(height));
  svg.attr('viewBox', `0 0 ${_chart.width} ${_chart.height}`);

  const innerW = _chart.width - m.left - m.right;
  const innerH = _chart.height - m.top - m.bottom;

  // update overlay size
  _chart.gMain.select('rect.overlay').attr('x', m.left).attr('y', m.top).attr('width', innerW).attr('height', innerH);

  // scales
  const t0 = (window.__tMin ?? 0), t1 = (window.__tMax ?? 1);
  _chart.x = d3.scaleLinear().domain([t0, t1]).range([m.left, m.left + innerW]);
  _chart.yL = d3.scaleLinear().domain(extentForKey(leftKey)).nice().range([m.top + innerH, m.top]);
  _chart.yR = d3.scaleLinear().domain(extentForKey(rightKey)).nice().range([m.top + innerH, m.top]);

  // axes
  const xAxis = d3.axisBottom(_chart.x).ticks(Math.min(10, Math.floor(innerW/70))).tickFormat(v => tickLabel(v));
  const yAxisL = d3.axisLeft(_chart.yL).ticks(Math.min(6, Math.floor(innerH/40)));
  const yAxisR = d3.axisRight(_chart.yR).ticks(Math.min(6, Math.floor(innerH/40)));

  _chart.gXAxis.attr('transform', `translate(0,${m.top + innerH})`).call(xAxis);
  _chart.gYLeft.attr('transform', `translate(${m.left},0)`).call(yAxisL);
  _chart.gYRight.attr('transform', `translate(${m.left + innerW},0)`).call(yAxisR);

  // lines
  const seriesL = seriesForKey(leftKey);
  const seriesR = seriesForKey(rightKey);
  const lineGenL = d3.line().x(d => _chart.x(d.t)).y(d => _chart.yL(d.v)).curve(d3.curveMonotoneX).defined(d => Number.isFinite(d.v));
  const lineGenR = d3.line().x(d => _chart.x(d.t)).y(d => _chart.yR(d.v)).curve(d3.curveMonotoneX).defined(d => Number.isFinite(d.v));
  _chart.pathLeft.attr('d', lineGenL(seriesL)).attr('stroke', getColor('left'));
  _chart.pathRight.attr('d', lineGenR(seriesR)).attr('stroke', getColor('right'));

  // legend
  renderLegend(leftKey, rightKey);
}

function renderLegend(leftKey, rightKey) {
  const labels = {
    altitude: 'Altitude (ft)', tas: 'TAS (kt)', gs: 'Ground Speed (kt)', vs: 'Vertical Speed (fpm)', tq1: 'ENG1 TQ (%)', tq2: 'ENG2 TQ (%)'
  };
  const el = document.getElementById('chart-legend');
  if (!el) return;
  el.innerHTML = '';
  const item = (color, text) => {
    const d = document.createElement('div'); d.className = 'item';
    const sw = document.createElement('span'); sw.className = 'sw'; sw.style.background = color; d.appendChild(sw);
    const tx = document.createElement('span'); tx.textContent = text; d.appendChild(tx);
    return d;
  };
  el.appendChild(item(getColor('left'), labels[leftKey] || leftKey));
  el.appendChild(item(getColor('right'), labels[rightKey] || rightKey));
}

function seriesForKey(key) {
  const smooth = Math.max(0, Math.min(50, parseInt(document.getElementById('smooth')?.value || '0', 10)));
  const acc = accessorForKey(key);
  const recs = (window.__records || []);
  const arr = recs.map(r => ({ t: r._t, v: acc(r) }));
  if (!smooth) return arr.filter(d => Number.isFinite(d.v));
  const kernel = movingAverageKernel(smooth);
  const smoothed = convolve1D(arr, kernel);
  return smoothed.filter(d => Number.isFinite(d.v));
}

function extentForKey(key) {
  const ser = seriesForKey(key);
  if (!ser.length) return [0, 1];
  let lo = Infinity, hi = -Infinity;
  for (const d of ser) { if (d.v < lo) lo = d.v; if (d.v > hi) hi = d.v; }
  if (!(Number.isFinite(lo) && Number.isFinite(hi))) return [0, 1];
  if (lo === hi) { lo -= 1; hi += 1; }
  return [lo, hi];
}

function accessorForKey(key) {
  switch (key) {
    case 'altitude': return (r) => (window.__computeAltitude ? window.__computeAltitude(r) : (r && r['Altitude Radar']) || 0);
    case 'tas': return (r) => +r.TAS || 0;
    case 'gs': return (r) => +r['Ground Speed'] || 0;
    case 'vs': return (r) => +r['Vertical Speed'] || 0;
    case 'tq1': return (r) => +r['Eng 1 Torque'] || 0;
    case 'tq2': return (r) => +r['Eng 2 Torque'] || 0;
    default: return () => NaN;
  }
}

function tickLabel(sec) {
  const h = Math.floor(sec/3600)%24, m = Math.floor(sec/60)%60, s = Math.floor(sec%60);
  const pad = (x) => x.toString().padStart(2, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

function updateCursor(sec) {
  if (!_chart.x) return;
  const x = _chart.x(sec);
  const m = _chart.margin;
  const innerH = _chart.height - m.top - m.bottom;
  _chart.cursor.attr('x1', x).attr('x2', x).attr('y1', m.top).attr('y2', m.top + innerH);

  // dots
  const lAcc = accessorForKey(_chart.leftKey);
  const rAcc = accessorForKey(_chart.rightKey);
  const rbs = window.__recordsBySecond;
  const nr = window.__nearestRow;
  const row = (rbs && rbs.get ? rbs.get(sec) : null) || (typeof nr === 'function' ? nr(sec) : null);
  if (row) {
    const yL = _chart.yL(lAcc(row));
    const yR = _chart.yR(rAcc(row));
    _chart.dotLeft.attr('cx', x).attr('cy', yL).attr('opacity', Number.isFinite(yL) ? 1 : 0);
    _chart.dotRight.attr('cx', x).attr('cy', yR).attr('opacity', Number.isFinite(yR) ? 1 : 0);
  }

  // sync map
  updateMapPosition(sec);
}

function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }

// Map state and helpers
let _map = { map: null, path: null, marker: null, coords: [] };

function setupMap() {
  const el = document.getElementById('map');
  if (!el || typeof L === 'undefined') return;
  if (_map.map) return;
  _map.map = L.map(el, { zoomControl: true, attributionControl: false });
  const tiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
  });
  tiles.addTo(_map.map);
  // Load KML path via fetch (simple parser for coordinates)
  fetch('MOJO69 Flight Path.kml').then(r => r.text()).then(txt => {
    const coords = parseKmlCoordinates(txt);
    _map.coords = coords;
    if (coords.length) {
      const latlngs = coords.map(c => [c[1], c[0]]);
      _map.path = L.polyline(latlngs, { color: getColor('left') || '#58a6ff', weight: 3, opacity: 0.9 }).addTo(_map.map);
      _map.marker = L.circleMarker(latlngs[0], { radius: 5, color: '#fff', weight: 1, fillColor: '#ff6b6b', fillOpacity: 0.9 }).addTo(_map.map);
      _map.map.fitBounds(_map.path.getBounds(), { padding: [12,12] });
    }
  }).catch(()=>{});
}

function parseKmlCoordinates(txt) {
  const coords = [];
  const re = /<coordinates>([\s\S]*?)<\/coordinates>/g;
  let m;
  while ((m = re.exec(txt))) {
    const block = m[1].trim();
    const pairs = block.split(/\s+/);
    for (const p of pairs) {
      const parts = p.split(',');
      if (parts.length >= 2) {
        const lon = parseFloat(parts[0]);
        const lat = parseFloat(parts[1]);
        if (Number.isFinite(lat) && Number.isFinite(lon)) coords.push([lon, lat]);
      }
    }
  }
  return coords;
}

function updateMapPosition(sec) {
  if (!_map.map || !_map.coords.length) return;
  // naive mapping by index across time range
  const t0 = (window.__tMin || 0), t1 = (window.__tMax || 1);
  const frac = (sec - t0) / Math.max(1, (t1 - t0));
  const idx = Math.max(0, Math.min(_map.coords.length - 1, Math.round(frac * (_map.coords.length - 1))));
  const c = _map.coords[idx];
  const latlng = [c[1], c[0]];
  if (_map.marker) _map.marker.setLatLng(latlng);
}

// Heading along KML path for current time
function headingAtTime(sec) {
  if (!_map.coords || _map.coords.length < 2) return 0;
  const t0 = (window.__tMin || 0), t1 = (window.__tMax || 1);
  const frac = (sec - t0) / Math.max(1, (t1 - t0));
  let idx = Math.max(0, Math.min(_map.coords.length - 2, Math.round(frac * (_map.coords.length - 2))));
  // choose forward pair where possible
  const c1 = _map.coords[idx];
  const c2 = _map.coords[idx + 1];
  return bearingFromLonLat(c1[0], c1[1], c2[0], c2[1]);
}

function bearingFromLonLat(lon1, lat1, lon2, lat2) {
  const toRad = (d) => d * Math.PI / 180;
  const toDeg = (r) => r * 180 / Math.PI;
  const φ1 = toRad(lat1), φ2 = toRad(lat2);
  const Δλ = toRad(lon2 - lon1);
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  let θ = toDeg(Math.atan2(y, x));
  if (!Number.isFinite(θ)) θ = 0;
  return (θ + 360) % 360;
}

// Keep map height in sync with gauges/panel height
function syncLayoutSizes() {
  const g = document.getElementById('gauges');
  const mapEl = document.getElementById('map');
  if (!g || !mapEl) return;
  const rect = g.getBoundingClientRect();
  const h = Math.max(360, Math.round(rect.height));
  if (h && Math.abs((mapEl.offsetHeight||0) - h) > 2) {
    mapEl.style.height = h + 'px';
    if (_map && _map.map && typeof _map.map.invalidateSize === 'function') {
      setTimeout(()=>{ try { _map.map.invalidateSize(); } catch {} }, 0);
    }
  }
}

function setupLayoutObservers() {
  const g = document.getElementById('gauges');
  if ('ResizeObserver' in window && g) {
    try {
      const ro = new ResizeObserver(()=>{ syncLayoutSizes(); });
      ro.observe(g);
    } catch {}
  } else {
    window.addEventListener('resize', syncLayoutSizes);
  }
}

// Simple symmetric moving-average kernel
function movingAverageKernel(radius) {
  const r = Math.max(0, Math.floor(radius));
  const len = r * 2 + 1;
  const w = 1 / len;
  const k = new Array(len).fill(w);
  return k;
}

function convolve1D(series, kernel) {
  const r = Math.floor(kernel.length / 2);
  const out = new Array(series.length);
  for (let i = 0; i < series.length; i++) {
    let acc = 0, wsum = 0;
    for (let j = -r; j <= r; j++) {
      const idx = i + j;
      if (idx < 0 || idx >= series.length) continue;
      const w = kernel[j + r];
      const v = series[idx].v;
      if (Number.isFinite(v)) { acc += v * w; wsum += w; }
    }
    const v = wsum ? acc / wsum : NaN;
    out[i] = { t: series[i].t, v };
  }
  return out;
}

// Highlights from markdown timeline
function extractHighlightsFromMarkdown(timeline) {
  // Simple heuristics: pick key calls like "IMC", "autopilot", "Level", "Climb", "Impact"
  const keys = [/IMC/i, /autopilot/i, /Level/i, /Climb/i, /Impact|IMPACTO/i, /wires/i, /water/i];
  return timeline.filter(ev => keys.some(k => k.test(ev.text))).slice(0, 50);
}

function renderHighlights() {
  if (!document.getElementById('highlight-list')) return;
  const el = document.getElementById('highlight-list');
  el.innerHTML = '';
  const toTime = (sec) => {
    const h = Math.floor(sec/3600)%24, m = Math.floor(sec/60)%60, s = Math.floor(sec%60);
    const pad = (x) => x.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(s)}`;
  };
  for (const h of (window.highlights || [])) {
    const d = document.createElement('div');
    d.className = 'highlight';
    d.innerHTML = `<div class="t">${toTime(h.t)}</div><div class="tx">${h.text}</div>`;
    d.addEventListener('click', () => {
      const sliderEl = document.getElementById('time');
      if (sliderEl) {
        sliderEl.value = Math.round(h.t);
        sliderEl.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    el.appendChild(d);
  }
}


