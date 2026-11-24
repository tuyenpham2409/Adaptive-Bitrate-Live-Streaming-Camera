// abr_pipeline_v3.cpp - SystemC (TLM-style) model of the streaming camera pipeline, week 3.
//
// What changed w.r.t. week 2 (abr_pipeline.cpp):
//   * parameters now come from the board: 3 renditions on the shared H.264 hardware encoder
//     (bcm2835-codec), 30 fps, measured speed 1.0x and 0 dropped frames (test T8)
//   * the HLS segmenter closes a segment every GOP = seg*fps encoded frames (1 s or 2 s)
//   * an audio branch (AAC, 1024 samples/frame at 48 kHz) feeds the same segments
//   * an HLS client module "joins" the live stream at random times and measures the
//     glass-to-glass latency for a given liveSyncDurationCount (hls.js), to compare with T11
//
// Build : g++ -std=c++17 -I$SYSTEMC/include abr_pipeline_v3.cpp -L$SYSTEMC/lib -lsystemc -o abr_pipeline_v3
// Run   : ./abr_pipeline_v3 --name S1B --ladder planned --seg 1 --sync 3 [--dur 60] [--enc 62.2]
#include <systemc>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include <ostream>
using namespace sc_core;

struct Rend { const char* name; int w, h; double kbps; };   // kbps = real average (video+audio)
struct Frame { int id; double t_cap; };
struct Enc   { int r; int id; double t_cap; double t_done; };
struct Seg   { double c_end; double t_pub; int audio; };
// sc_fifo<T> needs operator<< for its print() method
inline std::ostream& operator<<(std::ostream& o, const Frame& f) { return o << "frame " << f.id; }
inline std::ostream& operator<<(std::ostream& o, const Enc& e)   { return o << "enc r" << e.r << " f" << e.id; }

struct Ctx {                                  // simulation-wide parameters and counters
    std::string name = "S", ladder = "planned";
    double seg = 1.0, fps = 30.0, enc_mpx = 62.2, dur = 60.0, link_kbps = 20000.0;
    int sync = 3, fifo = 8, joins = 300;
    std::vector<Rend> L;
    long produced = 0, dropped = 0, encoded = 0, audio_frames = 0;
    double busy = 0, lat_sum = 0, lat_max = 0;
    std::vector<Seg> segs;                    // segments of rendition 0 (the top one)
    std::vector<double> join_lat;
} G;

static double sec(sc_time t) { return t.to_seconds(); }

SC_MODULE(Camera) {                           // UVC webcam, MJPEG 30 fps -> decoder -> split
    sc_fifo<Frame>* out;
    SC_CTOR(Camera) { SC_THREAD(run); }
    void run() {
        const double T = 1.0 / G.fps;
        for (int i = 0; sec(sc_time_stamp()) < G.dur; ++i) {
            wait(sc_time(T, SC_SEC));
            Frame f{i, sec(sc_time_stamp())};
            ++G.produced;
            if (!out->nb_write(f)) ++G.dropped;     // encoder queue full -> frame dropped
        }
    }
};

SC_MODULE(HwEncoder) {                        // ONE hardware encoder shared by all renditions
    sc_fifo<Frame>* in; sc_fifo<Enc>* out;
    SC_CTOR(HwEncoder) { SC_THREAD(run); }
    void run() {
        while (true) {
            Frame f = in->read();
            for (size_t r = 0; r < G.L.size(); ++r) {
                double t = (double)G.L[r].w * G.L[r].h / (G.enc_mpx * 1e6);   // pixels / throughput
                wait(sc_time(t, SC_SEC)); G.busy += t;
                out->write(Enc{(int)r, f.id, f.t_cap, sec(sc_time_stamp())});
            }
            double lat = sec(sc_time_stamp()) - f.t_cap;
            G.lat_sum += lat; G.lat_max = std::max(G.lat_max, lat); ++G.encoded;
        }
    }
};

SC_MODULE(AudioEnc) {                         // software AAC: 1024 samples @ 48 kHz = 21.33 ms
    SC_CTOR(AudioEnc) { SC_THREAD(run); }
    void run() { while (sec(sc_time_stamp()) < G.dur) { wait(sc_time(1024.0 / 48000.0, SC_SEC)); ++G.audio_frames; } }
};

SC_MODULE(Segmenter) {                        // HLS muxer: one segment per GOP and rendition
    sc_fifo<Enc>* in;
    SC_CTOR(Segmenter) { SC_THREAD(run); }
    void run() {
        std::vector<long> cnt(G.L.size(), 0); long a0 = 0;
        const long gop = std::lround(G.seg * G.fps);
        while (true) {
            Enc e = in->read();
            if (++cnt[e.r] % gop == 0 && e.r == 0) {
                G.segs.push_back(Seg{e.t_cap + 1.0 / G.fps, e.t_done, (int)(G.audio_frames - a0)});
                a0 = G.audio_frames;
            }
        }
    }
};

SC_MODULE(HlsClient) {                        // joins the live stream like hls.js with liveSyncDurationCount
    SC_CTOR(HlsClient) { SC_THREAD(run); }
    void run() {
        std::mt19937 rng(42); std::uniform_real_distribution<double> U(10.0, G.dur - 2.0);
        std::vector<double> tj(G.joins); for (auto& x : tj) x = U(rng);
        std::sort(tj.begin(), tj.end());
        const double fetch = 0.01 + G.L[0].kbps * G.seg / G.link_kbps;       // playlist RTT + first segment
        for (double t : tj) {
            if (t > sec(sc_time_stamp())) wait(sc_time(t - sec(sc_time_stamp()), SC_SEC));
            const Seg* last = nullptr;
            for (const Seg& s : G.segs) if (s.t_pub <= t) last = &s; else break;
            if (!last) continue;
            // playback starts sync*seg behind the end of the newest published segment
            double playhead = last->c_end - G.sync * G.seg;
            G.join_lat.push_back((t + fetch) - playhead);
        }
        sc_stop();
    }
};

int sc_main(int argc, char** argv) {
    for (int i = 1; i + 1 < argc; i += 2) {
        std::string k = argv[i], v = argv[i + 1];
        if (k == "--name") G.name = v; else if (k == "--ladder") G.ladder = v;
        else if (k == "--seg") G.seg = atof(v.c_str()); else if (k == "--sync") G.sync = atoi(v.c_str());
        else if (k == "--dur") G.dur = atof(v.c_str()); else if (k == "--enc") G.enc_mpx = atof(v.c_str());
        else if (k == "--fifo") G.fifo = atoi(v.c_str());
    }
    G.L = {{"720p", 1280, 720, 2628}, {"540p", 960, 540, 1328}, {"360p", 640, 360, 628}};
    if (G.ladder == "plus1080") G.L.insert(G.L.begin(), Rend{"1080p", 1920, 1080, 5128});
    if (G.ladder == "plus480")  G.L.push_back(Rend{"480p", 854, 480, 1000});

    sc_fifo<Frame> cam2enc(G.fifo); sc_fifo<Enc> enc2seg(100000);
    Camera cam("cam"); HwEncoder enc("enc"); AudioEnc aud("aud"); Segmenter seg("seg"); HlsClient cli("cli");
    cam.out = &cam2enc; enc.in = &cam2enc; enc.out = &enc2seg; seg.in = &enc2seg;
    sc_start(sc_time(G.dur + 1.0, SC_SEC));

    double px = 0; for (auto& r : G.L) px += (double)r.w * r.h;
    double nominal = 100.0 * px * G.fps / (G.enc_mpx * 1e6);
    auto st = [&](std::vector<double> v, double& mn, double& mean, double& mx) {
        if (v.empty()) { mn = mean = mx = NAN; return; }
        mn = *std::min_element(v.begin(), v.end()); mx = *std::max_element(v.begin(), v.end());
        double s = 0; for (double x : v) s += x; mean = s / v.size(); };
    double mn, mean, mx; st(G.join_lat, mn, mean, mx);
    double audio_per_seg = 0; for (auto& s : G.segs) audio_per_seg += s.audio;
    if (!G.segs.empty()) audio_per_seg /= G.segs.size();
    std::printf("%s,%s,%g,%d,%.1f,%.1f,%ld,%ld,%.1f,%.1f,%zu,%.1f,%.2f,%.2f,%.2f\n", G.name.c_str(), G.ladder.c_str(),
                G.seg, G.sync, nominal, 100.0 * G.busy / sec(sc_time_stamp()), G.produced, G.dropped,
                G.encoded ? 1e3 * G.lat_sum / G.encoded : 0.0, 1e3 * G.lat_max, G.segs.size(), audio_per_seg, mn, mean, mx);
    return 0;
}
