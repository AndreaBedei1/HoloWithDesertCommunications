// SPDX-License-Identifier: MIT
// Minimal external application interface to DESERT 4.0 UW/APPLICATION.
// All channel/MAC/routing behavior remains in the loaded DESERT modules.
#include <uwApplication_module.h>
#include <uwip-module.h>
#include <uwudp-module.h>
#include <scheduler.h>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <underwater-bpsk.h>
#include <mac.h>

static std::string hexify(const char* p, unsigned n) {
    std::ostringstream s;
    for (unsigned i = 0; i < n; ++i)
        s << std::hex << std::setfill('0') << std::setw(2) << (unsigned)(unsigned char)p[i];
    return s.str();
}

class HoloApplication : public uwApplicationModule {
public:
    HoloApplication() : uwApplicationModule() {
        // UW/APPLICATION::stop expects this timer even if start was never called.
        // We inject explicitly on the scheduler thread, so never schedule traffic.
        chkTimerPeriod = new uwSendTimerAppl(this);
    }
    int command(int argc, const char*const* argv) override {
        if (argc == 4 && std::strcmp(argv[1], "sendhex") == 0) {
            const std::string h(argv[3]);
            if (h.empty() || h.size() % 2 || h.size() > 2 * MAX_LENGTH_PAYLOAD ||
                h.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos) {
                Tcl::instance().result("invalid hex payload (limit 4096 bytes)");
                return TCL_ERROR;
            }
            char* end = nullptr;
            long dst = std::strtol(argv[2], &end, 10);
            if (*end || dst < 1 || dst > 254) return TCL_ERROR;
            Packet* p = Packet::alloc();
            auto* ch = HDR_CMN(p);
            auto* ah = HDR_DATA_APPLICATION(p);
            ch->uid() = uidcnt++;
            ch->ptype() = PT_DATA_APPLICATION;
            ch->direction() = hdr_cmn::DOWN;
            ch->timestamp() = Scheduler::instance().clock();
            ch->size() = h.size() / 2;
            HDR_UWUDP(p)->dport() = 1;
            HDR_UWIP(p)->daddr() = dst;
            ah->payload_size() = h.size() / 2;
            // Avoid UW/APPLICATION's USHRT_MAX-sized lookup's last index.
            ah->sn() = (txsn % 65534) + 1;
            ah->rftt_valid() = false;
            ah->priority() = 0;
            for (size_t i = 0; i < h.size(); i += 2)
                ah->payload_msg[i / 2] = (char)std::strtoul(h.substr(i, 2).c_str(), nullptr, 16);
            incrPktSent();
            std::cout << std::setprecision(15) << "{\"event\":\"app_tx\",\"time\":"
                << ch->timestamp() << ",\"node\":" << node_id << ",\"destination_address\":" << dst
                << ",\"ns_uid\":" << ch->uid() << ",\"wire_hex\":\"" << h << "\"}" << std::endl;
            sendDown(p);
            return TCL_OK;
        }
        return uwApplicationModule::command(argc, argv);
    }
    void recv(Packet* p) override {
        auto* ch = HDR_CMN(p);
        auto* ah = HDR_DATA_APPLICATION(p);
        if (ch->ptype() == PT_DATA_APPLICATION && ah->payload_size() <= MAX_LENGTH_PAYLOAD) {
            std::cout << std::setprecision(15) << "{\"event\":\"rx\",\"time\":"
                << Scheduler::instance().clock() << ",\"node\":" << node_id
                << ",\"source_address\":" << (int)HDR_UWIP(p)->saddr()
                << ",\"network_tx_time\":" << ch->timestamp()
                << ",\"ns_uid\":" << ch->uid() << ",\"wire_hex\":\""
                << hexify(ah->payload_msg, ah->payload_size()) << "\"}" << std::endl;
        }
        // Official receive accounting, validation, ownership and Packet::free.
        uwApplicationModule::recv(p);
    }
};

static class HoloApplicationClass : public TclClass {
public:
    HoloApplicationClass() : TclClass("Module/UW/APPLICATION/HOLO") {}
    TclObject* create(int, const char*const*) override { return new HoloApplication; }
} class_holo_application;

// Transparent observation point below routing/IP; never originates/forwards
// messages outside the DESERT stack. A downward event at a relay demonstrates
// network-layer forwarding; it is not labelled a successful PHY transmission.
class HoloProbe : public Module {
    int node_id_ = 0;
public:
    HoloProbe() { bind("node_id_", &node_id_); }
    void recv(Packet* p) override {
        if (HDR_CMN(p)->direction() == hdr_cmn::DOWN) {
            if (HDR_CMN(p)->ptype() == PT_DATA_APPLICATION) {
                auto* ah = HDR_DATA_APPLICATION(p);
                std::cout << std::setprecision(15) << "{\"event\":\"forward\",\"time\":"
                    << Scheduler::instance().clock() << ",\"node\":" << node_id_
                    << ",\"source_address\":" << (int)HDR_UWIP(p)->saddr()
                    << ",\"destination_address\":" << (int)HDR_UWIP(p)->daddr()
                    << ",\"next_hop_address\":" << HDR_CMN(p)->next_hop()
                    << ",\"wire_hex\":\"" << hexify(ah->payload_msg, ah->payload_size()) << "\"}" << std::endl;
            }
            sendDown(p);
        } else sendUp(p);
    }
};
static class HoloProbeClass : public TclClass {
public:
    HoloProbeClass() : TclClass("Module/HoloProbe") {}
    TclObject* create(int, const char*const*) override { return new HoloProbe; }
} class_holo_probe;

// Observe the official underwater PHY without replacing any of its decisions.
class HoloPhy : public UnderwaterMPhyBpsk {
    int node_id_ = 0;
    void report(const char* event, const std::string& wire, double timestamp,
                double duration, const char* outcome, double snr, int next_hop, int transmitter) {
        std::cout << std::setprecision(15) << "{\"event\":\"" << event << "\",\"time\":"
            << timestamp << ",\"node\":" << node_id_ << ",\"duration_s\":" << duration
            << ",\"outcome\":\"" << outcome << "\",\"snr_db\":";
        if (std::isfinite(snr)) std::cout << snr; else std::cout << "null";
        std::cout << ",\"transmitter_mac\":" << transmitter << ",\"next_hop_mac\":" << next_hop
                  << ",\"wire_hex\":\"" << wire << "\"}" << std::endl;
    }
    std::string wire(Packet* p) {
        if (HDR_CMN(p)->ptype() != PT_DATA_APPLICATION) return "";
        auto* ah = HDR_DATA_APPLICATION(p);
        return hexify(ah->payload_msg, ah->payload_size());
    }
protected:
    void startTx(Packet* p) override {
        auto h = wire(p);
        if (!h.empty()) report("phy_tx_start", h, Scheduler::instance().clock(), HDR_MPHY(p)->duration,
                               "transmitting", 0, HDR_MAC(p)->macDA(), HDR_MAC(p)->macSA());
        UnderwaterMPhyBpsk::startTx(p);
    }
    void startRx(Packet* p) override {
        auto h = wire(p);
        bool busy_tx = txPending;
        bool busy_rx = PktRx != nullptr;
        auto* ph = HDR_MPHY(p);
        double snr = 10 * std::log10(ph->Pr / ph->Pn);
        UnderwaterMPhyBpsk::startRx(p);
        if (!h.empty()) {
            const char* outcome = PktRx == p ? "synchronized" :
                busy_tx ? "transmitter_busy" : busy_rx ? "receiver_busy_overlap" :
                ph->modulationType != modid ? "wrong_modulation" : "below_acquisition_threshold";
            report("phy_rx_start", h, Scheduler::instance().clock(), ph->duration,
                   outcome, snr, HDR_MAC(p)->macDA(), HDR_MAC(p)->macSA());
        }
    }
    void endRx(Packet* p) override {
        auto h = wire(p);
        bool synchronized = PktRx == p;
        auto* ph = HDR_MPHY(p);
        double duration = ph->duration;
        double snr = 10 * std::log10(ph->Pr / ph->Pn);
        int hop = HDR_MAC(p)->macDA(), transmitter = HDR_MAC(p)->macSA();
        int noise = getErrorPktsNoise(), interference = getErrorPktsInterf();
        UnderwaterMPhyBpsk::endRx(p); // may free p; use only saved values afterwards
        if (!h.empty()) report("phy_rx_end", h, Scheduler::instance().clock(), duration,
            !synchronized ? "not_synchronized" : getErrorPktsNoise() > noise ? "noise_error" :
            getErrorPktsInterf() > interference ? "interference_error" : "decoded", snr, hop, transmitter);
    }
public:
    HoloPhy() { bind("node_id_", &node_id_); }
};
static class HoloPhyClass : public TclClass {
public:
    HoloPhyClass() : TclClass("Module/MPhy/BPSK/Underwater/HOLO") {}
    TclObject* create(int, const char*const*) override { return new HoloPhy; }
} class_holo_phy;

extern "C" int Holobridge_Init(Tcl_Interp*) { return TCL_OK; }
