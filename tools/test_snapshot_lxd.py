import json
import sys

from cloudcix_primitives import snapshot_lxd

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns` to ensure the name space we want exists
# * `tools/test_vlanif_ns.py build {vlan}` to ensure vlan tagged interface exists on podnet
# * `tools/test_bridge_lxd.py build br4000` to ensure the LXD bridge exists to connect to the vlan tagged interface
# * `tools/test_lxd.py build` to ensure the LXD instance exists to create snapshots for

cmd = sys.argv[1] if len(sys.argv) > 1 else None

endpoint_url = None
project = 'mynetns'
instance_name = 'mynetns-1234'
snapshot_name = 'snap01'
instance_type = 'containers'
new_snapshot_name = None
stateful = False ##  NOTE: Stateful snapshots of containers require CRIU installation and migration.stateful = true in the container's config.
expires_at = None
verify_lxd_certs = False

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]

if len(sys.argv) > 3:
    snapshot_name = sys.argv[3]

if len(sys.argv) > 4:
    project = sys.argv[4]

if len(sys.argv) > 5:
    instance_name = sys.argv[5]

if endpoint_url is None:
    print('Endpoint URL is required, please supply the host as second argument.')
    sys.exit(1)

status = None
msg = None
data = None
successful_payloads = None

if cmd == 'build':
    # Optional parameters for build
    if len(sys.argv) > 6:
        stateful = sys.argv[6].lower() == 'true'
    if len(sys.argv) > 7 and sys.argv[7].lower() != 'none':
        expires_at = sys.argv[7]
    
    status, msg, successful_payloads = snapshot_lxd.build(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        snapshot_name=snapshot_name,
        instance_type=instance_type,
        stateful=stateful,
        expires_at=expires_at,
        verify_lxd_certs=verify_lxd_certs,
    )
elif cmd == 'read':
    status, data, msg = snapshot_lxd.read(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        snapshot_name=snapshot_name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
elif cmd == 'update':
    # Optional parameters for update
    if len(sys.argv) > 6 and sys.argv[6].lower() != 'none':
        new_snapshot_name = sys.argv[6]
    if len(sys.argv) > 7 and sys.argv[7].lower() != 'none':
        expires_at = sys.argv[7]
        
    status, msg, successful_payloads = snapshot_lxd.update(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        snapshot_name=snapshot_name,
        instance_type=instance_type,
        new_snapshot_name=new_snapshot_name,
        expires_at=expires_at,
        verify_lxd_certs=verify_lxd_certs,
    )
elif cmd == 'scrub':
    status, msg, successful_payloads = snapshot_lxd.scrub(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        snapshot_name=snapshot_name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
else:
    print("Usage:")
    print("  For build:  python3 test_snapshot_lxd.py build <endpoint_url> <snapshot_name> [project] [instance_name] [stateful] [expires_at]")
    print("  For read:   python3 test_snapshot_lxd.py read <endpoint_url> <snapshot_name> [project] [instance_name]")
    print("  For update: python3 test_snapshot_lxd.py update <endpoint_url> <snapshot_name> [project] [instance_name] [new_name] [expires_at]")
    print("  For scrub:  python3 test_snapshot_lxd.py scrub <endpoint_url> <snapshot_name> [project] [instance_name]")
    sys.exit(1)

print("Status:", status)
print()
print("Message:")
if isinstance(msg, list):
    for item in msg:
        print(item)
else:
    print(msg)

if data is not None:
    print()
    print("Data:")
    print(json.dumps(data, sort_keys=True, indent=4))

if successful_payloads is not None:
    print()
    print("Successful Payloads:")
    print(json.dumps(successful_payloads, sort_keys=True, indent=4, default=str))