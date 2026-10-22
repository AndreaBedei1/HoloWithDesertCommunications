# SPDX-License-Identifier: MIT
load libuwcbr.so
load libsun.so

proc prepare_routing {} {
    global sun_parameters
    Module/UW/SUNNode set PoissonTraffic_ [dict get $sun_parameters poisson_timing]
    Module/UW/SUNSink set PoissonTraffic_ 0
    foreach {parameter binding} {buffer_interval_s timer_buffer_ data_interval_s period_data_ status_interval_s period_status_ max_ack_errors max_ack_error_ max_retransmissions max_retx_ buffer_packets buffer_max_size_ probe_min_snr_db probe_min_snr_} {
        Module/UW/SUNNode set $binding [dict get $sun_parameters $parameter]
    }
    Module/UW/SUNSink set t_probe [dict get $sun_parameters probe_interval_s]
}

proc create_routing {i} {
    global sun_parameters
    if {$i == [dict get $sun_parameters sink]} {return [new Module/UW/SUNSink]}
    return [new Module/UW/SUNNode]
}

proc initialize_routing {i} {}

proc configure_routes {} {
    global routing count ns sun_parameters
    for {set i 1} {$i <= $count} {incr i} {$routing($i) initialize}
    $ns at 0.1 [list $routing([dict get $sun_parameters sink]) start]
}

proc observe_routing {} {
    global routing count ns sun_parameters
    for {set i 1} {$i <= $count} {incr i} {
        set role node
        set commands {acks getackcount data_packets getdatapktcount forwarded_packets getforwardedcount buffer_drops getdatapktdroppedbuffer retransmission_drops getdatapktdroppedmaxretx path_packets getpathestablishmentpktcount}
        set local_values {}
        if {$i == [dict get $sun_parameters sink]} {
            set role sink
            set commands {acks getackcount probes getprobepktcount}
        } else {
            set local_values "\"paths_established\":[$routing($i) getNpathsestablished],\"queue\":[$routing($i) getbufferstatus]"
        }
        set values {}
        foreach {name command} $commands {lappend values "\"$name\":[observed_counter $routing($i) $command]"}
        puts "{\"event\":\"routing_stats\",\"time\":[$ns now],\"node\":$i,\"protocol\":\"sun\",\"role\":\"$role\",\"values\":{$local_values},\"class_values\":{[join $values ,]},\"counter_scope\":\"module_class\"}"
    }
}
