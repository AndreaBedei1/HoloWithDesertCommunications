proc prepare_routing {} {
    global flooding_parameters
    Module/UW/FLOODING set ttl_ [dict get $flooding_parameters ttl]
    Module/UW/FLOODING set maximum_cache_time_ [dict get $flooding_parameters maximum_cache_time_s]
    Module/UW/FLOODING set optimize_ [dict get $flooding_parameters optimize]
}
proc initialize_routing {i} {
    global routing
    $routing($i) addr $i
}
proc configure_routes {} {}
