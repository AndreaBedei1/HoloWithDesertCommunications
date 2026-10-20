# SPDX-License-Identifier: MIT
source [file join [file dirname [info script]] mac_tdma.tcl]
load libuwtdma_frame.so

proc prepare_mac {} { prepare_tdma_class Module/UW/TDMA_FRAME }

proc create_mac {i} {
    global frame_matrix
    set module [new Module/UW/TDMA_FRAME]
    $module setMacAddr $i
    $module setTopologyIndex $i
    $module setTopologySeparator { }
    $module setSTopologyFileName $frame_matrix
    return $module
}
