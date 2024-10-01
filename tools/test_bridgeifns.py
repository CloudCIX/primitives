amon@LAPTOP-J76M3340:~/work/cloudcix-work/primitives$ docker ps
CONTAINER ID   IMAGE     COMMAND       CREATED       STATUS       PORTS
     NAMES
a4523998db29   ubuntu    "/bin/bash"   13 days ago   Up 5 hours
     happy_shamir
amon@LAPTOP-J76M3340:~/work/cloudcix-work/primitives$ docker exec -it a
4 /bin/bash
(base) root@a4523998db29:/# ls
bin                home               mnt   sbin                usr
bin.usr-is-merged  lib                opt   sbin.usr-is-merged  var
boot               lib.usr-is-merged  proc  srv
dev                lib64              root  sys
etc                media              run   tmp
(base) root@a4523998db29:/# cd home/ubuntu/
.bash_logout  .bashrc       .profile      test/
(base) root@a4523998db29:/# cd home/ubuntu/test/
(base) root@a4523998db29:/home/ubuntu/test# ls
bridgeifns.py  primitives
(base) root@a4523998db29:/home/ubuntu/test# cd primitives/
(base) root@a4523998db29:/home/ubuntu/test/primitives# ls
DEVELOPMENT.md  README.md      cloudcix_primitives  setup.py
LICENSE         __pycache__    requirements.txt     test_bridgeifns.py
MANIFEST.in     bridgeifns.py  routens.py           tools
(base) root@a4523998db29:/home/ubuntu/test/primitives# vim test_bridgei
fns.py
(base) root@a4523998db29:/home/ubuntu/test/primitives# cat test_bridgei
fns.py
import sys
import json
from cloudcix_primitives import bridgeifns

# Fetch command and arguments
cmd = sys.argv[1] if len(sys.argv) > 1 else None
bridgename, namespace_name = "testbridge", "testns"

if len(sys.argv) > 2:
    bridgename = sys.argv[2]
if len(sys.argv) > 3:
    namespace_name = sys.argv[3]

status = None
msg = None
(base) root@a4523998db29:/home/ubuntu/test/primitives# python bridgeifn
s.py scrub frodo sam
(base) root@a4523998db29:/home/ubuntu/test/primitives# python bridgeifn
s.py read frodo sam
if len(sys.argv) > 2:
    bridgename = sys.argv[2]
if len(sys.argv) > 3:
    namespace_name = sys.argv[3]

status = None
msg = None
data = None

# Check and execute command
if cmd == 'build':
    status, msg = bridgeifns.build(bridgename, namespace_name, "/etc/cloudcix/pod/configs/config.json")
elif cmd == 'scrub':
    status, msg = bridgeifns.scrub(bridgename, namespace_name, "/etc/cloudcix/pod/configs/config.json")
elif cmd == 'read':
    status, data, msg = bridgeifns.read(bridgename, namespace_name,  "/etc/cloudcix/pod/configs/config.json")
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
