// E14: exact minimum DAG size of every 2-input ternary function over a single universal gate,
// by exhaustive canonical enumeration on the GPU.  
//
// Model (identical to synth/exact.py and src/main.rs): primary inputs x, y; gate i (1-based)
// takes operands (a_i, b_i) from the 2+i-1 earlier signals (0 = x, 1 = y, 2+j = gate j+1);
// no free constants; g is applied as out = g[3*u + v] (row-major table, -=0, 0=1, +=2,
// label = sum g[i]*3^i).  A function T^2 -> T is packed as 9 trits x 2 bits = 18 bits.
// Pruning (sound for minimum size): no duplicate signal; every gate but the output is used
// (prune when the unused gates cannot all be consumed by the remaining gates); symmetry
// rule: if gate i+1 does not use gate i then (a_i,b_i) < (a_{i+1},b_{i+1}) lexicographically.
// Host enumerates prefixes of P gates; each GPU thread runs a DFS from one prefix to size S,
// recording atomicMin(minsize[f], i) at every node i whose gates are all used.
//
// Usage: spectrum --enum results/enumerate.csv --out results/gpu_spectrum --smax 9
//                 [--device 0] [--gates 451,8431] [--nosym] [--prefix 5] [--limit N]
// One JSON per gate (atomic tmp+rename); a gate is claimed with mkdir <out>/<gate>.lock so
// several processes (one per GPU) share the queue; skip-if-exists => resumable.
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <chrono>
#include <sys/stat.h>
#include <unistd.h>

#define NF 19683
#define NFP (1<<18)   /* packed 2-bit-per-trit index space; minsize is indexed by packed value */
#define MAXS 12
typedef uint32_t u32; typedef uint64_t u64;

struct Prefix { uint8_t a[MAXS], b[MAXS]; };   // operands of gates 0..P-1

__host__ __device__ inline u32 apply(const uint8_t* g, u32 u, u32 v) {
    u32 o = 0;
    #pragma unroll
    for (int i = 0; i < 9; i++) o |= (u32)g[3 * ((u >> (2 * i)) & 3) + ((v >> (2 * i)) & 3)] << (2 * i);
    return o;
}
__host__ __device__ inline u32 key(int a, int b) { return (u32)a * 32 + b; }


__global__ void dfs_kernel(const uint8_t* __restrict__ gtab, const Prefix* __restrict__ pre, int npre,
                           int P, int S, int nosym, u32 fx, u32 fy, u32* __restrict__ minsize, unsigned long long* __restrict__ nodes)
{
    int t = blockIdx.x * blockDim.x + threadIdx.x;
    __shared__ uint8_t g[9];
    if (threadIdx.x < 9) g[threadIdx.x] = gtab[threadIdx.x];   // ALL threads reach the barrier before any exits
    __syncthreads();
    if (t >= npre) return;
    u32 sig[2 + MAXS]; u32 k[MAXS]; int ua[MAXS], ub[MAXS];
    sig[0] = fx; sig[1] = fy;
    u32 usedmask = 0;
    const Prefix pr = pre[t];
    for (int i = 0; i < P; i++) {
        int a = pr.a[i], b = pr.b[i];
        sig[2 + i] = apply(g, sig[a], sig[b]); k[i] = key(a, b);
        if (a >= 2) usedmask |= 1u << (a - 2);
        if (b >= 2) usedmask |= 1u << (b - 2);
    }
    u64 cnt = 0;
    // record prefix node if complete (all gates < P-1 used)
    {
        u32 need = (P >= 1) ? ((1u << (P - 1)) - 1u) : 0u;
        if ((usedmask & need) == need && P >= 1) atomicMin(&minsize[sig[1 + P]], (u32)P);
    }
    // iterative DFS over gates P..S-1
    int i = P;
    ua[i] = 0; ub[i] = -1;
    u32 savedmask[MAXS + 1]; savedmask[P] = usedmask;
    while (i >= P) {
        int n = 2 + i;                     // number of available signals
        // advance (ua[i], ub[i])
        ub[i]++;
        if (ub[i] >= n) { ub[i] = 0; ua[i]++; }
        if (ua[i] >= n) { i--; continue; }
        int a = ua[i], b = ub[i];
        // symmetry rule w.r.t. previous gate i-1 (signal index 2+i-1)
        if (!nosym && i >= 1) {
            int prev = 2 + i - 1;
            if (a != prev && b != prev && key(a, b) <= k[i - 1]) continue;
        }
        u32 f = apply(g, sig[a], sig[b]);
        // duplicate check
        bool dup = false;
        for (int j = 0; j < n; j++) if (sig[j] == f) { dup = true; break; }
        if (dup) continue;
        cnt++;
        u32 um = savedmask[i];
        if (a >= 2) um |= 1u << (a - 2);
        if (b >= 2) um |= 1u << (b - 2);
        // completeness: all gates 0..i-1 used
        u32 need = (1u << i) - 1u;
        int unused = __popc(need & ~um);
        int size = i + 1;
        if (unused == 0) atomicMin(&minsize[f], (u32)size);
        if (size < S && unused <= S - size) {
            sig[2 + i] = f; k[i] = key(a, b);
            i++; savedmask[i] = um; ua[i] = 0; ub[i] = -1;
        }
    }
    atomicAdd(nodes, (unsigned long long)cnt);
}

static bool file_exists(const std::string& p) { struct stat st; return stat(p.c_str(), &st) == 0; }

int main(int argc, char** argv) {
    std::string enumf = "results/enumerate.csv", out = "results/gpu_spectrum", gates;
    int S = 8, dev = 0, P = 5, nosym = 0; long limit = -1;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--enum") enumf = argv[++i]; else if (a == "--out") out = argv[++i];
        else if (a == "--smax") S = atoi(argv[++i]); else if (a == "--device") dev = atoi(argv[++i]);
        else if (a == "--gates") gates = argv[++i]; else if (a == "--nosym") nosym = 1;
        else if (a == "--prefix") P = atoi(argv[++i]); else if (a == "--limit") limit = atol(argv[++i]);
        else { fprintf(stderr, "unknown arg %s\n", a.c_str()); return 2; }
    }
    if (S > MAXS || P < 1 || P > S) { fprintf(stderr, "bad S/P\n"); return 2; }
    cudaSetDevice(dev);
    cudaSetDeviceFlags(cudaDeviceScheduleBlockingSync);   // host thread sleeps during kernels (no CPU spin); must follow cudaSetDevice
    mkdir(out.c_str(), 0755);
    u32 fx = 0, fy = 0;
    for (int i = 0; i < 9; i++) { fx |= (u32)(i / 3) << (2 * i); fy |= (u32)(i % 3) << (2 * i); }
    // gate list
    std::vector<long> glist;
    if (!gates.empty()) { std::stringstream ss(gates); std::string tok; while (std::getline(ss, tok, ',')) glist.push_back(atol(tok.c_str())); }
    else {
        std::ifstream in(enumf); std::string line; std::getline(in, line);
        std::vector<std::string> hdr; { std::stringstream ss(line); std::string t; while (std::getline(ss, t, ',')) hdr.push_back(t); }
        int ci = -1; for (size_t j = 0; j < hdr.size(); j++) if (hdr[j] == "closure_size") ci = j;
        if (ci < 0) { fprintf(stderr, "no closure_size column\n"); return 2; }
        while (std::getline(in, line)) {
            std::vector<std::string> f; std::stringstream ss(line); std::string t; while (std::getline(ss, t, ',')) f.push_back(t);
            if (f.size() > (size_t)ci && atol(f[ci].c_str()) == NF) glist.push_back(atol(f[0].c_str()));
        }
    }
    fprintf(stderr, "spectrum: %zu gates, S=%d, P=%d, device %d, nosym=%d, out=%s\n", glist.size(), S, P, dev, nosym, out.c_str());
    uint8_t* d_g; u32* d_min; u64* d_nodes; Prefix* d_pre = nullptr; size_t pre_cap = 0;
    cudaMalloc(&d_g, 9); cudaMalloc(&d_min, NFP * sizeof(u32)); cudaMalloc(&d_nodes, sizeof(u64));
    std::vector<u32> h_min(NFP); std::vector<u32> lab(NF);
    for (int L = 0; L < NF; L++) { u32 pk = 0; int v = L; for (int i = 0; i < 9; i++) { pk |= (u32)(v % 3) << (2 * i); v /= 3; } lab[L] = pk; }
    long done = 0;
    for (long gl : glist) {
        if (limit >= 0 && done >= limit) break;
        std::string jf = out + "/" + std::to_string(gl) + (nosym ? ".nosym" : "") + ".json";
        if (file_exists(jf)) continue;
        std::string lock = out + "/" + std::to_string(gl) + ".lock";
        if (mkdir(lock.c_str(), 0755) != 0) continue;      // claimed by another process
        auto t0 = std::chrono::steady_clock::now();
        uint8_t g[9]; long v = gl; for (int i = 0; i < 9; i++) { g[i] = v % 3; v /= 3; }
        // host prefix enumeration (same pruning rules), depth P
        std::fill(h_min.begin(), h_min.end(), 255u); h_min[fx] = 0; h_min[fy] = 0;
        std::vector<Prefix> pre; Prefix cur; std::vector<u32> sig(2 + MAXS); sig[0] = fx; sig[1] = fy;
        std::vector<u32> kk(MAXS); std::vector<u32> um(MAXS + 1, 0);
        // recursive lambda via explicit stack
        std::vector<int> A(MAXS), B(MAXS); int i = 0; A[0] = 0; B[0] = -1; um[0] = 0;
        while (i >= 0) {
            int n = 2 + i; B[i]++; if (B[i] >= n) { B[i] = 0; A[i]++; } if (A[i] >= n) { i--; continue; }
            int a = A[i], b = B[i];
            if (!nosym && i >= 1) { int prev = 2 + i - 1; if (a != prev && b != prev && key(a, b) <= kk[i - 1]) continue; }
            u32 f = apply(g, sig[a], sig[b]); bool dup = false; for (int j = 0; j < n; j++) if (sig[j] == f) { dup = true; break; }
            if (dup) continue;
            u32 m = um[i]; if (a >= 2) m |= 1u << (a - 2); if (b >= 2) m |= 1u << (b - 2);
            int size = i + 1; u32 need = (1u << i) - 1u; int unused = __builtin_popcount(need & ~m);
            if (unused > S - size) continue;
            if (unused == 0 && size < P && (u32)size < h_min[f]) h_min[f] = size;
            cur.a[i] = a; cur.b[i] = b; sig[2 + i] = f; kk[i] = key(a, b);
            if (size == P) { pre.push_back(cur); continue; }
            i++; um[i] = m; A[i] = 0; B[i] = -1;
        }
        if (pre.size() > pre_cap) { if (d_pre) cudaFree(d_pre); pre_cap = pre.size(); cudaMalloc(&d_pre, pre_cap * sizeof(Prefix)); }
        cudaMemcpy(d_pre, pre.data(), pre.size() * sizeof(Prefix), cudaMemcpyHostToDevice);
        cudaMemcpy(d_g, g, 9, cudaMemcpyHostToDevice);
        cudaMemcpy(d_min, h_min.data(), NFP * sizeof(u32), cudaMemcpyHostToDevice);
        cudaMemset(d_nodes, 0, sizeof(u64));
        int bs = 128; int nb = (int)((pre.size() + bs - 1) / bs);
        if (nb > 0) dfs_kernel<<<nb, bs>>>(d_g, d_pre, (int)pre.size(), P, S, nosym, fx, fy, d_min, (unsigned long long*)d_nodes);
        cudaError_t e = cudaDeviceSynchronize();
        if (e != cudaSuccess) { fprintf(stderr, "CUDA error on gate %ld: %s\n", gl, cudaGetErrorString(e)); rmdir(lock.c_str()); return 1; }
        u64 nodes = 0; cudaMemcpy(&nodes, d_nodes, sizeof(u64), cudaMemcpyDeviceToHost);
        cudaMemcpy(h_min.data(), d_min, NFP * sizeof(u32), cudaMemcpyDeviceToHost);
        double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        std::vector<long> hist(S + 1, 0); long reached = 0;
        for (int L = 0; L < NF; L++) { u32 m = h_min[lab[L]]; if (m <= (u32)S) { hist[m]++; reached++; } }
        // targets: h_sum = (x+y) mod-balanced sum, h_carry, mul (balanced: -=−1, 0=0, +=+1)
        u32 hs = 0, hc = 0, mu = 0;
        for (int i = 0; i < 9; i++) { int x = i / 3 - 1, y = i % 3 - 1; int s = x + y; int c = (s > 1) ? 1 : (s < -1 ? -1 : 0); int sb = s - 3 * c;
            hs |= (u32)(sb + 1) << (2 * i); hc |= (u32)(c + 1) << (2 * i); mu |= (u32)(x * y + 1) << (2 * i); }
        std::string tmp = jf + ".tmp"; FILE* fo = fopen(tmp.c_str(), "w");
        fprintf(fo, "{\"gate\":%ld,\"S\":%d,\"P\":%d,\"nosym\":%d,\"device\":%d,\"prefixes\":%zu,\"nodes\":%llu,\"seconds\":%.3f,\"reached\":%ld,\"hist\":[", gl, S, P, nosym, dev, pre.size(), (unsigned long long)nodes, secs, reached);
        for (int s = 0; s <= S; s++) fprintf(fo, "%s%ld", s ? "," : "", hist[s]);
        fprintf(fo, "],\"h_sum\":%d,\"h_carry\":%d,\"mul\":%d,\"minsize\":\"", h_min[hs] <= (u32)S ? (int)h_min[hs] : -1, h_min[hc] <= (u32)S ? (int)h_min[hc] : -1, h_min[mu] <= (u32)S ? (int)h_min[mu] : -1);
        for (int L = 0; L < NF; L++) { u32 m = h_min[lab[L]]; fputc(m <= (u32)S ? ('0' + m) : '.', fo); }   // one char per function, position = label
        fprintf(fo, "\"}\n"); fclose(fo); rename(tmp.c_str(), jf.c_str()); rmdir(lock.c_str());
        done++;
        fprintf(stderr, "g%ld S=%d reached %ld/%d nodes %llu in %.1fs (h_sum %d h_carry %d mul %d)\n", gl, S, reached, NF, (unsigned long long)nodes, secs,
                h_min[hs] <= (u32)S ? (int)h_min[hs] : -1, h_min[hc] <= (u32)S ? (int)h_min[hc] : -1, h_min[mu] <= (u32)S ? (int)h_min[mu] : -1);
    }
    fprintf(stderr, "spectrum: done %ld gates\n", done);
    return 0;
}
