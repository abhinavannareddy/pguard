// C++20 implementation of the windowed feature extractor, parity-tested against Python.
#include "pguard_signal.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

namespace {
constexpr double kEps = 1e-9;
constexpr int32_t kRssiMin = -120, kRssiMax = -1;
constexpr double kMaxWindows = 1e9;  // far above any real recording; bounds memory

double round4(double v) { return std::round(v * 1e4) / 1e4; }

bool valid_params(const pg_params &p) {
  const auto pos = [](double v) { return std::isfinite(v) && v > 0.0; };
  const auto frac = [](double v) { return std::isfinite(v) && v >= 0.0 && v <= 1.0; };
  return pos(p.window_s) && pos(p.expected_hz) && pos(p.stale_s) && frac(p.min_coverage) &&
         frac(p.min_quality) && pos(p.motion_threshold_db);
}

struct Bucket {
  std::vector<double> values;
  double last_t = 0.0;
  size_t corrupt = 0;
};

pg_window finish(double t_start, const Bucket &b, const pg_params &p) {
  pg_window w{};
  w.t_start = t_start;
  w.t_end = t_start + p.window_s;
  w.n_valid = b.values.size();
  w.n_corrupt = b.corrupt;
  const double coverage =
      std::min(1.0, static_cast<double>(w.n_valid) / (p.expected_hz * p.window_s));
  const size_t received = w.n_valid + b.corrupt;
  w.quality =
      received ? round4(coverage * (1.0 - static_cast<double>(b.corrupt) / received)) : 0.0;
  if (!b.values.empty()) {
    const double mean = std::accumulate(b.values.begin(), b.values.end(), 0.0) / b.values.size();
    w.mean_dbm = round4(mean);
    w.has_mean = 1;
    if (b.values.size() >= 2) {
      double ss = 0.0;
      for (double v : b.values) ss += (v - mean) * (v - mean);
      w.motion_energy = round4(std::sqrt(ss / b.values.size()));
      w.has_energy = 1;
    }
  }
  const bool stale = !b.values.empty() && w.t_end - b.last_t > p.stale_s + kEps;
  if (b.values.empty()) w.flags |= PG_FLAG_NO_SAMPLES;
  if (b.corrupt > 0) w.flags |= PG_FLAG_CORRUPT;
  if (coverage < p.min_quality) w.flags |= PG_FLAG_LOW_COVERAGE;
  if (stale) w.flags |= PG_FLAG_STALE;
  if (coverage < p.min_coverage) {
    w.state = PG_NO_DATA;
  } else if (w.quality < p.min_quality || stale || !w.has_energy) {
    w.state = PG_UNCERTAIN;
  } else {
    w.state = w.motion_energy >= p.motion_threshold_db ? PG_MOTION : PG_QUIET;
  }
  return w;
}
}  // namespace

extern "C" {

PG_API int32_t pg_abi_version(void) { return 1; }

PG_API int64_t pg_extract_series(const double *t, const int32_t *rssi, size_t n, double t0,
                                 double t1, const pg_params *p, pg_window *out, size_t max_out) {
  if (!p || (n && (!t || !rssi)) || (max_out && !out)) return PG_ERR_NULL;
  if (!valid_params(*p) || !std::isfinite(t0) || !std::isfinite(t1)) return PG_ERR_PARAMS;
  const double raw = (t1 - t0) / p->window_s + kEps;
  if (!std::isfinite(raw)) return PG_ERR_PARAMS;
  // Range-check before converting: a double outside the integer range is undefined behaviour.
  if (raw >= static_cast<double>(max_out) + 1.0 || raw >= kMaxWindows) return PG_ERR_BUFFER;
  const int64_t windows = raw < 1.0 ? 0 : static_cast<int64_t>(raw);

  std::vector<size_t> order(n);
  std::iota(order.begin(), order.end(), size_t{0});
  std::stable_sort(order.begin(), order.end(), [&](size_t a, size_t b) { return t[a] < t[b]; });

  std::vector<Bucket> buckets(static_cast<size_t>(windows));
  for (size_t idx : order) {
    if (!std::isfinite(t[idx]) || t[idx] < t0) continue;
    const double d = (t[idx] - t0) / p->window_s + kEps;
    if (!(d >= 0.0) || d >= static_cast<double>(windows)) continue;
    const auto i = static_cast<int64_t>(d);
    Bucket &b = buckets[static_cast<size_t>(i)];
    if (rssi[idx] >= kRssiMin && rssi[idx] <= kRssiMax) {
      b.values.push_back(rssi[idx]);
      b.last_t = t[idx];
    } else {
      ++b.corrupt;
    }
  }
  for (int64_t i = 0; i < windows; ++i)
    out[i] = finish(t0 + static_cast<double>(i) * p->window_s, buckets[static_cast<size_t>(i)], *p);
  return windows;
}

}  // extern "C"
