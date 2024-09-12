# Primitives

## directorymain
Primitive to Build and Delete directories on PodNet HA

supported verbs:

- build:
    - path: str
    - config_file=None

- read:
    - path: str
    - config_file=None
    
- scrub:
    - path: str
    - config_file=None
    
## firewallns
Primitive to Build and Delete nftables tables of Network Namespace on PodNet HA

supported verbs:

- build:
    - namespace: str
    - table: str
    - priority: int
    - config_file=None
    - rules: optional array
        - version: int
          source: array
            - str
          destination: array
            - str
          protocol: str
          port: array
            - str
          action: bool
          log: bool
          iiface: str
          oiface: str
          order: int
    - nats: dict
        dnats: optional array
            - public: str
              private: str
              iiface: str
        snats: optional array
            - public: str
              private: str
              oiface: str            

## storage_kvm
Primitive for Storage drives (QEMU images) on KVM hosts
    - host: str
    - domain_path: str
    - storage: str
    - size: int

- read:
    - host: str
    - domain_path: str
    - storage: str
    
- scrub:
    - host: str
    - domain_path: str
    - storage: str

- update:
    - host: str
    - domain_path: str
    - storage: str
    - size: int

