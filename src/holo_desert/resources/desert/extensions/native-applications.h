// Observational subclasses: native DESERT timers and packet generation remain unchanged.
#include <uwcbr-module.h>
#include <uwvbr-module.h>

struct HoloNativeHeader {
    int flow, source, serial, bytes;
    double creation;
    static int offset;
    static HoloNativeHeader* get(const Packet* p) {
        return reinterpret_cast<HoloNativeHeader*>(p->access(offset));
    }
};
int HoloNativeHeader::offset;
static class HoloNativeHeaderClass : public PacketHeaderClass {
public:
    HoloNativeHeaderClass():PacketHeaderClass("PacketHeader/HoloNative",sizeof(HoloNativeHeader)) {
        this->bind();
        bind_offset(&HoloNativeHeader::offset);
    }
} class_holo_native_header;

static bool nativeApplicationType(packet_t type) { return type==PT_UWCBR || type==PT_UWVBR; }
static std::string nativePacketId(const Packet* p) {
    auto* h=HoloNativeHeader::get(p);
    return "native:"+std::to_string(h->flow)+":"+std::to_string(h->source)+":"+std::to_string(h->serial);
}

template<class Base> class HoloNativeApplication : public Base {
    int node_=0, flow_=0, serial_=0;
    const char* generator_;
    void report(const char* event,const HoloNativeHeader& h,int uid,int destination) {
        std::cout<<std::setprecision(15)<<"{\"event\":\"native_app_"<<event
            <<"\",\"time\":"<<Scheduler::instance().clock()<<",\"node\":"<<node_
            <<",\"flow_index\":"<<h.flow<<",\"native_packet_id\":\"native:"<<h.flow<<":"<<h.source<<":"<<h.serial
            <<"\",\"source_address\":"<<h.source<<",\"destination_address\":"<<destination
            <<",\"creation_time\":"<<h.creation<<",\"packet_bytes\":"<<h.bytes
            <<",\"ns_uid\":"<<uid<<",\"generator\":\""<<generator_<<"\"}"<<std::endl;
    }
protected:
    void initPkt(Packet* p) override {
        Base::initPkt(p);
        if(HDR_CMN(p)->ptype()==PT_UWVBR)HDR_UWCBR(p)->sn()=HDR_UWVBR(p)->sn();
        auto* h=HoloNativeHeader::get(p);
        *h={flow_,node_,++serial_,HDR_CMN(p)->size(),HDR_CMN(p)->timestamp()};
        report("tx",*h,HDR_CMN(p)->uid(),HDR_UWIP(p)->daddr());
    }
public:
    HoloNativeApplication(const char* generator):Base(),generator_(generator) {
        this->bind("holo_node_",&node_);this->bind("holo_flow_",&flow_);
    }
    void recv(Packet* p) override {
        const auto h=*HoloNativeHeader::get(p);
        int uid=HDR_CMN(p)->uid(),dst=HDR_UWIP(p)->daddr(),before=this->pkts_recv;
        Base::recv(p);
        if(this->pkts_recv>before)report("rx",h,uid,dst);
    }
};
static class HoloCbrClass : public TclClass {
public:
    HoloCbrClass():TclClass("Module/UW/CBR/HOLO"){}
    TclObject* create(int,const char*const*)override{return new HoloNativeApplication<UwCbrModule>("desert_cbr");}
} class_holo_cbr;
static class HoloVbrClass : public TclClass {
public:
    HoloVbrClass():TclClass("Module/UW/VBR/HOLO"){}
    TclObject* create(int,const char*const*)override{return new HoloNativeApplication<UwVbrModule>("desert_vbr");}
} class_holo_vbr;
