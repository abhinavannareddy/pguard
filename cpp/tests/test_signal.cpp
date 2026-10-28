// Self-contained C++ tests (no framework). Run through ctest.
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "pguard_signal.h"

static int failures = 0;
#define CHECK(c)                                                    \
  do {                                                              \
    if (!(c)) {                                                     \
      std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c);       \
      ++failures;                                                   \
    }                                                               \
  } while (0)

static const pg_params P{2.0, 5.0, 1.0, 0.2, 0.5, 0.8};

static void series(const std::vector<double> &t, const std::vector<int32_t> &r, double t1,
                   std::vector<pg_window> &out, int64_t *n) {
  out.assign(64, pg_window{});
  *n = pg_extract_series(t.data(), r.data(), t.size(), 0.0, t1, &P, out.data(), out.size());
}

int main() {
  std::vector<pg_window> w;
  int64_t n = 0;

  {  // constant signal at 5 Hz is QUIET with full quality
    std::vector<double> t;
    std::vector<int32_t> r;
    for (int i = 0; i < 50; ++i) {
      t.push_back(i / 5.0);
      r.push_back(-41);
    }
    series(t, r, 10.0, w, &n);
    CHECK(n == 5);
    for (int64_t i = 0; i < n; ++i) CHECK(w[i].state == PG_QUIET && w[i].quality > 0.99);
  }
  {  // alternating -49/-41 is MOTION
    std::vector<double> t;
    std::vector<int32_t> r;
    for (int i = 0; i < 50; ++i) {
      t.push_back(i / 5.0);
      r.push_back(i % 2 ? -49 : -41);
    }
    series(t, r, 10.0, w, &n);
    for (int64_t i = 0; i < n; ++i) CHECK(w[i].state == PG_MOTION);
  }
  {  // a gap is NO_DATA, never QUIET
    std::vector<double> t;
    std::vector<int32_t> r;
    for (int i = 0; i < 50; ++i)
      if (i < 10 || i >= 30) {
        t.push_back(i / 5.0);
        r.push_back(-41);
      }
    series(t, r, 10.0, w, &n);
    CHECK(w[2].state == PG_NO_DATA && (w[2].flags & PG_FLAG_NO_SAMPLES));
    CHECK(w[0].state == PG_QUIET);
  }
  {  // an all-corrupt window is NO_DATA with the corrupt flag
    std::vector<double> t;
    std::vector<int32_t> r;
    for (int i = 0; i < 10; ++i) {
      t.push_back(i / 5.0);
      r.push_back(12);
    }
    series(t, r, 2.0, w, &n);
    CHECK(n == 1 && w[0].state == PG_NO_DATA && (w[0].flags & PG_FLAG_CORRUPT));
  }
  {  // invalid params and small buffers are errors, not silent results
    pg_params bad = P;
    bad.window_s = 0.0;
    pg_window out[1];
    CHECK(pg_extract_series(nullptr, nullptr, 0, 0, 10, &bad, out, 1) == PG_ERR_PARAMS);
    CHECK(pg_extract_series(nullptr, nullptr, 0, 0, 10, &P, out, 1) == PG_ERR_BUFFER);
    CHECK(pg_extract_series(nullptr, nullptr, 0, 0, 10, nullptr, out, 1) == PG_ERR_NULL);
  }
  {  // the ring buffer overwrites the oldest sample and counts the drop
    pg_ring *ring = pg_ring_create(2);
    CHECK(ring != nullptr);
    CHECK(pg_ring_push(ring, 1, -40) == 0 && pg_ring_push(ring, 2, -41) == 0);
    CHECK(pg_ring_push(ring, 3, -42) == 1 && pg_ring_dropped(ring) == 1);
    double t[4];
    int32_t r[4];
    CHECK(pg_ring_drain(ring, t, r, 4) == 2 && t[0] == 2 && r[1] == -42);
    CHECK(pg_ring_create(0) == nullptr);
    pg_ring_destroy(ring);
  }
  CHECK(pg_abi_version() == 1);
  std::printf(failures ? "C++ tests FAILED: %d\n" : "C++ tests passed\n", failures);
  return failures ? EXIT_FAILURE : EXIT_SUCCESS;
}
