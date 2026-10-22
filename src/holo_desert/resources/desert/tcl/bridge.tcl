# SPDX-License-Identifier: MIT
# The scheduler is held inside a callback at each barrier, not replaced or reset.
foreach lib {libMiracle.so libMiracleBasicMovement.so libmphy.so libmmac.so libUwmStd.so libuwcsmaaloha.so libuwaloha.so libuwip.so libuwstaticrouting.so libuwmll.so libuwudp.so libuwapplication.so} {
    load $lib
}
source [lindex $argv 0]
foreach lib $extra_libraries { load $lib }
foreach lib {libWOSS.so libWOSSPhy.so} { load $lib }
load libuwcbr.so
load libuwvbr.so
foreach lib {libuwem_channel.so libuwem_propagation.so libuwem_phy.so libuwem_antenna.so libuwoptical_propagation.so libuwoptical_channel.so libuwoptical_phy.so} { load $lib }
load /opt/holo/libholobridge.so
PacketHeaderManager set tab_(PacketHeader/HoloNative) 1
source /opt/holo/desert/tcl/modules/mac_${mac_adapter}.tcl
source /opt/holo/desert/tcl/modules/routing_${routing_adapter}.tcl
set mac_queue_command getQueueSize
set mac_stat_commands {}
prepare_mac
prepare_routing
set ns [new Simulator]
$ns use-Miracle
global defaultRNG
for {set i 0} {$i < $seed} {incr i} { $defaultRNG next-substream }
set trace [open /dev/null w]
set channel [new Module/UnderwaterChannel]
$channel set propSpeed_ $sound_speed
if {$environment_adapter eq "woss"} { source /opt/holo/desert/tcl/modules/environment_woss.tcl }
if {$environment_adapter in {optical em}} { source /opt/holo/desert/tcl/modules/environment_${environment_adapter}.tcl }
Module/MPhy/BPSK set BitRate_ $bitrate
Module/MPhy/BPSK/Underwater set MaxTxSPL_dB_ $power
Module/MPhy/BPSK/Underwater set MinTxSPL_dB_ $power
Module/MPhy/BPSK/Underwater set SPLOptimization_ 0
Module/MPhy/BPSK/Underwater set CentralFreqOptimization_ 0
Module/MPhy/BPSK/Underwater set BandwidthOptimization_ 0
Module/MPhy/BPSK/Underwater/HOLO set node_id_ 0
Module/UW/APPLICATION set drop_out_of_order_ 0
Module/UW/APPLICATION set period_ 100000000
Module/HoloProbe set node_id_ 0
if {$multiphy_enabled} { source /opt/holo/desert/tcl/modules/multiphy.tcl }

if {![llength [info commands create_routing]]} {
    proc create_routing {i} { global routing_class; return [new $routing_class] }
}
for {set i 1} {$i <= $count} {incr i} {
    set node($i) [$ns create-M_Node $trace $trace]
    set app($i) [new Module/UW/APPLICATION/HOLO]
    set udp($i) [new Module/UW/UDP]
    set routing($i) [create_routing $i]
    set ip($i) [new Module/UW/IP]
    set probe($i) [new Module/HoloProbe]
    set mll($i) [new Module/UW/MLL]
    set mac($i) [create_mac $i]
    set phy($i) [new $phy_class($i)]
    set settings $acoustic($i)
    set mask($i) [new MSpectralMask/Rect]
    if {$environment_adapter in {optical em}} {
        configure_medium_phy $i
    } else {
    if {$environment_adapter eq "woss"} {
        set propagation($i) [new WOSS/MPropagation]
        $propagation($i) setWossManager $woss_manager
    } else {
        set propagation($i) [new MPropagation/Underwater]
        foreach {key binding} {spreading practicalSpreading_} {
            $propagation($i) set $binding [dict get $settings $key]
        }
    }
    foreach {key binding} {shipping shipping_ wind_speed_mps windspeed_} {
        $propagation($i) set $binding [dict get $settings $key]
    }
    $mask($i) setFreq [dict get $settings frequency_hz]
    $mask($i) setBandwidth [dict get $settings bandwidth_hz]
    foreach {key binding} {tx_power_db MaxTxSPL_dB_ tx_power_db MinTxSPL_dB_ bitrate_bps BitRate_ rx_snr_penalty_db RxSnrPenalty_dB_ acquisition_threshold_db AcquisitionThreshold_dB_} {
        $phy($i) set $binding [dict get $settings $key]
    }
    }
    $phy($i) set node_id_ $i
    if {$environment_adapter eq "woss"} {
        foreach binding {SPLOptimization_ CentralFreqOptimization_ BandwidthOptimization_} { $phy($i) set $binding 0 }
    }
    set modules [list $app($i) $udp($i) $routing($i) $ip($i) $probe($i) $mll($i) $mac($i) $phy($i)]
    set layer 8
    if {$multiphy_enabled} {
        prepare_multi_phy $i
        set modules [lreplace $modules end end $multi_controller($i)]
        incr layer [llength $multi_indices($i)]
    }
    set application_layer($i) $layer
    foreach module $modules {
        $node($i) addModule $layer $module 0
        incr layer -1
    }
    for {set j 0} {$j < 7} {incr j} {
        $node($i) setConnection [lindex $modules $j] [lindex $modules [expr {$j + 1}]] 0
    }
    if {$multiphy_enabled} { connect_multi_phy $i } else { $node($i) addToChannel $channel $phy($i) 0 }
    set port [$udp($i) assignPort $app($i)]
    if {$port != 1} { error "Unexpected UDP application port $port" }
    $ip($i) addr $i
    initialize_routing $i
    $app($i) set node_ID_ $i
    $probe($i) set node_id_ $i
    if {$environment_adapter eq "woss"} { set position($i) [new WOSS/Position] } else { set position($i) [new Position/BM] }
    $node($i) addPosition $position($i)
    if {$environment_adapter eq "woss"} { update_woss_position $i {*}$initial_position($i) }
    set posdb($i) [new PlugIn/PositionDB]
    $node($i) addPlugin $posdb($i) 20 PDB
    $posdb($i) addpos $i $position($i)
    if {$environment_adapter eq "woss"} {
        set estimator($i) [new WOSS/PlugIn/ChannelEstimator]
        $estimator($i) setChannelEstimator $channel_estimator
        $estimator($i) insertNode [$mac($i) addr] $position($i)
        $node($i) addPlugin $estimator($i) 19 CHE
        $woss_creator setCustomAngles $position($i) 0 -90 90
    }
    set interf($i) [new MInterference/MIV]
    $interf($i) set maxinterval_ 1000
    $phy($i) setPropagation $propagation($i)
    $phy($i) setSpectralMask $mask($i)
    $phy($i) setInterference $interf($i)
    if {$multiphy_enabled} {
        # Keep each PHY's independently configured propagation/mask/interference.
        set index [lindex $multi_indices($i) 0]
        $phy($i) setPropagation $interface_prop($i,$index)
        $phy($i) setSpectralMask $interface_mask($i,$index)
        $phy($i) setInterference $interface_interf($i,$index)
    }
    puts "{\"event\":\"node_info\",\"time\":0,\"node\":$i,\"mac_address\":[$mac($i) addr]}"
}
configure_routes
start_macs
for {set i 1} {$i <= $count} {incr i} {
    for {set j 1} {$j <= $count} {incr j} {
        $mll($i) addentry $j [$mac($j) addr]
    }
}

source /opt/holo/desert/tcl/modules/native_applications.tcl
configure_native_applications

proc number {s} {
    if {![string is double -strict $s] || [string match -nocase *nan* $s] || [string match -nocase *inf* $s]} { error "Non-finite numeric argument" }
    return $s
}
proc nodeid {s} {
    global count
    if {![string is integer -strict $s] || $s < 1 || $s > $count} { error "Unknown node" }
    return $s
}
proc observed_counter {module command} {
    if {[catch {$module $command} value]} { return null }
    if {![string is double -strict $value] || [string match -nocase *nan* $value] || [string match -nocase *inf* $value]} { return null }
    return $value
}
proc barrier {} {
    global ns position propagation app phy mac count mac_queue_command mac_stat_commands environment_adapter multiphy_enabled
    set now [$ns now]
    puts "{\"event\":\"barrier\",\"time\":$now}"
    flush stdout
    while {[gets stdin line] >= 0} {
        set advancing 0
        if {[catch {
            set op [lindex $line 0]
            switch -- $op {
                POSITION {
                    if {[llength $line] ni {6 7 9}} { error "POSITION requires node x y z state_time and optional yaw/pitch/roll radians" }
                    lassign $line op id x y z state_time yaw pitch roll
                    if {$yaw eq ""} { set yaw 0 }
                    if {$pitch eq ""} { set pitch 0 }; if {$roll eq ""} { set roll 0 }
                    number $yaw; number $pitch; number $roll
                    nodeid $id
                    if {abs([number $state_time] - $now) > 0.000001} { error "Position timestamp differs from scheduler" }
                    number $x; number $y; number $z
                    if {$environment_adapter eq "optical" && ($z >= 0 || $z < -20)} { error "Optical noise LUT covers underwater depths through 20 m" }
                    if {$environment_adapter eq "optical"} { $propagation($id) setHeading $position($id) $yaw $pitch $roll }
                    set geographic {}
                    if {$environment_adapter eq "woss"} {
                        set geographic [update_woss_position $id $x $y $z]
                    } else {
                        $position($id) setX_ $x
                        $position($id) setY_ $y
                        $position($id) setZ_ $z
                    }
                    puts "{\"event\":\"position_applied\",\"time\":$now,\"node\":$id,\"x\":$x,\"y\":$y,\"z\":$z$geographic}"
                }
                SEND {
                    if {$environment_adapter eq "woss"} { validate_woss_geometry }
                    if {[llength $line] != 4} { error "SEND requires source destination hex" }
                    lassign $line op src dst hex
                    nodeid $src
                    nodeid $dst
                    $app($src) sendhex $dst $hex
                }
                POWER {
                    if {[llength $line] != 3} { error "POWER requires node dB" }
                    lassign $line op id db
                    nodeid $id
                    number $db
                    if {$environment_adapter in {optical em}} {
                        if {$environment_adapter eq "optical" && ($db < 1e-15 || $db > 10000)} { error "Optical power must be watts in supported range" }
                        if {$environment_adapter eq "em" && ($db < -100 || $db > 100)} { error "EM power must be dBm in supported range" }
                        $phy($id) set TxPower_ $db
                        set unit [expr {$environment_adapter eq "optical" ? "tx_power_w" : "tx_power_dbm"}]
                    } else {
                        if {$db < 0 || $db > 200} { error "Acoustic source level outside supported range" }
                        $phy($id) set MaxTxSPL_dB_ $db
                        $phy($id) set MinTxSPL_dB_ $db
                        set unit tx_power_db
                    }
                    puts "{\"event\":\"power_applied\",\"time\":$now,\"node\":$id,\"$unit\":$db}"
                }
                INTERFACE {
                    if {!$multiphy_enabled || [llength $line] != 3} { error "INTERFACE requires a multiPHY node and interface index" }
                    lassign $line op id index
                    nodeid $id
                    select_multi_interface $id $index
                }
                STATS {
                    if {$multiphy_enabled} { observe_multi_phy }
                    if {[info procs observe_routing] ne {}} { observe_routing }
                    if {[llength [info commands observe_ranging]]} { observe_ranging }
                    for {set id 1} {$id <= $count} {incr id} {
                        set q [observed_counter $mac($id) $mac_queue_command]
                        set specific {}
                        foreach {key command} $mac_stat_commands {
                            lappend specific "\"$key\":[observed_counter $mac($id) $command]"
                        }
                        puts "{\"event\":\"mac_specific_stats\",\"time\":$now,\"node\":$id,\"values\":{[join $specific ,]}}"
                        puts "{\"event\":\"stats\",\"time\":$now,\"node\":$id,\"app_sent\":[$app($id) getsentpkts],\"app_received\":[$app($id) getrecvpkts],\"mac_queue\":$q,\"mac_data_tx\":[observed_counter $mac($id) getDataPktsTx],\"mac_data_rx\":[observed_counter $mac($id) getDataPktsRx],\"mac_error_rx\":[observed_counter $mac($id) getErrorPktsRx],\"mac_discarded_tx\":[observed_counter $mac($id) getDiscardedPktsTx],\"phy_noise_errors\":[observed_counter $phy($id) getErrorPktsNoise],\"phy_interference_errors\":[observed_counter $phy($id) getErrorPktsInterf]}"
                    }
                }
                STEP {
                    if {$environment_adapter eq "woss"} { validate_woss_geometry }
                    if {[llength $line] != 2} { error "STEP requires target time" }
                    set target [number [lindex $line 1]]
                    if {$target <= $now} { error "STEP must advance time" }
                    $ns at $target barrier
                    set advancing 1
                }
                STOP { if {$environment_adapter eq "woss"} { close_woss }; exit 0 }
                default { error "Unknown command" }
            }
            flush stdout
        } reason]} {
            # Do not put arbitrary exception text into JSON without escaping.
            puts stderr "Holo bridge command failed: $reason"
            puts "{\"event\":\"error\",\"time\":$now,\"reason\":\"invalid bridge command; see engine log\"}"
            flush stdout
            exit 2
        }
        if {$advancing} { return }
    }
    exit 0
}
$ns at 0.0 barrier
$ns run
