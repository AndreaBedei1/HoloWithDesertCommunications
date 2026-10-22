# Native water/air attenuation and antenna gain; SF7 CR4/5 empirical PER table.
set channel [new Module/UW/ElectroMagnetic/Channel]
set em_per_lut /home/DESERT_Underwater/DESERT_Framework/DESERT/samples/desert_samples/dbs/em_attenuation/CR_4-5/SF_7.csv
if {![file readable $em_per_lut] || [file size $em_per_lut] == 0} { error "Missing pinned EM PER LUT" }
proc configure_medium_phy {i} {
    global phy propagation antenna mask medium_parameters em_per_lut
    set p $medium_parameters
    set propagation($i) [new Module/UW/ElectroMagnetic/Propagation]
    $propagation($i) set T_ [dict get $p temperature_c]
    $propagation($i) set S_ [dict get $p salinity_ppt]
    $phy($i) set TxPower_ [dict get $p tx_power_dbm]
    $phy($i) set BitRate_ [dict get $p bitrate_bps]
    set antenna($i) [new Module/UW/ElectroMagnetic/Antenna]
    $antenna($i) setGain [dict get $p antenna_gain_db]
    $phy($i) setAntenna $antenna($i)
    $phy($i) setLUTFileName $em_per_lut
    $phy($i) setLUTSeparator ,
    $phy($i) useLUT
    $mask($i) setFreq [dict get $p frequency_hz]
    $mask($i) setBandwidth [dict get $p bandwidth_hz]
}
