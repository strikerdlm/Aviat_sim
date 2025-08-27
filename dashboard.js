// Minimal D3 helpers from g3 (already bundled with g3)
/* global g3 */

(function () {
  const host = document.getElementById('gauges');
  // panel will create and set g3.activeController internally

  // Layout gauges (two rows): Airspeed, Altitude, Vertical Speed, Engine Torques
  const panel = g3.panel().width(1280).height(620).smooth(true).grid(false);

  const row1y = 150, row2y = 450;

  // Airspeed (TAS)
  const gaugeTAS = g3.gauge()
    .metric('tas')
    .unit('knot')
    .measure(d3.scaleLinear().domain([0, 200]).range([30, 350]))
    .append(
      g3.gaugeFace(),
      g3.axisTicks().step(5).size(10),
      g3.axisTicks().step(10).size(15).style('stroke-width: 2'),
      g3.axisLabels().step(20).inset(30),
      g3.gaugeLabel('TAS KT').y(-33),
      g3.indicatePointer().shape('sword')
    );

  // Altitude (Radar Alt or Altitude)
  const gaugeALT = g3.gauge()
    .metric('altitude')
    .unit('ft')
    .measure(d3.scaleLinear().domain([0, 1000]).range([0, 360]))
    .append(
      g3.gaugeFace(),
      g3.axisTicks().step(20),
      g3.axisTicks().step(100).size(15).style('stroke-width: 2'),
      g3.axisLabels().step(100).format(v => v/100).size(20),
      g3.gaugeLabel('ALT (ft)').y(-33),
      g3.indicatePointer().shape('blade'),
      g3.indicatePointer().shape('dagger').rescale(v => v/100)
    );

  // Vertical Speed (ft/min)
  const gaugeVSI = g3.gauge()
    .metric('vs')
    .unit('ft/min')
    .measure(d3.scaleLinear().domain([-2000, 2000]).range([90, 450]))
    .append(
      g3.gaugeFace(),
      g3.axisTicks().step(100).size(5),
      g3.axisTicks().step(500).size(15).style('stroke-width: 2'),
      g3.axisLabels().step(1000).format(v => Math.abs(v/100)).size(16),
      g3.gaugeLabel('VSI').y(-25).size(12),
      g3.indicatePointer().shape('sword')
    );

  // Engine torque (% proxy)
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

  // Place gauges
  const put = g3.put();
  put.x(160).y(row1y).scale(1.2).append(gaugeTAS);
  put.x(480).y(row1y).scale(1.2).append(gaugeALT);
  put.x(800).y(row1y).scale(1.2).append(gaugeVSI);
  put.x(1120).y(row1y).scale(1.2).append(g3.gauge().append(g3.gaugeFace(), g3.gaugeLabel(''))); // spacer aesthetic

  put.x(320).y(row2y).scale(1.2).append(tq1);
  put.x(640).y(row2y).scale(1.2).append(tq2);

  // mount
  d3.select(host).call(panel.append(put));

  // Controls/dom
  const playBtn = document.getElementById('btn-play');
  const speedSel = document.getElementById('speed');
  const slider = document.getElementById('time');
  const markers = document.getElementById('markers');
  const clock = document.getElementById('clock');
  const transcriptEl = document.getElementById('transcript-list');
  const eventBody = document.getElementById('event-body');

  // Data holders
  let records = [];
  let timeline = [];
  let tMin = 0, tMax = 0;
  let playing = false;
  let rafId = null;
  let lastTs = 0;

  // d3 is provided via script tag

  // CSV parsing
  function loadCSV() {
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
    near.forEach(r => {
      const div = document.createElement('div');
      div.className = 'line' + (r._t === nowSec ? ' now' : '');
      const time = `${r.Local_Hour?.toString().padStart(2,'0') ?? '--'}:${r.Local_Minute?.toString().padStart(2,'0') ?? '--'}:${r.Local_Second?.toString().padStart(2,'0') ?? '--'}`;
      div.innerHTML = `<div class="t">${time}</div><div class="crew">${r.Crew || ''}</div><div class="say">${(r.Transcripts||'').replace(/^"+|"+$/g,'')}</div>`;
      transcriptEl.appendChild(div);
    });
  }

  function updateEvent(nowSec) {
    if (!timeline.length) { eventBody.textContent = '—'; return; }
    // find latest event <= now
    let best = null;
    for (const ev of timeline) if (ev.t <= nowSec) best = ev; else break;
    eventBody.textContent = best ? best.text : '—';
  }

  function sendMetrics(row) {
    const metrics = {
      latest: row._t,
      units: {
        tas: 'knot', altitude: 'ft', vs: 'ft/min', tq1: 'percent', tq2: 'percent'
      },
      metrics: {
        tas: +row.TAS || 0,
        altitude: (Number.isFinite(row['Altitude Radar']) && row['Altitude Radar'] >= 0) ? row['Altitude Radar'] : (Number.isFinite(row['Ai Pressure']) ? (row['Ai Pressure']*1.0) : 0),
        vs: +row['Vertical Speed'] || 0,
        tq1: +row['Eng 1 Torque'] || 0,
        tq2: +row['Eng 2 Torque'] || 0
      }
    };
    if (g3.activeController) g3.activeController(metrics, sel => sel.transition().duration(180));
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
    renderMarkers();
    renderTranscript(tMin);
    updateEvent(tMin);

    // bind controls
    slider.addEventListener('input', onSlider);
    playBtn.addEventListener('click', () => {
      playing = !playing;
      playBtn.textContent = playing ? '❚❚' : '▶';
      lastTs = performance.now();
      if (playing) rafId = requestAnimationFrame(tickPlay); else cancelAnimationFrame(rafId);
    });

    // initial draw with first record
    if (records.length) sendMetrics(records[0]);
  }

  // d3 minimal shims via existing d3 from g3 bundle
  function d3Ready() { return !!window.d3; }
  (function waitD3(){ if (d3Ready()) init(); else setTimeout(waitD3, 50); })();
})();


