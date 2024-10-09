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
    - config_file: optional str
    - chains: optional dict
      - prerouting: optional dict
        - priority: int
        - policy: string
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
      - input: optional dict, dict object same as prerouting
      - forward: optional dict, dict object same as prerouting
      - output: optional dict, dict object same as prerouting
      - postrouting: optional dict, dict object same as prerouting
    - nats: optional dict
        - prerouting: optional dict
          - priority: int
          - policy: optional string
          - rules: optional array        
            - public: str
              private: str
              iiface: str
        - postrouting: optional array
          - priority: int
          - policy: optional string
          - rules: optional array 
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

## cloudinit_kvm
Primitive for Cloud-init VM on KVM hosts

supported verbs:

- build:
    - cloudimage: str
    - cpu: int
    - domain: str
    - domain_path: str
    - gateway_interface: dict
    - host: str
    - primary_storage: str
    - ram: int
    - size: int
    - secondary_interfaces: optional list
    - secondary_storages: optional list

- read:
    - domain: str
    - host: str

- quiesce:
    - domain: str
    - host: str

- restart:
    - domain: str
    - host: str

- scrub:
    - domain: str
    - domain_path: str
    - host: str
    - primary_storage: str
