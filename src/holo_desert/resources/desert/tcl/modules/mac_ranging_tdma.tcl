# SPDX-License-Identifier: MIT
# Native Module/UW/RANGING_TDMA: UwTDMA data slots plus a ranging frame per slot.
load libuwmmac_clmsgs.so
load libuwphy_clmsgs.so
load libuwtdma.so
load libuwranging_tdma.so

proc prepare_mac {} {
    global mac_parameters count buffer_packets mac_queue_command mac_stat_commands mac_bindings
    set mac_bindings {frame_duration guard_time tot_slots max_packet_per_slot queue_size_ fair_mode}
    set class Module/UW/RANGING_TDMA
    set mac_queue_command get_buffer_size
    # getCtrlPktsRx is not listed: the native counter also counts received data frames.
    set mac_stat_commands {upper_data_rx get_upper_data_pkts_rx sent_packets get_sent_pkts received_packets get_recv_pkts ranging_tx getCtrlPktsTx ranging_rx_errors getXCtrlPktsRx}
    # Class values must exist before the first new: the constructor sizes its tables from
    # tot_slots (unset: SIGFPE) and binds guard_time/tot_slots only with fair_mode 1.
    # RANGING_TDMA does not inherit the Tcl defaults of Module/UW/TDMA.
    foreach {key value} {debug_ 0 sea_trial_ 0 fair_mode 1 HDR_size_ 0 drop_old_ 0 checkPriority_ 0 mac2phy_delay_ 1e-9} { $class set $key $value }
    $class set queue_size_ $buffer_packets
    $class set tot_slots $count
    foreach {parameter binding} {frame_duration_s frame_duration guard_time_s guard_time max_packets_per_slot max_packet_per_slot} {
        $class set $binding [dict get $mac_parameters $parameter]
    }
}

proc create_mac {i} {
    # Slot and ranging index are the native creation order (node i owns slot i-1);
    # setSlotNumber is never called because the travel-time arithmetic assumes that order.
    set module [new Module/UW/RANGING_TDMA]
    $module setMacAddr $i
    return $module
}

proc start_macs {} {
    global ns mac count
    # Travel times are computed from absolute time modulo the frame: every MAC starts at 0.
    for {set i 1} {$i <= $count} {incr i} { $ns at 0 [list $mac($i) start] }
}

proc observe_ranging {} {
    global mac count ns sound_speed
    for {set observer 1} {$observer <= $count} {incr observer} {
        for {set a 0} {$a < $count} {incr a} {
            for {set b [expr {$a+1}]} {$b < $count} {incr b} {
                set travel [$mac($observer) get_distance $a $b]
                set distance null
                set valid false
                # get_distance returns the one-way travel time in seconds, -1 when never measured.
                if {[string is double -strict $travel] && $travel >= 0 && ![string match -nocase *nan* $travel] && ![string match -nocase *inf* $travel]} {
                    set distance [expr {$travel*$sound_speed}]
                    set valid true
                } else {set travel null}
                puts "{\"event\":\"ranging_estimate\",\"time\":[$ns now],\"node\":$observer,\"peer_a\":[expr {$a+1}],\"peer_b\":[expr {$b+1}],\"travel_time_s\":$travel,\"distance_m\":$distance,\"valid\":$valid,\"measurement_time\":null,\"protocol\":\"ranging_tdma\"}"
            }
        }
    }
}
