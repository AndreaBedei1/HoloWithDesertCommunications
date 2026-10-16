#!/usr/bin/env bash
set -euo pipefail
root=/home/DESERT_Underwater
build="$root/DESERT_buildCopy_LOCAL"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source "$build/environment"
git -C "$root" rev-parse HEAD > /opt/holo/desert-source-commit
unpacked="$root/DESERT_Framework/.unpacked_folder"
mapfile -t dirs < <(find "$root/DESERT_Framework/DESERT" "$unpacked/ns-2.34" "$unpacked/nsmiracle-2.0.0" \
  -type f -name '*.h' ! -path '*/compat/*' ! -path '*/tcp/linux/*' -printf '%h\n' | sort -u)
flags=("-I/opt/holo/desert/extensions" "-I$unpacked/ns-2.34" "-I$unpacked/tcl-8.5.19/generic" \
  "-I$unpacked/tcl-8.5.19/unix" "-I$unpacked/tclcl-1.20" "-I$unpacked/otcl-1.14")
for dir in "${dirs[@]}"; do flags+=("-I$dir"); done
g++ -std=c++11 -shared -fPIC -O2 -Wno-write-strings "${flags[@]}" /opt/holo/desert/extensions/bridge.cc \
  -L"$build/lib" -Wl,-rpath,"$build/lib" -luwapplication -lUwmStd -lmphy -lMiracle -luwip -luwudp \
  -o /opt/holo/libholobridge.so
