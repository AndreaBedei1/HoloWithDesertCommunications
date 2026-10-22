# Native omnidirectional optical propagation with fixed water attenuation.
# Directional adapter supplies body/mount orientation to native Lambert-Beer gain; receiver optics are omnidirectional.
set channel [new Module/UW/Optical/Channel]
source /opt/holo/desert/tcl/modules/optical_phy.tcl
proc configure_medium_phy {i} {
    global phy propagation mask medium_parameters
    set propagation($i) [new Module/UW/OPTICAL/Propagation/HOLO]
    configure_optical_phy $phy($i) $propagation($i) $mask($i) $medium_parameters
}
