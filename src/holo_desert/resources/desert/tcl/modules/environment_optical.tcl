# Native omnidirectional optical propagation with fixed water attenuation.
# Directional adapter supplies body/mount orientation to native Lambert-Beer gain; receiver optics are omnidirectional.
set channel [new Module/UW/Optical/Channel]
set optical_noise_lut /home/DESERT_Underwater/DESERT_Framework/DESERT/samples/desert_samples/dbs/optical_noise/LUT.txt
if {![file readable $optical_noise_lut] || [file size $optical_noise_lut] == 0} { error "Missing pinned optical noise LUT" }
proc configure_medium_phy {i} {
    global phy propagation mask medium_parameters optical_noise_lut
    set p $medium_parameters
    set propagation($i) [new Module/UW/OPTICAL/Propagation/HOLO]
    foreach {key binding} {receiver_area_m2 Ar_ transmitter_area_m2 At_ attenuation_per_m c_ beam_angle_rad theta_} {
        $propagation($i) set $binding [dict get $p $key]
    }
    $propagation($i) setOmnidirectional
    if {[dict get $p directional]} { $propagation($i) setDirectional }
    foreach {key binding} {mount_yaw_deg mount_yaw_ mount_pitch_deg mount_pitch_ mount_roll_deg mount_roll_} {
        $propagation($i) set $binding [expr {[dict get $p $key]*acos(-1)/180}]
    }
    foreach {key binding} {offset_x_m offset_x_ offset_y_m offset_y_ offset_z_m offset_z_} {
        $propagation($i) set $binding [dict get $p $key]
    }
    $propagation($i) setFixedC
    foreach {key binding} {tx_power_w TxPower_ bitrate_bps BitRate_ temperature_k T_ receiver_area_m2 Ar_ dark_current_a Id_ shunt_resistance_ohm R_ responsivity_a_w S_ acquisition_threshold_db AcquisitionThreshold_dB_} {
        $phy($i) set $binding [dict get $p $key]
    }
    $phy($i) setLUTFileName $optical_noise_lut
    $phy($i) setLUTSeparator " "
    $phy($i) useLUT
    $mask($i) setFreq [dict get $p frequency_hz]
    $mask($i) setBandwidth [dict get $p bandwidth_hz]
}
