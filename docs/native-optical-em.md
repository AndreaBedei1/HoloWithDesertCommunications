# Native optical and electromagnetic interfaces

`network.medium` selects `acoustic` (the historical default), `optical`, or `em`.
The two new single interfaces currently require CSMA-ALOHA and StaticRouting.
Acoustic per-node overrides are rejected for a nonacoustic interface. A flow
inherits its network medium; it cannot select a different single interface.

## Optical: experimental native interface

The chain uses DESERT `Module/UW/Optical/Channel`, `UwOpticalMPropagation`,
`UwOpticalPhy`, the native interference model, and the installed optical
ambient-noise LUT. All acquisition, noise, interference and packet reception
decisions execute in DESERT. Attenuation is a configurable constant `c` in m⁻¹;
this interface does not silently select an oceanographic attenuation profile.
Temperature is kelvin; optical transmitter power is watts, not acoustic SPL.
Receiver/transmitter areas are m², responsivity A/W and dark current amperes.

`directional=false` preserves omnidirectional native gain. The optional
`native-optical-lambert-beer-body-frame-v1` C++ geometry adapter supplies the
transmitter angle to the unchanged native `getLambertBeerGain(distance,beta)`.
It transforms the transducer forward axis by mount then measured body rotation,
using right-handed `Rz(yaw) Ry(pitch) Rx(roll)`. Backward-facing transmitters
have zero gain. Mount angles are degrees and offsets metres in vehicle body
coordinates. HoloOcean DynamicsSensor roll, pitch and yaw are transported at
each synchronized position update; Python makes no link decision.

Limits: receiver optics remain omnidirectional; no receiver FOV or occlusion
model is claimed. Offsets affect native gain distance/angle; propagation delay
and ambient-noise depth use the vehicle COM. This is an experimental gain
adapter, not a calibrated complete commercial optical modem. The pinned noise
LUT covers 0–20 m, so initial positions, desired waypoints and measured updates
outside `-20 <= z < 0` are rejected. No zero ambient-noise extrapolation is used.
The native optical model makes an acquisition decision from squared
photodetector-current SNR and rejects receptions with positive interference;
it does not implement an additional Python BER curve.

## Electromagnetic: experimental native interface

The complete native chain includes `Module/UW/ElectroMagnetic/Channel`,
`Propagation`, `PHY` and `Antenna`. Temperature is Celsius, salinity ppt,
transmitter power dBm, antenna gain dB, frequency/bandwidth Hz, bitrate bit/s.
The surface stays at local `z=0`; underwater coordinates are negative.
The native antenna has constant gain and does not respond to vehicle pointing.

The fixed trusted resource is DESERT's `em_attenuation/CR_4-5/SF_7.csv`.
It is an empirical SF7 CR4/5 RSSI/PER table, not calibration for every bitrate,
frequency or hardware device. The complete effective configuration records
all parameters; arbitrary user paths or Tcl are never accepted.

`em-power-lut-v1` builds a separately named copy of the pinned native
EM PHY. It fixes the original end-iterator dereference above maximum RSSI and
normalizes exact table hits from percent to probability, matching upstream's
interpolated branch. The supplied values are 6.5 and 2.5 percent; the original
exact-match branch incorrectly returned these directly as probabilities.
It also stores positive linear mW in the MPhy packet header and uses the actual
source packet power in the received-power equation. Upstream stores dBm in a
header asserted positive and reads the receiver's own transmitter power:
negative source powers crash and heterogeneous transmitter settings are ignored.
The patched native path handles both correctly, retaining dBm at the user API.
Source-pattern assertions reject a different upstream implementation at build
time. The installed source, library and original Tcl class remain untouched.

## Evidence and remaining validation

The isolated native bridge tests use port 5559 and disposable sessions:

```
$env:DESERT_PORT='5559'
.venv/Scripts/python.exe -m pytest tests/integration/test_native_media.py -m desert -q
```

They exercise real optical delivery, low-power and high-attenuation failures,
freshwater EM delivery, seawater attenuation failure, body yaw/pitch,
transducer mounting, position movement, rotated body offsets, and STOP/restart.
Unit tests cover typed/socket validation, power-unit separation, preservation
of measured RPY, and the isolated native source patch. A full HoloOcean
orientation calibration and physical-device validation remain separate work.

Telemetry distinguishes optical TX/RX W and noise A² from EM TX dBm/RX mW.
PHY receive lifecycle events are observations before the native receive
decision; application `rx` events establish delivery. No per-packet error
cause is invented when the native model does not expose it.
