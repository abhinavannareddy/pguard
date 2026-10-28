/* PGuard signal core: C ABI. Mirrors the Python reference in src/pguard/signal/features.py.
 * Missing, stale or corrupt input is NO_DATA or UNCERTAIN, never QUIET (safety rule S4). */
#ifndef PGUARD_SIGNAL_H
#define PGUARD_SIGNAL_H

#include <stddef.h>
#include <stdint.h>

#ifdef _WIN32
#define PG_API __declspec(dllexport)
#else
#define PG_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum pg_state { PG_NO_DATA = 0, PG_UNCERTAIN = 1, PG_QUIET = 2, PG_MOTION = 3 };
enum pg_flag {
  PG_FLAG_NO_SAMPLES = 1u, PG_FLAG_CORRUPT = 2u, PG_FLAG_LOW_COVERAGE = 4u, PG_FLAG_STALE = 8u
};
enum pg_status { PG_OK = 0, PG_ERR_PARAMS = -1, PG_ERR_BUFFER = -2, PG_ERR_NULL = -3 };

typedef struct {
  double window_s, expected_hz, stale_s, min_coverage, min_quality, motion_threshold_db;
} pg_params;

typedef struct {
  double t_start, t_end;
  size_t n_valid, n_corrupt;
  double quality, mean_dbm, motion_energy;
  int32_t has_mean, has_energy;
  uint32_t flags;
  int32_t state;
} pg_window;

/* Windows [t0, t1) of length window_s. Samples may be unordered. Returns the number of
 * windows written, or a negative pg_status. */
PG_API int64_t pg_extract_series(const double *t, const int32_t *rssi, size_t n, double t0,
                                 double t1, const pg_params *p, pg_window *out, size_t max_out);

PG_API int32_t pg_abi_version(void);

/* Driver shim: a fixed-size ring buffer between a capture driver and the core. When full it
 * overwrites the oldest sample and COUNTS the drop, so loss is visible. Not thread-safe:
 * the caller serialises access (shortcut: add a lock if a second thread ever drains). */
typedef struct pg_ring pg_ring;
PG_API pg_ring *pg_ring_create(size_t capacity);
PG_API void pg_ring_destroy(pg_ring *r);
PG_API int32_t pg_ring_push(pg_ring *r, double t, int32_t rssi);
PG_API size_t pg_ring_drain(pg_ring *r, double *t, int32_t *rssi, size_t max);
PG_API uint64_t pg_ring_dropped(const pg_ring *r);

#ifdef __cplusplus
}
#endif
#endif
