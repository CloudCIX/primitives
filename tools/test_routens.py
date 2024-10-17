import sys
import json
from cloudcix_primitives import routens

"""
Requirements

build ns -- python3 test_ns_primitive.py build maria
build bridgeifns -- python3 test_bridgeifns.py build frodo maria
build networkns -- python3 test_networkns_primitive.py build 'maria' '192.0.2.146' 'maria.frodo'

"""
# Fetch command and arguments
cmd = sys.argv[1] if len(sys.argv) > 1 else None
destination, gateway, namespace = "test_destination", "test_gateway", "testns"

if len(sys.argv) > 2:
    destination = sys.argv[2]
if len(sys.argv) > 3:
    gateway = sys.argv[3]
if len(sys.argv) > 4:
    namespace = sys.argv[4]

route = {'destination':destination , 'gateway': gateway}


status = None
msg = None
data = None

# Check and execute command
if cmd == 'build':
    status, msg = routens.build(namespace, route, "/etc/cloudcix/pod/configs/config.json")
elif cmd == 'scrub':
    status, msg = routens.scrub(namespace, route, "/etc/cloudcix/pod/configs/config.json")
elif cmd == 'read':
    status, data, msg = routens.read(namespace, route, "/etc/cloudcix/pod/configs/config.json")
else:
   print(f"Unknown command: {cmd}")
   sys.exit(1)

# Output the status and messages
print("Status: %s" % status)
print("\nMessage:")
if isinstance(msg, list):
    for item in msg:
        print(item)
else:
    print(msg)

# Output data if available
if data is not None:
    print("\nData:")
    print(json.dumps(data, sort_keys=True, indent=4))
