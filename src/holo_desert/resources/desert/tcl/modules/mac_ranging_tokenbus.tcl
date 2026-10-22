# SPDX-License-Identifier: MIT
source /opt/holo/desert/tcl/modules/mac_tokenbus.tcl
load libuwranging_tokenbus.so

proc observe_ranging {} {
    global mac count ns sound_speed
    for {set observer 1} {$observer <= $count} {incr observer} {
        $mac($observer) calc_distances
        for {set a 0} {$a < $count} {incr a} {
            for {set b [expr {$a+1}]} {$b < $count} {incr b} {
                set travel [$mac($observer) get_distance $a $b]
                set distance null
                set valid false
                if {[string is double -strict $travel] && $travel >= 0 && ![string match -nocase *nan* $travel] && ![string match -nocase *inf* $travel]} {
                    # Native get_distance returns one-way seconds, as in the official sample.
                    set distance [expr {$travel*$sound_speed}]
                    set valid true
                } else {set travel null}
                puts "{\"event\":\"ranging_estimate\",\"time\":[$ns now],\"node\":$observer,\"peer_a\":[expr {$a+1}],\"peer_b\":[expr {$b+1}],\"travel_time_s\":$travel,\"distance_m\":$distance,\"valid\":$valid,\"measurement_time\":null,\"protocol\":\"ranging_tokenbus\"}"
            }
        }
    }
}
