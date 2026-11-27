// Hybrid ABR controller for hls.js v1 (team algorithm, week 4).
// Pure decision logic = HybridCore (no browser needed, unit-tested against models/abr_custom.py).
// makeController(Hls) wraps it in the controller API that hls.js expects (config.abrController).
(function (root) {
  'use strict';
  const DEFAULTS = { a_down: 0.7, a_up: 0.35, m_down: 0.9, m_up: 0.85, n_up: 3, buf_up: 1.5, buf_emerg: 1.0, hold: 6.0 };

  class HybridCore {
    // bw: BANDWIDTH of every level in kbit/s, ascending
    constructor(bw, params) {
      this.bw = bw; this.p = Object.assign({}, DEFAULTS, params || {});
      this.est = null; this.streak = 0; this.lastDown = -1e9;
    }
    _best(est, margin) {
      let t = 0;
      for (let i = 0; i < this.bw.length; i++) if (margin * est >= this.bw[i]) t = i;
      return t;
    }
    // level: level of the segment just downloaded; kbit: its size; durS: its load time (s);
    // bufS: seconds of video buffered ahead; nowS: clock (s). Returns the level for the next segment.
    onSegment(level, kbit, durS, bufS, nowS) {
      const p = this.p, s = kbit / Math.max(durS, 0.05);
      if (this.est === null) this.est = s;
      else this.est += (s < this.est ? p.a_down : p.a_up) * (s - this.est);
      const cur = level;
      let target = this._best(this.est, p.m_down);
      if (target < cur) {
        if (bufS < p.buf_emerg) target = Math.min(target, this._best(Math.min(this.est, s), 0.7));
        this.streak = 0; this.lastDown = nowS;
        return target;
      }
      const ok = cur < this.bw.length - 1 && p.m_up * this.est >= this.bw[cur + 1] &&
                 bufS >= p.buf_up && nowS - this.lastDown >= p.hold;
      this.streak = ok ? this.streak + 1 : 0;
      if (this.streak >= p.n_up) { this.streak = 0; return cur + 1; }
      return cur;
    }
  }

  function makeController(Hls) {
    return class HybridAbrController {
      constructor(hls) {
        this.hls = hls; this.core = null; this.target = 0; this.lastSampleKbps = 0;
        this.bwEstimator = {                       // read by hls.bandwidthEstimate and others
          getEstimate: () => (this.core && this.core.est ? this.core.est * 1000 : 0),
          getEstimateTTFB: () => 100, canEstimate: () => !!(this.core && this.core.est),
          defaultEstimate: 500000, sample() {}, sampleTTFB() {}, update() {}, destroy() {}
        };
        hls.on(Hls.Events.MANIFEST_PARSED, this.onManifest, this);
        hls.on(Hls.Events.FRAG_LOADED, this.onFragLoaded, this);
      }
      onManifest() {
        this.core = new HybridCore(this.hls.levels.map(l => l.bitrate / 1000));
        this.target = 0;                           // start on the lowest rendition, climb in a few segments
      }
      onFragLoaded(_, data) {
        if (!this.core || (data.frag.type && data.frag.type !== 'main')) return;
        const st = data.frag.stats, durS = (st.loading.end - st.loading.start) / 1000;
        if (!(durS > 0) || !st.loaded) return;
        const v = this.hls.media; let buf = 0;
        if (v && v.buffered.length) buf = Math.max(0, v.buffered.end(v.buffered.length - 1) - v.currentTime);
        this.target = this.core.onSegment(data.frag.level, st.loaded * 8 / 1000, durS, buf, performance.now() / 1000);
      }
      get firstAutoLevel() { return 0; }
      get forcedAutoLevel() { return -1; }
      get nextAutoLevel() { return this.target; }
      set nextAutoLevel(n) { this.target = Math.max(0, n | 0); }   // hls.js forces a level after load errors
      resetEstimator() { if (this.core) this.core.est = null; }
      destroy() {
        this.hls.off(Hls.Events.MANIFEST_PARSED, this.onManifest, this);
        this.hls.off(Hls.Events.FRAG_LOADED, this.onFragLoaded, this);
      }
    };
  }

  const api = { HybridCore, DEFAULTS, makeController };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.HybridAbr = api;
})(typeof self !== 'undefined' ? self : this);
