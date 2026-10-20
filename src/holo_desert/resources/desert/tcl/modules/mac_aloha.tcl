# SPDX-License-Identifier: MIT
proc prepare_mac {} {}

proc create_mac {i} {
    global mac_class max_tries buffer_packets ack
    set module [new $mac_class]
    # shortcut: historical constructor defaults determine queue mode; retain until legacy behavior is explicitly migrated.
    $module set max_tx_tries_ $max_tries
    $module set buffer_pkts_ $buffer_packets
    $module set max_payload_ 4096
    if {$ack} { $module setAckMode } else { $module setNoAckMode }
    $module initialize
    return $module
}

proc start_macs {} {}
