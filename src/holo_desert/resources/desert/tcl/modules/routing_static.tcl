proc prepare_routing {} {}
proc initialize_routing {i} {}
proc configure_routes {} {
    global routes routing
    foreach entry $routes {
        lassign $entry src dst hop
        $routing($src) addRoute $dst $hop
    }
}
