# SPDX-License-Identifier: MIT
# The scheduler is held inside a callback at each barrier, not replaced or reset.
foreach lib {libMiracle.so libMiracleBasicMovement.so libmphy.so libmmac.so libUwmStd.so libuwcsmaaloha.so libuwaloha.so libuwip.so libuwstaticrouting.so libuwmll.so libuwudp.so libuwapplication.so} {
    load $lib
}
source [lindex $argv 0]
foreach lib $extra_libraries { load $lib }
load /opt/holo/libholobridge.so
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

for {set i 1} {$i <= $count} {incr i} {
    set node($i) [$ns create-M_Node $trace $trace]
    set app($i) [new Module/UW/APPLICATION/HOLO]
    set udp($i) [new Module/UW/UDP]
    set routing($i) [new $routing_class]
    set ip($i) [new Module/UW/IP]
    set probe($i) [new Module/HoloProbe]
    set mll($i) [new Module/UW/MLL]
    set mac($i) [create_mac $i]
    set phy($i) [new $phy_class($i)]
    set settings $acoustic($i)
    set propagation($i) [new MPropagation/Underwater]
    foreach {key binding} {spreading practicalSpreading_ shipping shipping_ wind_speed_mps windspeed_} {
        $propagation($i) set $binding [dict get $settings $key]
    }
    set mask($i) [new MSpectralMask/Rect]
    $mask($i) setFreq [dict get $settings frequency_hz]
    $mask($i) setBandwidth [dict get $settings bandwidth_hz]
    foreach {key binding} {tx_power_db MaxTxSPL_dB_ tx_power_db MinTxSPL_dB_ bitrate_bps BitRate_ rx_snr_penalty_db RxSnrPenalty_dB_ acquisition_threshold_db AcquisitionThreshold_dB_} {
        $phy($i) set $binding [dict get $settings $key]
    }
    $phy($i) set node_id_ $i
    set modules [list $app($i) $udp($i) $routing($i) $ip($i) $probe($i) $mll($i) $mac($i) $phy($i)]
    set layer 8
    foreach module $modules {
        $node($i) addModule $layer $module 0
        incr layer -1
    }
    for {set j 0} {$j < 7} {incr j} {
        $node($i) setConnection [lindex $modules $j] [lindex $modules [expr {$j + 1}]] 0
    }
    $node($i) addToChannel $channel $phy($i) 0
    set port [$udp($i) assignPort $app($i)]
    if {$port != 1} { error "Unexpected UDP application port $port" }
    $ip($i) addr $i
    initialize_routing $i
    $app($i) set node_ID_ $i
    $probe($i) set node_id_ $i
    set position($i) [new Position/BM]
    $node($i) addPosition $position($i)
    set posdb($i) [new PlugIn/PositionDB]
    $node($i) addPlugin $posdb($i) 20 PDB
    $posdb($i) addpos $i $position($i)
    set interf($i) [new MInterference/MIV]
    $interf($i) set maxinterval_ 1000
    $phy($i) setPropagation $propagation($i)
    $phy($i) setSpectralMask $mask($i)
    $phy($i) setInterference $interf($i)
    puts "{\"event\":\"node_info\",\"time\":0,\"node\":$i,\"mac_address\":[$mac($i) addr]}"
}
configure_routes
start_macs
for {set i 1} {$i <= $count} {incr i} {
    for {set j 1} {$j <= $count} {incr j} {
        $mll($i) addentry $j [$mac($j) addr]
    }
}

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
    global ns position app phy mac count mac_queue_command mac_stat_commands
    set now [$ns now]
    puts "{\"event\":\"barrier\",\"time\":$now}"
    flush stdout
    while {[gets stdin line] >= 0} {
        set advancing 0
        if {[catch {
            set op [lindex $line 0]
            switch -- $op {
                POSITION {
                    if {[llength $line] != 6} { error "POSITION requires node x y z state_time" }
                    lassign $line op id x y z state_time
                    nodeid $id
                    if {abs([number $state_time] - $now) > 0.000001} { error "Position timestamp differs from scheduler" }
                    $position($id) setX_ [number $x]
                    $position($id) setY_ [number $y]
                    $position($id) setZ_ [number $z]
                    puts "{\"event\":\"position_applied\",\"time\":$now,\"node\":$id,\"x\":$x,\"y\":$y,\"z\":$z}"
                }
                SEND {
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
                    $phy($id) set MaxTxSPL_dB_ [number $db]
                    $phy($id) set MinTxSPL_dB_ [number $db]
                    puts "{\"event\":\"power_applied\",\"time\":$now,\"node\":$id,\"tx_power_db\":$db}"
                }
                STATS {
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
                    if {[llength $line] != 2} { error "STEP requires target time" }
                    set target [number [lindex $line 1]]
                    if {$target <= $now} { error "STEP must advance time" }
                    $ns at $target barrier
                    set advancing 1
                }
                STOP { exit 0 }
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
