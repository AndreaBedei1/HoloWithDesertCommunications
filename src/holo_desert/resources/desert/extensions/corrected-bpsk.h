// SPDX-License-Identifier: MIT
#ifndef HOLO_CORRECTED_BPSK_H
#define HOLO_CORRECTED_BPSK_H
#include <algorithm>
#include <cmath>

namespace holo_bpsk {
// S(total)/S(noise), accumulated in log space over fractional chunk bits.
inline double log_success_ratio(double noise_ber, double total_ber, double bits) {
    return bits * std::min(0.0, std::log1p(-total_ber) - std::log1p(-noise_ber));
}
// Equivalent to (PERtotal-PERnoise)/(1-PERnoise), including near-zero PERs.
inline double conditional_error(double log_ratio) {
    return -std::expm1(std::min(0.0, log_ratio));
}
}
#endif
