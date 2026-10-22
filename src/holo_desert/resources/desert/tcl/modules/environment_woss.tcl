# Native no-database Bellhop configuration. All files live in the session directory.
set woss_utilities [new WOSS/Utilities]
WOSS/Manager/Simple set is_time_evolution_active -1
WOSS/Manager/Simple set space_sampling 0
set woss_manager [new WOSS/Manager/Simple]
WOSS/Position set compDistance_ 0
WOSS/Definitions/RandomGenerator/NS2 set rep_number_ $seed
set random_generator [new WOSS/Definitions/RandomGenerator/NS2]
$random_generator initialize
set definitions [new WOSS/Definitions/Handler]
foreach {command class} {
    setSSPCreator WOSS/Definitions/SSP
    setSedimentCreator WOSS/Definitions/Sediment
    setPressureCreator WOSS/Definitions/Pressure
    setTimeArrCreator WOSS/Definitions/TimeArr
    setTransducerCreator WOSS/Definitions/Transducer
    setTimeReferenceCreator WOSS/Definitions/TimeReference/NS2
    setAltimetryCreator WOSS/Definitions/Altimetry/Flat
    setLocationCreator WOSS/Position
} { $definitions $command [new $class] }
$definitions setRandomGeneratorCreator $random_generator
file mkdir [file join [pwd] bellhop]
WOSS/Creator/Database/Binary/Results/TimeArr set debug 0
WOSS/Creator/Database/Binary/Results/TimeArr set woss_db_debug 0
set results [new WOSS/Creator/Database/Binary/Results/TimeArr]
$results set space_sampling 0
$results setDbPathName [file join [pwd] bellhop results.dat]
foreach {key value} {evolution_time_quantum -1 range -1 total_range_steps -1 depth 0} {
    WOSS/Definitions/Altimetry/Flat set $key $value
}
set altimetry [new WOSS/Definitions/Altimetry/Flat]
set db_manager [new WOSS/Database/Manager]
$db_manager setCustomAltimetry $altimetry
$db_manager setCustomSediment HoloSynthetic [dict get $woss_parameters sediment_speed_mps] 200 [dict get $woss_parameters sediment_density_g_cm3] [dict get $woss_parameters sediment_attenuation_db_lambda] 0.8 1
set ssp_path [file join [pwd] ssp.txt]
set ssp_file [open $ssp_path w]
puts $ssp_file "SSP\n\n[dict get $woss_parameters origin_latitude_deg]\n[dict get $woss_parameters origin_longitude_deg]\n"
foreach point $woss_ssp { puts $ssp_file "0 [lindex $point 0] [lindex $point 1]" }
close $ssp_file
$db_manager setCustomSSP 0 $ssp_path
$db_manager setCustomBathymetry [dict get $woss_parameters origin_latitude_deg] [dict get $woss_parameters origin_longitude_deg] -500 2 0 [dict get $woss_parameters water_depth_m] 1000000 [dict get $woss_parameters water_depth_m]
foreach {key value} {
    debug 0 woss_debug 0 woss_clean_workdir 1 bellhop_arr_syntax 2 evolution_time_quantum -1
    total_runs 1 frequency_step 0 total_range_steps 3000 tx_min_depth_offset 0 tx_max_depth_offset 0
    total_transmitters 1 total_rx_depths 2 rx_min_depth_offset -0.1 rx_max_depth_offset 0.1
    total_rx_ranges 2 rx_min_range_offset -0.1 rx_max_range_offset 0.1 total_rays 0
    min_angle -90 max_angle 90 ssp_depth_precision 1e-8 normalized_ssp_depth_steps 100000
} { WOSS/Creator/Bellhop set $key $value }
set woss_creator [new WOSS/Creator/Bellhop]
$woss_creator setWorkDirPath [file join [pwd] bellhop]
$woss_creator setBellhopPath /home/DESERT_Underwater/DESERT_buildCopy_LOCAL/bin
$woss_creator setBellhopBinName bellhop.exe
$woss_creator setBellhopMode 0 0 A
$woss_creator setBeamOptions 0 0 B
$woss_creator setBathymetryType 0 0 LL
$woss_creator setBathymetryMethod 0 0 S
$woss_creator setAltimetryType 0 0 L
$woss_creator setSimulationTimes 0 0 1 12 2009 0 0 1 1 12 2009 0 0 1
set controller [new WOSS/Controller]
$controller setTimeArrResultsDbCreator $results
$controller setWossDbManager $db_manager
$controller setWossManager $woss_manager
$controller setWossCreator $woss_creator
$controller setTransducerhandler [new WOSS/Definitions/TransducerHandler]
$controller initialize
WOSS/ChannelEstimator set space_sampling_ 0
WOSS/ChannelEstimator set avg_coeff_ 0.5
set channel_estimator [new WOSS/ChannelEstimator]
WOSS/Module/Channel set channel_eq_snr_threshold_db_ 0
WOSS/Module/Channel set channel_symbol_resolution_ 5e-3
WOSS/Module/Channel set channel_eq_time_ -1
set channel [new WOSS/Module/Channel]
$channel setWossManager $woss_manager
$channel setChannelEstimator $channel_estimator

proc update_woss_position {id x y z} {
    global position woss_utilities woss_parameters
    if {$z >= -0.1 || $z <= -[dict get $woss_parameters water_depth_m]+0.1} { error "WOSS node requires 0.1 m clearance from sea surface and seabed" }
    # Holo X forward, Y left; bearing is clockwise from geographic north.
    set bearing [expr {[dict get $woss_parameters x_bearing_deg] - atan2($y,$x)*180/acos(-1)}]
    set distance [expr {hypot($x,$y)}]
    if {$distance > 100000} { error "WOSS local frame supports offsets up to 100 km" }
    set lat [$woss_utilities getLatfromDistBearing [dict get $woss_parameters origin_latitude_deg] [dict get $woss_parameters origin_longitude_deg] $bearing $distance]
    set lon [$woss_utilities getLongfromDistBearing [dict get $woss_parameters origin_latitude_deg] [dict get $woss_parameters origin_longitude_deg] $bearing $distance]
    $position($id) setLatitude_ $lat
    $position($id) setLongitude_ $lon
    $position($id) setAltitude_ $z
    global woss_local_position
    set woss_local_position($id) [list $x $y $z]
    return ",\"latitude_deg\":$lat,\"longitude_deg\":$lon,\"altitude_m\":$z"
}
proc validate_woss_geometry {} {
    global woss_local_position count
    for {set i 1} {$i <= $count} {incr i} {
        lassign $woss_local_position($i) x y z
        for {set j [expr {$i+1}]} {$j <= $count} {incr j} {
            lassign $woss_local_position($j) xx yy zz
            if {hypot($x-$xx,$y-$yy)<1} { error "WOSS Bellhop requires at least 1 m horizontal separation" }
        }
    }
}
proc close_woss {} {
    global db_manager woss_manager
    $db_manager closeAllConnections
    delete $db_manager
    delete $woss_manager
}
