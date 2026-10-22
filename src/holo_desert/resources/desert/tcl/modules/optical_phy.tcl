# Native optical PHY and propagation from validated optical settings, shared by
# the single-medium optical stack and optical multi-PHY interfaces.
set optical_noise_lut /home/DESERT_Underwater/DESERT_Framework/DESERT/samples/desert_samples/dbs/optical_noise/LUT.txt
if {![file readable $optical_noise_lut] || [file size $optical_noise_lut] == 0} { error "Missing pinned optical noise LUT" }
proc configure_optical_phy {phy propagation mask settings} {
    global optical_noise_lut
    foreach {key binding} {receiver_area_m2 Ar_ transmitter_area_m2 At_ attenuation_per_m c_ beam_angle_rad theta_} {
        $propagation set $binding [dict get $settings $key]
    }
    $propagation setOmnidirectional
    if {[dict get $settings directional]} { $propagation setDirectional }
    foreach {key binding} {mount_yaw_deg mount_yaw_ mount_pitch_deg mount_pitch_ mount_roll_deg mount_roll_} {
        $propagation set $binding [expr {[dict get $settings $key]*acos(-1)/180}]
    }
    foreach {key binding} {offset_x_m offset_x_ offset_y_m offset_y_ offset_z_m offset_z_} {
        $propagation set $binding [dict get $settings $key]
    }
    $propagation setFixedC
    foreach {key binding} {tx_power_w TxPower_ bitrate_bps BitRate_ temperature_k T_ receiver_area_m2 Ar_ dark_current_a Id_ shunt_resistance_ohm R_ responsivity_a_w S_ acquisition_threshold_db AcquisitionThreshold_dB_} {
        $phy set $binding [dict get $settings $key]
    }
    $phy setLUTFileName $optical_noise_lut
    $phy setLUTSeparator " "
    $phy useLUT
    $mask setFreq [dict get $settings frequency_hz]
    $mask setBandwidth [dict get $settings bandwidth_hz]
}
