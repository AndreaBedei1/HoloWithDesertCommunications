proc configure_native_applications {} {
    global native_flows count node udp ns native_app application_layer
    set port_number 1
    foreach flow $native_flows {
        lassign $flow index class source destination start stop poisson period size period2 duration1 duration2
        incr port_number
        for {set id 1} {$id <= $count} {incr id} {
            $class set holo_node_ $id
            $class set holo_flow_ $index
            set app [new $class]
            set native_app($index,$id) $app
            $app set destAddr_ $destination
            $app set destPort_ $port_number
            $app set packetSize_ $size
            $app set PoissonTraffic_ $poisson
            $app set drop_out_of_order_ 0
            if {$class eq "Module/UW/CBR/HOLO"} {
                $app set period_ $period
            } else {
                $app set period1_ $period
                $app set period2_ $period2
                $app set timer_switch_1_ $duration1
                $app set timer_switch_2_ $duration2
            }
            # Distinct UDP endpoints share the existing native network stack.
            $node($id) addModule [expr {$application_layer($id)+1}] $app 0
            $node($id) setConnection $app $udp($id) 0
            if {[$udp($id) assignPort $app] != $port_number} { error "Native application port mismatch" }
        }
        $ns at $start [list $native_app($index,$source) start]
        $ns at $stop [list $native_app($index,$source) stop]
    }
}
