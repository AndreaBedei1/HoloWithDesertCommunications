# SPDX-License-Identifier: MIT
load libuwcsburst.so

proc prepare_mac {} {
    global mac_parameters buffer_packets mac_queue_command mac_stat_commands mac_bindings
    set mac_bindings {queue_size max_packet_per_burst fix_sens_time rv_sens_time}
    set mac_queue_command get_buffer_size
    set mac_stat_commands {upper_data_rx get_upper_data_pkts_rx sent_packets get_sent_pkts received_packets get_recv_pkts}
    Module/UW/CSBURST set queue_size $buffer_packets
    foreach {parameter binding} {max_packets_per_burst max_packet_per_burst fixed_sensing_s fix_sens_time random_sensing_s rv_sens_time} {
        Module/UW/CSBURST set $binding [dict get $mac_parameters $parameter]
    }
}

proc create_mac {i} {
    set module [new Module/UW/CSBURST]
    $module setMacAddr $i
    return $module
}

proc start_macs {} {}
