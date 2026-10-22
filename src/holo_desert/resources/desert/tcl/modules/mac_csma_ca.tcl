# SPDX-License-Identifier: MIT
load libuwcsmaca.so

proc prepare_mac {} {
    global mac_parameters bitrate buffer_packets
    global mac_stat_commands mac_bindings
    set mac_bindings {queue_size_ bitrate_ backoff_delta_ backoff_max cts_wait_val_ data_wait_val_ ack_wait_val_}
    set mac_stat_commands {rts_rx getRTSRx cts_rx getCTSRx rts_dropped getRTSDropped cts_dropped getCTSDropped data_dropped getDataDropped upper_data_rx getUpDataRx}
    Module/UW/CSMA_CA set debug_ 0
    Module/UW/CSMA_CA set queue_size_ $buffer_packets
    Module/UW/CSMA_CA set bitrate_ $bitrate
    foreach {parameter binding value} {queue_size queue_size_ 10 backoff_delta_s backoff_delta_ 1 backoff_max backoff_max 20 cts_wait_s cts_wait_val_ 10 data_wait_s data_wait_val_ 10 ack_wait_s ack_wait_val_ 10} {
        if {$parameter eq "queue_size"} { set value $buffer_packets }
        if {[dict exists $mac_parameters $parameter]} { set value [dict get $mac_parameters $parameter] }
        Module/UW/CSMA_CA set $binding $value
    }
}

proc create_mac {i} {
    global ack acoustic
    set module [new Module/UW/CSMA_CA]
    $module set bitrate_ [dict get $acoustic($i) bitrate_bps]
    $module setMacAddr $i
    if {$ack} { $module setAckMode } else { $module setNoAckMode }
    $module initialize
    return $module
}

proc start_macs {} {}
