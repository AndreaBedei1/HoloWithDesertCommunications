# Native WOSS/Bellhop

Select `network.acoustic.propagation: woss` and the original BPSK variant. The bridge uses `WOSS/Module/Channel`, `WOSS/MPropagation` and a transparent observer subclass of `WOSS/Module/MPhy/BPSK`. Transmission, received power, propagation delay, interference and reception decisions remain in DESERT/WOSS. The corrected analytic BPSK variant is rejected with WOSS.

`network.woss` defines an explicitly synthetic environment: a flat sea surface, a flat seabed, one sediment and a depth-dependent sound speed profile. It does not import the Unreal seabed or geographic databases. SSP samples must increase from depth zero to `water_depth_m`; depth is positive downwards and speed is in m/s. Sediment inputs are speed in m/s, density in g/cm³ and attenuation in dB/wavelength. The remaining native shear-wave speed, shear attenuation and layer depth retain the pinned no-database sample values 200 m/s, 0.8 dB/wavelength and 1 m.

The geographic origin is latitude/longitude in degrees. `x_bearing_deg` is the clockwise bearing of HoloOcean's positive X axis from geographic north. Positive Y points left: with X bearing 90° (east), positive Y points north. Native WOSS geodesic utilities convert the local horizontal vector; local Z remains altitude relative to sea surface zero. WOSS Earth-centred XYZ must never receive the local HoloOcean coordinates.

The supported local frame extends 100 km from the origin. Nodes require more than 0.1 m clearance from the surface and seabed because the pinned Bellhop receiver samples span ±0.1 m. All node pairs require at least 1 m horizontal separation. In the pinned native implementation a vertically aligned link aborts in `bellhop-woss.cpp:946`, so configuration and runtime guards reject it before propagation. These are explicit model constraints, not artificial link losses.

Every synchronized position command updates native latitude, longitude and altitude before the next scheduler step. Position acknowledgements include both local coordinates and applied geographic coordinates. Exact native space sampling is fixed at zero in the manager, estimator and results database. Each session owns its SSP, Bellhop work directory and results database in a new temporary directory. Stop closes native database connections and deletes the manager; restart never reuses another environment's results. The environment is stationary in time; vehicle movement changes native geometry. Vehicle attitude does not steer this omnidirectional acoustic model.

Analytic spreading and constant propagation speed do not control WOSS: Bellhop uses the configured SSP and environment. Acoustic source level remains dB re µPa at 1 m; frequency/bandwidth are Hz and bitrate is bit/s. The bridge reports native received power, noise, interference and arrival times. It does not expose an invented multipath summary.

## Demonstration and verification

The moving example is `src/holo_desert/resources/demos/e08_woss/scenario.yaml`. Import that YAML through the scenario editor or pass its path to the CLI. It requires HoloOcean; the standalone fixture deliberately does not fabricate its trajectories. It is separate from the six historical examples.

`tests/unit/test_environment.py` covers typed and raw configuration validation, SSP coverage, geometry, class selection and historical defaults. `tests/integration/test_environment_stack.py` runs real bridge packets: delivery, bearing/left-axis conversion, depth/distance movement, changed native power/delay, nonuniform SSP sensitivity, restart and invalid runtime geometry recovery.

An isolated `holo-environment-qa` container on port 5557 was used; the existing user service on 5555 was untouched. A disposable executable wrapper counted four actual Bellhop invocations for the two integration tests and delegated each to the unchanged native executable. The official pinned no-database sample was also verified independently (17 native transmissions, 5 receptions). Neither sample success nor the bridge tests alone establish a HoloOcean calibration or field validation.
