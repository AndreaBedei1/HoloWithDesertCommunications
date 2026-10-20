# SPDX-License-Identifier: MIT
load libuwmmac_clmsgs.so
load libuwphy_clmsgs.so
load libuwtdma.so

proc prepare_tdma_class {class} {
    global mac_parameters count buffer_packets
    global mac_queue_command mac_stat_commands
    set mac_queue_command get_buffer_size
    set mac_stat_commands {upper_data_rx get_upper_data_pkts_rx sent_packets get_sent_pkts received_packets get_recv_pkts}
    foreach {key value} {debug_ 0 HDR_size_ 0 wait_constant_ 0.1 MAC_addr_ 0 sea_trial_ 0 fair_mode 1 drop_old_ 0 checkPriority_ 0 mac2phy_delay_ 1e-9} {
        $class set $key $value
    }
    $class set queue_size_ $buffer_packets
    $class set tot_slots $count
    foreach {parameter binding value} {frame_duration_s frame_duration 3 guard_time_s guard_time 0.1 max_packets_per_slot max_packet_per_slot 1} {
        if {[dict exists $mac_parameters $parameter]} { set value [dict get $mac_parameters $parameter] }
        $class set $binding $value
    }
}

proc prepare_mac {} { prepare_tdma_class Module/UW/TDMA }

proc create_mac {i} {
    global mac_parameters
    set module [new Module/UW/TDMA]
    $module setMacAddr $i
    $module setSlotNumber [dict get $mac_parameters slot_assignment $i]
    return $module
}

proc start_macs {} {
    global ns mac count
    for {set i 1} {$i <= $count} {incr i} { $ns at 0 [list $mac($i) start] }
}
