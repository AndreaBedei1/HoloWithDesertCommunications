"""Compile the same probability helper used by the native PHY, without NS mocks."""
from pathlib import Path

import pytest

from holo_desert.desert_adapter.backend import docker_command


pytestmark = pytest.mark.desert


def test_conditional_bpsk_probability_native(tmp_path):
    root = Path(__file__).resolve().parents[2]
    header = root / "src/holo_desert/resources/desert/extensions/corrected-bpsk.h"
    assert header.is_file(), "corrected PHY probability implementation is missing"
    source = tmp_path / "check.cc"
    source.write_text(r'''
#include "corrected-bpsk.h"
#include <cassert>
#include <cmath>
int main() {
    const double bn = .000443618, bi = .002, bits = 1600;
    assert(holo_bpsk::conditional_error(0) == 0);
    const double whole = holo_bpsk::log_success_ratio(bn, bi, bits);
    const double split = holo_bpsk::log_success_ratio(bn, bi, 600.25)
                       + holo_bpsk::log_success_ratio(bn, bi, 999.75);
    assert(std::abs(whole - split) < 1e-12);
    assert(holo_bpsk::log_success_ratio(bn, bn, bits) == 0);
    const double pn = 1 - std::pow(1-bn, bits);
    const double pt = 1 - std::pow(1-bi, bits);
    const double q = holo_bpsk::conditional_error(whole);
    assert(std::abs(pn + (1-pn)*q - pt) < 1e-13);
    assert(std::abs(q - (pt-pn)/(1-pn)) < 1e-13);
    assert(holo_bpsk::conditional_error(-1e-20) > 0);
    assert(holo_bpsk::conditional_error(-10000) == 1);
}
''', encoding="utf-8")
    result = docker_command(
        "run", "--rm", "--entrypoint", "bash",
        "-v", f"{header.parent}:/include:ro", "-v", f"{tmp_path}:/check:ro",
        "holo-desert-engine:4.0.0-v2", "-lc",
        "g++ -std=c++11 -I/include /check/check.cc -o /tmp/check && /tmp/check",
    )
    assert result.returncode == 0
