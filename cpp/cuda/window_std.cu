// Optional CUDA kernel: population standard deviation of many fixed-length windows at once.
// WRITTEN, not run: the build laptop has no NVIDIA GPU. Enable with -DPGUARD_CUDA=ON on a
// machine with the CUDA toolkit; the CPU path in src/signal.cpp stays the reference.
#include <cuda_runtime.h>

#include <cmath>
#include <cstdint>

extern "C" {

__global__ void pg_window_std_kernel(const float *x, int win, int nwin, float *out) {
  const int w = blockIdx.x * blockDim.x + threadIdx.x;
  if (w >= nwin) return;
  const float *p = x + static_cast<int64_t>(w) * win;
  float mean = 0.f;
  for (int i = 0; i < win; ++i) mean += p[i];
  mean /= static_cast<float>(win);
  float ss = 0.f;
  for (int i = 0; i < win; ++i) ss += (p[i] - mean) * (p[i] - mean);
  out[w] = sqrtf(ss / static_cast<float>(win));
}

// Returns 0 on success, otherwise a cudaError_t value.
int pg_cuda_window_std(const float *host_x, int win, int nwin, float *host_out) {
  if (!host_x || !host_out || win < 2 || nwin < 1) return -1;
  float *dx = nullptr, *dout = nullptr;
  const size_t in_bytes = static_cast<size_t>(win) * nwin * sizeof(float);
  const size_t out_bytes = static_cast<size_t>(nwin) * sizeof(float);
  cudaError_t e = cudaMalloc(&dx, in_bytes);
  if (e == cudaSuccess) e = cudaMalloc(&dout, out_bytes);
  if (e == cudaSuccess) e = cudaMemcpy(dx, host_x, in_bytes, cudaMemcpyHostToDevice);
  if (e == cudaSuccess) {
    const int threads = 128, blocks = (nwin + threads - 1) / threads;
    pg_window_std_kernel<<<blocks, threads>>>(dx, win, nwin, dout);
    e = cudaGetLastError();
  }
  if (e == cudaSuccess) e = cudaMemcpy(host_out, dout, out_bytes, cudaMemcpyDeviceToHost);
  cudaFree(dx);
  cudaFree(dout);
  return static_cast<int>(e);
}

}  // extern "C"
