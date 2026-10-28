/* C driver shim: ring buffer between a capture driver and the signal core. */
#include <stdlib.h>

#include "pguard_signal.h"

struct pg_ring {
  double *t;
  int32_t *rssi;
  size_t capacity, head, count;
  uint64_t dropped;
};

pg_ring *pg_ring_create(size_t capacity) {
  if (capacity == 0) return NULL;
  pg_ring *r = calloc(1, sizeof *r);
  if (!r) return NULL;
  r->t = malloc(capacity * sizeof *r->t);
  r->rssi = malloc(capacity * sizeof *r->rssi);
  if (!r->t || !r->rssi) {
    free(r->t);
    free(r->rssi);
    free(r);
    return NULL;
  }
  r->capacity = capacity;
  return r;
}

void pg_ring_destroy(pg_ring *r) {
  if (!r) return;
  free(r->t);
  free(r->rssi);
  free(r);
}

int32_t pg_ring_push(pg_ring *r, double t, int32_t rssi) {
  if (!r) return PG_ERR_NULL;
  int32_t dropped = 0;
  if (r->count == r->capacity) {
    r->head = (r->head + 1) % r->capacity;
    r->count--;
    r->dropped++;
    dropped = 1;
  }
  const size_t tail = (r->head + r->count) % r->capacity;
  r->t[tail] = t;
  r->rssi[tail] = rssi;
  r->count++;
  return dropped;
}

size_t pg_ring_drain(pg_ring *r, double *t, int32_t *rssi, size_t max) {
  if (!r || !t || !rssi) return 0;
  size_t n = 0;
  while (r->count > 0 && n < max) {
    t[n] = r->t[r->head];
    rssi[n] = r->rssi[r->head];
    r->head = (r->head + 1) % r->capacity;
    r->count--;
    n++;
  }
  return n;
}

uint64_t pg_ring_dropped(const pg_ring *r) { return r ? r->dropped : 0; }
