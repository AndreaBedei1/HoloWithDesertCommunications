# DESERT native Position-Based Routing (network/uwPositionBasedRouting) without global ground truth.
# - anchor  (Module/UW/PosBasedRt): its own surveyed position (scenario constant), its static
#   next-hop table, and the vehicle state carried by the headers it receives.
# - vehicle (Module/UW/PosBasedRt/ROV): its own navigation fix, copied from its own POSITION
#   command, and the surveyed positions of the anchors. It never sees another vehicle's position.
# The bridge's live Position objects ($position(i)) are never handed to a routing module.
# libuwsmposition.so and libuwposbasedrt.so come with the extra libraries the builder lists.

proc prepare_routing {} {
    global routing_bindings pbr_parameters
    # ROV_speed_ is bound only by the anchor class (and never used natively); vehicles read back null.
    set routing_bindings {maxTxRange_ ROV_speed_}
    foreach class {Module/UW/PosBasedRt Module/UW/PosBasedRt/ROV} { $class set debug_ 0 }
    Module/UW/PosBasedRt set maxTxRange_ [dict get $pbr_parameters anchor_range_m]
    Module/UW/PosBasedRt/ROV set maxTxRange_ [dict get $pbr_parameters vehicle_range_m]
}

proc create_routing {i} {
    global pbr_role
    if {$pbr_role($i) eq "vehicle"} { return [new Module/UW/PosBasedRt/ROV] }
    return [new Module/UW/PosBasedRt]
}

# The routing address must equal the IP address set just before.
proc initialize_routing {i} {
    global routing
    $routing($i) addr $i
}

# A constant Position holding a surveyed value. The native setters copy it once and free
# the copy's Tcl name, so every call gets a fresh object (reuse aborts with a double free).
proc pbr_survey_object {coordinates} {
    lassign $coordinates x y z
    set p [new Position/BM]
    $p setX_ $x
    $p setY_ $y
    $p setZ_ $z
    return $p
}

proc configure_routes {} {
    global count routing pbr_role pbr_survey pbr_routes pbr_nav
    # Native setters print to stdout; keep the JSON event lines whole.
    flush stdout
    for {set i 1} {$i <= $count} {incr i} {
        if {$pbr_role($i) eq "anchor"} {
            $routing($i) setNodePosition [pbr_survey_object $pbr_survey($i)]
            continue
        }
        # Own navigation estimate; the vehicle class requires a Position/UWSM.
        set pbr_nav($i) [new Position/UWSM]
        $routing($i) setROVPosition $pbr_nav($i)
        for {set j 1} {$j <= $count} {incr j} {
            if {$pbr_role($j) eq "anchor"} { $routing($i) addPosition_IPotherNodes [pbr_survey_object $pbr_survey($j)] $j }
        }
    }
    foreach entry $pbr_routes {
        lassign $entry src dst hop kind
        $routing($src) addRoute $dst $hop [expr {$kind eq "vehicle" ? "toMovingNode" : "toFixedNode"}]
    }
    flush stdout
}

# Bridge hook in POSITION: a vehicle's own fix reaches only its own routing module.
# UWSM setX/Y/Z also reset source and destination, so headers carry a hold at the fix.
proc routing_position_applied {id x y z now} {
    global pbr_role pbr_nav
    if {$pbr_role($id) ne "vehicle"} { return }
    $pbr_nav($id) setX_ $x
    $pbr_nav($id) setY_ $y
    $pbr_nav($id) setZ_ $z
}
