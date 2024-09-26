# Primitives

## directorymain
Primitive to Build and Delete directories on PodNet HA

supported verbs:

- build:
    - path: str
    - config_file: optional str

- read:
    - path: str
    - config_file: optional str
    
- scrub:
    - path: str
    - config_file: optional str
    
## firewallns
Primitive to Build and Delete nftables tables of Network Namespace on PodNet HA

supported verbs:

- build:
    - namespace: str
    - table: str
    - priority: int
    - config_file: optional str
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
    - nats: optional dict
        dnats: optional array
            - public: str
              private: str
              iiface: str
        snats: optional array
            - public: str
              private: str
              oiface: str
    - sets: optional array
        - name: str
          type: str
          elements: array
            - ip_address: str
                        
- read:
    - namespace: str
    - table: str
    - config_file: optional str

- scrub:
    - namespace: str
    - table: str
    - config_file: optional str

## storage_kvm
Primitive for Storage drives (QEMU images) on KVM hosts

supported verbs:

- build
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

