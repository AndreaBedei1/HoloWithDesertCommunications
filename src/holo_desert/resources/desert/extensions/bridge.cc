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
#include <rng.h>
#include <uw-mac-DACAP-alter.h>
#include "corrected-bpsk.h"

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

// Upstream decisions stay delegated; the corrected variant replaces only endRx.
class HoloPhy : public UnderwaterMPhyBpsk {
    int node_id_ = 0;
    struct Observation {
        std::string wire;
        bool application, receiving;
        int uid, bits, packet_type, hop, transmitter;
        double pt, pr, pn, pi, duration, txtime, rxtime;
        Observation(Packet* p, bool is_receiving = true) {
            receiving = is_receiving;
            auto* ch = HDR_CMN(p);
            auto* ph = HDR_MPHY(p);
            application = ch->ptype() == PT_DATA_APPLICATION;
            if (!application && ch->ptype() == PT_DACAP) {
                const auto* dacap = HDR_DACAP(p);
                // DATA_PKT is private to pinned uw-mac-DACAP-alter.cpp's enum.
                application = dacap->dacap_type == 6 && dacap->orig_type == PT_DATA_APPLICATION;
            }
            if (application) {
                auto* ah = HDR_DATA_APPLICATION(p);
                if (ah->payload_size() <= MAX_LENGTH_PAYLOAD)
                    wire = hexify(ah->payload_msg, ah->payload_size());
            }
            uid = ch->uid(); bits = ch->size()*8; packet_type = ch->ptype();
            hop = HDR_MAC(p)->macDA(); transmitter = HDR_MAC(p)->macSA();
            pt = ph->Pt;
            pr = receiving ? ph->Pr : 0;
            pn = receiving ? ph->Pn : 0;
            pi = receiving ? ph->Pi : 0;
            duration = ph->duration; txtime = ph->txtime;
            rxtime = receiving ? ph->rxtime : 0;
        }
    };
    static void number(double value) {
        if (std::isfinite(value)) std::cout << value; else std::cout << "null";
    }
    void report(const char* event, const Observation& o, const char* outcome) {
        std::cout << std::setprecision(15) << "{\"event\":\"phy_"
            << (o.application ? "" : "control_") << event << "\",\"time\":"
            << Scheduler::instance().clock() << ",\"node\":" << node_id_
            << ",\"duration_s\":" << o.duration << ",\"outcome\":\"" << outcome
            << "\",\"snr_db\":";
        if (o.receiving && o.pn > 0 && o.pr > 0) number(10*std::log10(o.pr/o.pn));
        else std::cout << "null";
        std::cout << ",\"pt\":"; number(o.pt);
        std::cout << ",\"pr\":"; if (o.receiving) number(o.pr); else std::cout << "null";
        std::cout << ",\"pn\":"; if (o.receiving) number(o.pn); else std::cout << "null";
        std::cout << ",\"pi\":"; if (o.receiving) number(o.pi); else std::cout << "null";
        std::cout << ",\"phy_bits\":" << o.bits << ",\"packet_type\":" << o.packet_type
            << ",\"ns_uid\":" << o.uid << ",\"phy_tx_time\":"; number(o.txtime);
        std::cout << ",\"phy_rx_time\":"; if (o.receiving) number(o.rxtime); else std::cout << "null";
        std::cout << ",\"rx_snr_penalty_db\":" << RxSnrPenalty_dB_
            << ",\"phy_patch_id\":\"" << patchId() << "\""
            << ",\"transmitter_mac\":" << o.transmitter << ",\"next_hop_mac\":" << o.hop;
        if (o.application) std::cout << ",\"wire_hex\":\"" << o.wire << "\"";
        if (std::strcmp(event, "rx_end") == 0) {
            std::cout << ",\"positive_interference\":" << (o.pi > 0 ? "true" : "false");
            if (conditional_probability_ >= 0)
                std::cout << ",\"conditional_interference_per\":" << conditional_probability_;
        }
        std::cout << "}" << std::endl;
    }
protected:
    double conditional_probability_ = -1;
    virtual const char* patchId() const { return "upstream"; }
    virtual void receiveDecision(Packet* p) { UnderwaterMPhyBpsk::endRx(p); }
    void startTx(Packet* p) override {
        report("tx_start", Observation(p, false), "transmitting");
        UnderwaterMPhyBpsk::startTx(p);
    }
    void endTx(Packet* p) override {
        report("tx_end", Observation(p, false), "transmitted");
        UnderwaterMPhyBpsk::endTx(p);
    }
    void startRx(Packet* p) override {
        Observation o(p);
        bool busy_tx = txPending, busy_rx = PktRx != nullptr;
        bool wrong_modulation = HDR_MPHY(p)->modulationType != modid;
        UnderwaterMPhyBpsk::startRx(p);
        const char* outcome = PktRx == p ? "synchronized" :
            busy_tx ? "transmitter_busy" : busy_rx ? "receiver_busy_overlap" :
            wrong_modulation ? "wrong_modulation" : "below_acquisition_threshold";
        report("rx_start", o, outcome);
    }
    void endRx(Packet* p) override {
        Observation o(p);
        bool synchronized = PktRx == p;
        int noise = getErrorPktsNoise(), interference = getErrorPktsInterf();
        conditional_probability_ = -1;
        receiveDecision(p); // may free p; report only saved values
        report("rx_end", o, !synchronized ? "not_synchronized" :
            getErrorPktsNoise() > noise ? "noise_error" :
            getErrorPktsInterf() > interference ? "interference_error" : "decoded");
    }
public:
    HoloPhy() { bind("node_id_", &node_id_); }
};
static class HoloPhyClass : public TclClass {
public:
    HoloPhyClass() : TclClass("Module/MPhy/BPSK/Underwater/HOLO") {}
    TclObject* create(int, const char*const*) override { return new HoloPhy; }
} class_holo_phy;

class HoloCorrectedPhy : public HoloPhy {
protected:
    const char* patchId() const override { return "conditional-bpsk-v1"; }
    void receiveDecision(Packet* p) override {
        if (PktRx != p) { dropPacket(p); return; }
        auto* ch = HDR_CMN(p);
        auto* ph = HDR_MPHY(p);
        const int bits = ch->size()*8;
        const double noise_per = getPER(ph->Pr/ph->Pn, bits);
        const double noise_ber = getPER(ph->Pr/ph->Pn, 1);
        double log_ratio = 0;
        bool positive_interference = false;
        if (interference_) {
            const PowerChunkList& chunks = interference_->getInterferencePowerChunkList(p);
            double remaining = ph->duration;
            for (const auto& chunk : chunks) {
                const double duration = std::min(remaining, std::max(0.0, chunk.second));
                remaining -= duration;
                if (chunk.first > 0 && duration > 0) {
                    positive_interference = true;
                    log_ratio += holo_bpsk::log_success_ratio(noise_ber,
                        getPER(ph->Pr/(ph->Pn+chunk.first), 1), bits*duration/ph->duration);
                }
            }
        } else if (ph->Pi > 0) {
            positive_interference = true;
            log_ratio = holo_bpsk::log_success_ratio(noise_ber,
                getPER(ph->Pr/(ph->Pn+ph->Pi), 1), bits);
        }
        conditional_probability_ = holo_bpsk::conditional_error(log_ratio);
        const bool noise_error = RNG::defaultrng()->uniform_double() < noise_per;
        const bool interference_error = !noise_error && positive_interference
            && conditional_probability_ > 0
            && RNG::defaultrng()->uniform_double() < conditional_probability_;
        ch->error() = noise_error || interference_error;
        if (noise_error) incrErrorPktsNoise();
        else if (interference_error) incrErrorPktsInterf();
        sendUp(p);
        PktRx = nullptr;
    }
};
static class HoloCorrectedPhyClass : public TclClass {
public:
    HoloCorrectedPhyClass() : TclClass("Module/MPhy/BPSK/Underwater/HOLO/Corrected") {}
    TclObject* create(int, const char*const*) override { return new HoloCorrectedPhy; }
} class_holo_corrected_phy;

extern "C" int Holobridge_Init(Tcl_Interp*) { return TCL_OK; }
