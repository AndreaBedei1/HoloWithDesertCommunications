// SPDX-License-Identifier: MIT
// Passive lifecycle observation; reception decisions remain native.
#include <uwoptical-phy.h>
#include <uwoptical-mpropagation.h>
#include "uwem-phy-safe.h"

// Active right-handed Rz(yaw) Ry(pitch) Rx(roll), angles in radians.
struct HoloOpticalPose {double yaw=0,pitch=0,roll=0;};
struct HoloOpticalVector {double x,y,z;};
static HoloOpticalVector opticalRotate(HoloOpticalVector v,const HoloOpticalPose& p) {
    double y=v.y*std::cos(p.roll)-v.z*std::sin(p.roll), z=v.y*std::sin(p.roll)+v.z*std::cos(p.roll);
    double x=v.x*std::cos(p.pitch)+z*std::sin(p.pitch);z=-v.x*std::sin(p.pitch)+z*std::cos(p.pitch);
    return {x*std::cos(p.yaw)-y*std::sin(p.yaw),x*std::sin(p.yaw)+y*std::cos(p.yaw),z};
}
static std::map<Position*,HoloOpticalPose> holo_optical_pose;
class HoloOpticalPropagation : public UwOpticalMPropagation {
    double mount_yaw_=0,mount_pitch_=0,mount_roll_=0,offset_x_=0,offset_y_=0,offset_z_=0;
public:
    HoloOpticalPropagation() {
        bind("mount_yaw_",&mount_yaw_);bind("mount_pitch_",&mount_pitch_);bind("mount_roll_",&mount_roll_);
        bind("offset_x_",&offset_x_);bind("offset_y_",&offset_y_);bind("offset_z_",&offset_z_);
    }
    int command(int argc,const char*const* argv) override {
        if(argc==6 && std::strcmp(argv[1],"setHeading")==0) {
            auto* position=dynamic_cast<Position*>(TclObject::lookup(argv[2]));
            if(!position)return TCL_ERROR;
            HoloOpticalPose pose;double* angles[]={&pose.yaw,&pose.pitch,&pose.roll};
            for(int i=0;i<3;++i){char* end=nullptr;*angles[i]=std::strtod(argv[i+3],&end);if(*end || !std::isfinite(*angles[i]))return TCL_ERROR;}
            holo_optical_pose[position]=pose;return TCL_OK;
        }
        return UwOpticalMPropagation::command(argc,argv);
    }
    double getGain(Packet* p) override {
        auto* ph=HDR_MPHY(p);auto* tx=ph->srcPosition;auto* rx=ph->dstPosition;
        if(!tx || !rx)return 0;
        auto source=holo_optical_pose[tx],destination=holo_optical_pose[rx];
        // shortcut: offsets affect gain only; use native transducer Positions when delay/noise-depth offsets must be resolved.
        auto txoffset=opticalRotate({offset_x_,offset_y_,offset_z_},source);
        auto rxoffset=opticalRotate({offset_x_,offset_y_,offset_z_},destination);
        double dx=rx->getX()+rxoffset.x-tx->getX()-txoffset.x;
        double dy=rx->getY()+rxoffset.y-tx->getY()-txoffset.y;
        double dz=rx->getZ()+rxoffset.z-tx->getZ()-txoffset.z;
        double distance=std::sqrt(dx*dx+dy*dy+dz*dz);
        if(distance==0)return getLambertBeerGain(0,0);
        if(omnidirectional_)return getLambertBeerGain(distance,0);
        HoloOpticalPose mount;mount.yaw=mount_yaw_;mount.pitch=mount_pitch_;mount.roll=mount_roll_;
        auto forward=opticalRotate(opticalRotate({1,0,0},mount),source);
        double cosine=(dx*forward.x+dy*forward.y+dz*forward.z)/distance;
        if(cosine<=0)return 0;
        return getLambertBeerGain(distance,std::acos(std::min(1.,cosine)));
    }
};
static class HoloOpticalPropagationClass : public TclClass {
public:
    HoloOpticalPropagationClass():TclClass("Module/UW/OPTICAL/Propagation/HOLO"){}
    TclObject* create(int,const char*const*) override {return new HoloOpticalPropagation;}
} class_holo_optical_propagation;

template<class Base, bool Optical> class ObservedMediumPhy : public Base {
    int node_id_=0;
    static void number(double value) {if(std::isfinite(value))std::cout << value;else std::cout << "null";}
    void report(const char* event, Packet* p, bool receiving) {
        auto* ch=HDR_CMN(p);auto* ph=HDR_MPHY(p);
        std::cout << std::setprecision(15) << "{\"event\":\"phy_";
        if(ch->ptype()!=PT_DATA_APPLICATION && !nativeApplicationType(ch->ptype()))std::cout << "control_";
        std::cout << event << "\",\"time\":" << Scheduler::instance().clock()
            << ",\"node\":" << node_id_ << ",\"medium\":\"" << (Optical?"optical":"em")
            << "\",\"power_unit\":\"" << (Optical?"W":"dBm")
            << "\",\"received_power_unit\":\"" << (Optical?"W":"mW")
            << "\",\"phy_patch_id\":\"" << (Optical?"native-optical-lambert-beer-body-frame-v1":"em-power-lut-v1")
            << "\",\"ns_uid\":" << ch->uid() << ",\"phy_bits\":" << ch->size()*8
            << ",\"duration_s\":" << ph->duration << ",\"pt\":";number(Optical?ph->Pt:10*std::log10(ph->Pt));
        if(receiving){std::cout << ",\"pr\":";number(ph->Pr);if(Optical){std::cout << ",\"noise_unit\":\"A2\",\"pn\":";number(ph->Pn);}}
        if(ch->ptype()==PT_DATA_APPLICATION) {
            auto* ah=HDR_DATA_APPLICATION(p);
            if(ah->payload_size()<=MAX_LENGTH_PAYLOAD)std::cout << ",\"wire_hex\":\"" << hexify(ah->payload_msg,ah->payload_size()) << "\"";
        } else if(nativeApplicationType(ch->ptype()))std::cout << ",\"native_packet_id\":\"" << nativePacketId(p) << "\"";
        std::cout << "}" << std::endl;
    }
protected:
    void startTx(Packet* p) override { report("tx_start",p,false);Base::startTx(p); }
    void endTx(Packet* p) override { report("tx_end",p,false);Base::endTx(p); }
    void startRx(Packet* p) override { report("rx_start",p,true);Base::startRx(p); }
    void endRx(Packet* p) override { report("rx_end",p,true);Base::endRx(p); }
public:
    ObservedMediumPhy(){this->bind("node_id_",&node_id_);}
};
static class HoloOpticalPhyClass : public TclClass {
public:
    HoloOpticalPhyClass():TclClass("Module/UW/OPTICAL/PHY/HOLO"){}
    TclObject* create(int,const char*const*) override {return new ObservedMediumPhy<UwOpticalPhy,true>;}
} class_holo_optical_phy;
static class HoloEmPhyClass : public TclClass {
public:
    HoloEmPhyClass():TclClass("Module/UW/ElectroMagnetic/PHY/HOLO"){}
    TclObject* create(int,const char*const*) override {return new ObservedMediumPhy<HoloSafeElectroMagneticPhy,false>;}
} class_holo_em_phy;
