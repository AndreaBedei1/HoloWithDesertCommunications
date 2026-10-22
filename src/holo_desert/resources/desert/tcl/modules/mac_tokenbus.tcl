# SPDX-License-Identifier: MIT
load libuwcbr.so
load libuwtokenbus.so

proc prepare_mac {} {
    global mac_parameters mac_class count buffer_packets mac_queue_command mac_stat_commands mac_bindings
    set mac_bindings {n_nodes_ queue_size_ slot_time_ min_token_hold_time_ max_token_hold_time_}
    set mac_queue_command get_buffer_size
    set mac_stat_commands {token_resends get_count_token_resend token_regenerations get_count_token_regen invalid_tokens get_count_token_invalid bus_idle_expirations get_bus_idle_exp token_pass_expirations get_token_pass_exp}
    foreach {binding value} {debug_ 0 debug_tb 0 drop_old_ 0 checkPriority_ 0 mac2phy_delay_ 1e-9} {$mac_class set $binding $value}
    # Membership and ring timers are captured and started by the native constructor.
    $mac_class set n_nodes_ $count
    $mac_class set queue_size_ $buffer_packets
    foreach {parameter binding} {slot_time_s slot_time_ min_token_hold_s min_token_hold_time_ max_token_hold_s max_token_hold_time_} {
        $mac_class set $binding [dict get $mac_parameters $parameter]
    }
}

proc create_mac {i} {
    global mac_class
    set module [new $mac_class]
    $module setMacAddr $i
    return $module
}

proc start_macs {} {}
