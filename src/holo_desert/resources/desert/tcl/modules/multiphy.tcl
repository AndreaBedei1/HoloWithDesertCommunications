# One MAC and native master/slave PHY controller per node, sharing one scheduler.
# Each interface is built for its medium: acoustic interfaces share the bridge's
# acoustic channel, optical interfaces share one native optical channel.
if {$multi_optical} {
    source /opt/holo/desert/tcl/modules/optical_phy.tcl
    set optical_channel [new Module/UW/Optical/Channel]
}
proc prepare_multi_phy {i} {
    global multi_policy multi_master multi_alpha multi_controller multi_indices multi_medium optical_interfaces
    global multi_phy_class multi_settings interface_phy interface_mask interface_prop interface_interf phy
    set class Module/UW/MULTI_STACK_CONTROLLER_PHY
    if {$multi_policy eq "received_power"} {
        set class [expr {$i == $multi_master ? "Module/UW/MULTI_STACK_CONTROLLER_PHY_MASTER" : "Module/UW/MULTI_STACK_CONTROLLER_PHY_SLAVE"}]
    }
    set multi_controller($i) [new $class]
    if {$multi_policy eq "received_power" && $i == $multi_master} { $multi_controller($i) setAlpha $multi_alpha }
    set optical_interfaces($i) {}
    set first 1
    foreach index $multi_indices($i) {
        if {$first} { set interface_phy($i,$index) $phy($i); set first 0 } else { set interface_phy($i,$index) [new $multi_phy_class($i,$index)] }
        set p $interface_phy($i,$index)
        $p set node_id_ $i
        $p set interface_index_ $index
        set settings $multi_settings($i,$index)
        set interface_mask($i,$index) [new MSpectralMask/Rect]
        set interface_interf($i,$index) [new MInterference/MIV]
        $interface_interf($i,$index) set maxinterval_ 1000
        if {$multi_medium($i,$index) eq "optical"} {
            set interface_prop($i,$index) [new Module/UW/OPTICAL/Propagation/HOLO]
            configure_optical_phy $p $interface_prop($i,$index) $interface_mask($i,$index) $settings
            lappend optical_interfaces($i) $index
        } else {
            foreach binding {SPLOptimization_ CentralFreqOptimization_ BandwidthOptimization_} { $p set $binding 0 }
            foreach {key binding} {tx_power_db MaxTxSPL_dB_ tx_power_db MinTxSPL_dB_ bitrate_bps BitRate_ rx_snr_penalty_db RxSnrPenalty_dB_ acquisition_threshold_db AcquisitionThreshold_dB_} { $p set $binding [dict get $settings $key] }
            set interface_prop($i,$index) [new MPropagation/Underwater]
            foreach {key binding} {spreading practicalSpreading_ shipping shipping_ wind_speed_mps windspeed_} { $interface_prop($i,$index) set $binding [dict get $settings $key] }
            $interface_mask($i,$index) setFreq [dict get $settings frequency_hz]
            $interface_mask($i,$index) setBandwidth [dict get $settings bandwidth_hz]
        }
        $p setPropagation $interface_prop($i,$index)
        $p setSpectralMask $interface_mask($i,$index)
        $p setInterference $interface_interf($i,$index)
    }
}

proc connect_multi_phy {i} {
    global multi_indices multi_controller multi_initial multi_policy multi_master multi_thresholds multi_medium interface_phy node channel optical_channel
    set layer [llength $multi_indices($i)]
    foreach index $multi_indices($i) {
        set p $interface_phy($i,$index)
        $node($i) addModule $layer $p 0
        incr layer -1
        $node($i) setConnection $multi_controller($i) $p 0
        if {$multi_medium($i,$index) eq "optical"} { $node($i) addToChannel $optical_channel $p 0 } else { $node($i) addToChannel $channel $p 0 }
        if {$multi_policy eq "received_power" && $i == $multi_master} { $multi_controller($i) addLayer [$p Id_] $index }
    }
    $multi_controller($i) setManualLowerlId [$interface_phy($i,$multi_initial) Id_]
    if {$multi_policy eq "received_power"} {
        if {$i == $multi_master} {
            foreach threshold $multi_thresholds {
                lassign $threshold from to power
                $multi_controller($i) addThreshold [$interface_phy($i,$from) Id_] [$interface_phy($i,$to) Id_] $power
            }
        }
        $multi_controller($i) setAutomaticSwitch
    } else { $multi_controller($i) setManualSwitch }
}

proc select_multi_interface {id index} {
    global multi_policy multi_controller multi_indices interface_phy mac ns
    if {$multi_policy ne "manual" || ![string is integer -strict $index] || $index ni $multi_indices($id)} { error "Unsupported interface selection" }
    if {[$multi_controller($id) getStatus] != 1 || [$mac($id) getQueueSize] > 0} { error "Interface selection requires an idle controller and empty MAC queue" }
    $multi_controller($id) setManualLowerlId [$interface_phy($id,$index) Id_]
    puts "{\"event\":\"interface_selected\",\"time\":[$ns now],\"node\":$id,\"interface_index\":$index,\"policy\":\"manual\"}"
}

proc observe_multi_phy {} {
    global multi_controller multi_indices interface_phy count ns multi_policy
    for {set i 1} {$i <= $count} {incr i} {
        set active [$multi_controller($i) set set_lower_id_active_]
        foreach index $multi_indices($i) {
            if {[$interface_phy($i,$index) Id_] == $active} {
                puts "{\"event\":\"interface_state\",\"time\":[$ns now],\"node\":$i,\"interface_index\":$index,\"controller_state\":[$multi_controller($i) getStatus],\"policy\":\"$multi_policy\"}"
            }
        }
    }
}
