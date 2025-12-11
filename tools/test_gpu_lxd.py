"""
Test GPU LXD primitives
"""
# stdlib
import sys
# libs
from cloudcix_primitives import gpu_lxd

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns` to ensure the name space we want exists
# * `tools/test_vlanif_ns.py build {vlan}` to ensure vlan tagged interface exists on podnet
# * `tools/test_bridge_lxd.py build br4000` to ensure the LXD bridge exists to connect to the vlan tagged interface
# * `tools/test_lxd.py build` to ensure the LXD instance exists to attach GPU

cmd = sys.argv[1]

endpoint_url = None
project = 'default'
instance_name = 'test-instance'
instance_type = 'virtual-machine'
device_identifier = '0000:04:04.0'
device_name = 'gpu0'
verify_lxd_certs = False

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]

if len(sys.argv) > 3:
    project = sys.argv[3]

if len(sys.argv) > 4:
    instance_name = sys.argv[4]

if len(sys.argv) > 5:
    device_identifier = sys.argv[5]

if len(sys.argv) > 6:
    device_name = sys.argv[6]

if len(sys.argv) > 7:
    instance_type = sys.argv[7]

if endpoint_url is None:
    print('Endpoint URL is required, please supply the host as second argument.')
    exit()

if cmd == 'build':
    status, msg = gpu_lxd.build(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        device_identifier=device_identifier,
        device_name=device_name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
elif cmd == 'read':
    status, msg, gpu_details = gpu_lxd.read(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
    print("Status: %s" % status)
    print()
    print("Message:")
    print(msg)
    print()
    if gpu_details:
        print("GPU Details:")
        for name, details in gpu_details.items():
            print(f"  {name}: {details}")
    sys.exit(0)
elif cmd == 'scrub':
    status, msg = gpu_lxd.scrub(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        device_identifier=device_identifier,
        device_name=device_name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
else:
    print(f"Unknown command: {cmd}")
    sys.exit(1)

print("Status: %s" % status)
print()
print("Message:")
if type(msg) == list:
    for item in msg:
        print(item)
else:
    print(msg)