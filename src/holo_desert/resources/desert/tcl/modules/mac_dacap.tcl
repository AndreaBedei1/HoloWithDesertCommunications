# SPDX-License-Identifier: MIT
load libuwdacap.so

proc prepare_mac {} {
    global mac_parameters max_tries buffer_packets
    global mac_stat_commands
    set mac_stat_commands {mean_defer_time_s getMeanDeferTime defer_count getTotalDeferTimes warning_tx getWrnPktsTx warning_rx getWrnPktsRx rts_tx getRtsPktsTx rts_rx getRtsPktsRx cts_tx getCtsPktsTx cts_rx getCtsPktsRx upper_data_rx getUpLayersDataRx}
    Module/UW/DACAP set debug_ 0
    Module/UW/DACAP set max_tx_tries $max_tries
    Module/UW/DACAP set buffer_pkts $buffer_packets
    Module/UW/DACAP set max_payload 4096
    foreach {parameter binding value} {wait_costant_s wait_costant 0.2 delta_d delta_D 1500 t_min t_min 2 tw_min T_W_min 0 max_prop_delay_s max_prop_delay 2} {
        if {[dict exists $mac_parameters $parameter]} { set value [dict get $mac_parameters $parameter] }
        Module/UW/DACAP set $binding $value
    }
}

proc create_mac {i} {
    global ack
    set module [new Module/UW/DACAP]
    $module setMacAddr $i
    if {$ack} { $module setAckMode } else { $module setNoAckMode }
    return $module
}

proc start_macs {} {}
