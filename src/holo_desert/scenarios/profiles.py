"""Communication profiles reuse the atomic, revisioned YAML store."""
import re
from .library import ScenarioLibrary
from .network import CommunicationProfile, Network
from ..resources.docker.stack_builder import MACS, catalog


class ProfileLibrary(ScenarioLibrary):
    PREFIX='profile_'
    ID=re.compile(r'profile_[0-9a-f]{32}\Z')
    MODEL=CommunicationProfile

    @staticmethod
    def public(record):
        return {**record['configuration'],'id':record['id'],'revision':record['revision'],'kind':'user'}


def builtin_profiles():
    # Values are bridge profiles; metadata separately records upstream defaults.
    result=[]
    for protocol in MACS:
        if not any(m['id']==protocol and m['operational'] for m in catalog()['modules']):continue
        config=Network().model_dump();config['mac']['protocol']=protocol
        result.append({'id':'builtin_'+protocol,'kind':'example','name':protocol.upper().replace('_','-'),
                       'description':'Profilo acustico '+protocol,'network':config})
    for identifier,name,network in [
        ('flooding','Flooding con TDMA',Network(mac={'protocol':'tdma'},routing='flooding')),
        ('bpsk_corrected','BPSK corretto sperimentale',Network(acoustic={'phy':'bpsk_corrected'}))]:
        result.append({'id':'builtin_'+identifier,'kind':'example','name':name,
                       'description':'Configurazione verificata; applicazione soggetta ai vincoli dello scenario.',
                       'network':network.model_dump()})
    return result
