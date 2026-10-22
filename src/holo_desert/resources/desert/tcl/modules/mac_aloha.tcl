# SPDX-License-Identifier: MIT
proc prepare_mac {} {
    global mac_class buffer_packets bounded_queue
    # CSMA freezes has_buffer_queue in its constructor; ALOHA always enables it.
    if {$mac_class eq "Module/UW/CSMA_ALOHA"} {
        $mac_class set buffer_pkts_ [expr {$bounded_queue ? $buffer_packets : -1}]
    }
}

proc create_mac {i} {
    global mac_class max_tries buffer_packets ack
    set module [new $mac_class]
    $module set max_tx_tries_ $max_tries
    $module set buffer_pkts_ $buffer_packets
    $module set max_payload_ 4096
    if {$ack} { $module setAckMode } else { $module setNoAckMode }
    $module initialize
    return $module
}

proc start_macs {} {}
