# Primitives

## bridge_podnet
Primitive for Building Public subnet bridge on PodNet using netplan service.

Supported verbs:

- head 
    - identifier: str
    - config_filepath=None
    
- build
    - address_range: str
    - identifier: str
    - config_filepath=None

## firewallns
Primitive for setup of Namepace Firewall on PodNet using nftable service.

Supported verbs:

- build_overwrite
    - namespace_identifier: str
    - config_filepath=None
    - firewall_rules=None
    - log=None
    - nat=None
    - namespace_pubif=None
    - namespace_pubif6=None

## network_namespace
Primitive for Namespace Network on PodNet.

Supported verbs:

- build
    - namespace_identifier: str
    - bridge_podnet_identifier=None
    - bridge6_podnet_identifier=None
    - config_filepath=None
    - ip4=None
    - ip6=None
    - namespace_networks=None

- scrub
    - namespace_identifier: str
    - config_filepath=None
 