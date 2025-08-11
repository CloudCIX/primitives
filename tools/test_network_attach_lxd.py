import sys
import json

from cloudcix_primitives import network_attach_lxd

def usage():
    print("usage:")
    print("  test_network_secondary.py build <endpoint_url> <project> <instance_name> <vlan_id> <device_name> <instance_type> [mac_address] [verify_lxd_certs]")
    print("  test_network_secondary.py read <endpoint_url> <project> <instance_name> <instance_type> [verify_lxd_certs]")
    print("  test_network_secondary.py scrub <endpoint_url> <project> <instance_name> <device_name> <instance_type> [verify_lxd_certs]")
    print()
    print("examples:")
    print("  test_network_secondary.py build https://127.0.0.1:8443 myproject mycontainer 1002 eth1 containers 00:16:3e:aa:bb:cc false")
    print("  test_network_secondary.py read https://127.0.0.1:8443 myproject mycontainer containers false")
    print("  test_network_secondary.py scrub https://127.0.0.1:8443 myproject mycontainer eth1 containers false")

def to_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd not in ("build", "read", "scrub"):
        usage()
        sys.exit(1)

    endpoint_url = None
    project = None
    instance_name = None
    vlan_id = None
    device_name = None
    instance_type = None
    mac_address = None
    verify_lxd_certs = False

    if cmd == "build":
        if len(sys.argv) < 8:
            usage()
            sys.exit(2)
        endpoint_url = sys.argv[2]
        project = sys.argv[3]
        instance_name = sys.argv[4]
        vlan_id = sys.argv[5]
        device_name = sys.argv[6]
        instance_type = sys.argv[7]
        if len(sys.argv) > 8:
            mac_address = sys.argv[8]
        if len(sys.argv) > 9:
            verify_lxd_certs = to_bool(sys.argv[9], False)
        status, msg = network_attach_lxd.build(
            endpoint_url=endpoint_url,
            project=project,
            instance_name=instance_name,
            vlan_id=vlan_id,
            device_name=device_name,
            instance_type=instance_type,
            mac_address=mac_address,
            verify_lxd_certs=verify_lxd_certs,
        )
    elif cmd == "read":
        if len(sys.argv) < 6:
            usage()
            sys.exit(2)
        endpoint_url = sys.argv[2]
        project = sys.argv[3]
        instance_name = sys.argv[4]
        instance_type = sys.argv[5]
        if len(sys.argv) > 6:
            verify_lxd_certs = to_bool(sys.argv[6], False)
        status, data, msg = network_attach_lxd.read(
            endpoint_url=endpoint_url,
            project=project,
            instance_name=instance_name,
            instance_type=instance_type,
            verify_lxd_certs=verify_lxd_certs,
        )
    elif cmd == "scrub":
        if len(sys.argv) < 7:
            usage()
            sys.exit(2)
        endpoint_url = sys.argv[2]
        project = sys.argv[3]
        instance_name = sys.argv[4]
        device_name = sys.argv[5]
        instance_type = sys.argv[6]
        if len(sys.argv) > 7:
            verify_lxd_certs = to_bool(sys.argv[7], False)
        status, msg = network_attach_lxd.scrub(
            endpoint_url=endpoint_url,
            project=project,
            instance_name=instance_name,
            device_name=device_name,
            instance_type=instance_type,
            verify_lxd_certs=verify_lxd_certs,
        )
    else:
        usage()
        sys.exit(3)

    print(f"Status: {status}")
    print()
    print("Message:")
    if isinstance(msg, list):
        for m in msg:
            print(m)
    else:
        print(msg if msg is not None else "")

    if cmd == "read" and 'data' in locals() and data is not None:
        print()
        print("Data:")
        try:
            print(json.dumps(data, indent=2, sort_keys=True))
        except Exception:
            print(str(data))

if __name__ == "__main__":
	main()
