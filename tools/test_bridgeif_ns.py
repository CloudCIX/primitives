import sys
import json
from cloudcix_primitives import bridgeif_ns
# Create namespace with ns.py build verb
# At the moment manually create global bridge

# Fetch command and arguments
cmd = sys.argv[1] if len(sys.argv) > 1 else None
bridgename = "testbridge"
namespace_name = "testns"
config_file = "/etc/cloudcix/pod/configs/config.json"

if len(sys.argv) > 2:
    bridgename = sys.argv[2]
if len(sys.argv) > 3:
    namespace_name = sys.argv[3]

status = None
msg = None
data = None

# Check and execute command
if cmd == 'build':
    status, msg = bridgeif_ns.build(bridgename, namespace_name, config_file)
elif cmd == 'read':
    status, data, msg = bridgeif_ns.read(bridgename, namespace_name, config_file)
elif cmd == 'scrub':
    status, msg = bridgeif_ns.scrub(bridgename, namespace_name, config_file)
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
