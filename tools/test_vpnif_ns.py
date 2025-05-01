#!/usr/bin/env python
"""
Test script for vpnif_ns primitive

# Test just the read function
python simple_vpnif_test.py --function read

# Test just the build function with a specific VPN ID
python simple_vpnif_test.py --function build --vpn-id 6000

# Test all functions with custom settings
python simple_vpnif_test.py --function all --host 192.168.1.10 --user admin --namespace custom_ns

"""
# Import modules
import subprocess
import sys
import time
import getpass
import random
import os
import tempfile
import atexit
import signal
import shutil
import argparse

def print_separator():
    """Print a line separator for better readability"""
    print("-" * 80)

class SSHKeyManager:
    """Manages SSH keys during the testing session to avoid repeated passphrase prompts"""
    def __init__(self):
        self.ssh_agent_proc = None
        self.temp_dir = None
        self.ssh_agent_sock = None
        self.key_added = False
        
    def start_ssh_agent(self):
        """Start an SSH agent for the session"""
        print("Starting SSH agent...")
        self.temp_dir = tempfile.mkdtemp()
        self.ssh_agent_sock = os.path.join(self.temp_dir, "ssh_agent.sock")
        
        # Start the SSH agent
        agent_cmd = ["ssh-agent", "-a", self.ssh_agent_sock]
        try:
            agent_output = subprocess.check_output(agent_cmd, universal_newlines=True)
            # Extract environment variables from ssh-agent output
            for line in agent_output.split("\n"):
                if "SSH_AGENT_PID" in line:
                    pid = line.split(";")[0].split("=")[1]
                    self.ssh_agent_proc = int(pid)
            
            # Set environment variables
            os.environ["SSH_AUTH_SOCK"] = self.ssh_agent_sock
            print("SSH agent started successfully")
            
            # Register cleanup function
            atexit.register(self.cleanup)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to start SSH agent: {e}")
            return False
    
    def add_key(self, key_path=None, max_attempts=3):
        """Add the SSH key to the agent with retry logic"""
        attempts = 0
        
        while attempts < max_attempts:
            # Default to id_rsa if no key provided
            if key_path is None:
                key_path = os.path.expanduser("~/.ssh/id_rsa")
            
            # Expand user path if it starts with ~
            if key_path.startswith('~'):
                key_path = os.path.expanduser(key_path)
            
            # Validate that the key file exists
            if not os.path.isfile(key_path):
                print(f"Key file not found: {key_path}")
                attempts += 1
                if attempts < max_attempts:
                    key_path = input("Please enter a valid path to your SSH private key: ")
                continue
            
            try:
                # Try to add the key
                subprocess.check_call(["ssh-add", key_path])
                self.key_added = True
                print(f"Successfully added SSH key {key_path} to agent")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Failed to add SSH key to agent: {e}")
                attempts += 1
                if attempts < max_attempts:
                    retry = input("Do you want to try again with a different key? (y/n): ")
                    if retry.lower() == 'y':
                        key_path = input("Enter path to your SSH private key: ")
                    else:
                        break
        
        print("Failed to add SSH key after multiple attempts. Continuing without SSH agent key.")
        return False
    
    def cleanup(self):
        """Clean up SSH agent and temporary files"""
        if self.ssh_agent_proc:
            try:
                os.kill(self.ssh_agent_proc, signal.SIGTERM)
                print("SSH agent terminated")
            except OSError as e:
                print(f"Error terminating SSH agent: {e}")
        
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print("Temporary directory removed")

def run_ssh_command(command, host, username="user1", timeout=30):
    """Run command via SSH which will prompt for passphrase"""
    ssh_cmd = ["ssh", "-o", f"ConnectTimeout={timeout}", f"{username}@{host}", command]
    print(f"Running: ssh {username}@{host} '{command}'")
    
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("Success!")
            print(f"Output:\n{result.stdout}")
            return True, result.stdout.strip()
        else:
            print("Failed!")
            print(f"Error:\n{result.stderr}")
            return False, result.stderr.strip()
    except Exception as e:
        print(f"Error executing command: {str(e)}")
        return False, str(e)

def check_host_connectivity(host, username, timeout=5):
    """Check if the host is reachable via SSH"""
    print(f"Checking connectivity to {host}...")
    command = "echo 'Connection test successful'"
    ssh_cmd = ["ssh", "-o", f"ConnectTimeout={timeout}", f"{username}@{host}", command]
    
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            print(f"✓ Successfully connected to {host}")
            return True
        else:
            print(f"✗ Failed to connect to {host}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Connection timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"✗ Error connecting to {host}: {str(e)}")
        return False

def get_network_interfaces(host, username, sudo_password, timeout=10):
    """Get available network interfaces on the target host"""
    print("\nDetecting available network interfaces on the target host...")
    command = f"echo '{sudo_password}' | sudo -S ip -o link show | grep -v '@' | grep -v lo: | grep -o '^[0-9]*: [^:]*' | awk '{{print $2}}'"
    success, output = run_ssh_command(command, host, username, timeout)
    
    if success and output:
        interfaces = [iface.replace(':', '').strip() for iface in output.strip().split('\n')]
        return interfaces
    else:
        print("Failed to get network interfaces")
        return []

def test_build(host, username, sudo_password, namespace, vpn_id, physical_dev, timeout):
    """Test the build function of vpnif_ns primitive"""
    print_separator()
    print("TESTING BUILD FUNCTION")
    print_separator()
    
    print(f"Using physical device: {physical_dev}")
    
    # Step 1: Check if interface exists
    print("\nStep 1: Checking if XFRM interface exists...")
    command = f"ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo 'Interface does not exist'"
    success, output = run_ssh_command(command, host, username, timeout)
    interface_exists = "Interface does not exist" not in output if success else False
    
    if interface_exists:
        print(f"XFRM interface xfrm{vpn_id} already exists in namespace {namespace}")
        print("Build will not recreate existing interface. Use scrub first if needed.")
        return True
    
    # Step 2: Create the interface if it doesn't exist
    # First check if interface exists in root namespace
    print("Checking if interface exists in root namespace...")
    command = f"echo '{sudo_password}' | sudo -S ip link show | grep xfrm{vpn_id} || echo 'Not found'"
    success, output = run_ssh_command(command, host, username, timeout)
    if "Not found" not in output:
        print(f"Warning: Interface xfrm{vpn_id} already exists in root namespace. Deleting it first...")
        command = f"echo '{sudo_password}' | sudo -S ip link delete xfrm{vpn_id}"
        run_ssh_command(command, host, username, timeout)
        time.sleep(1)  # Wait for deletion to complete

    print("\nStep 2: Creating XFRM interface...")
    print(f"Command: ip link add xfrm{vpn_id} type xfrm dev {physical_dev} if_id {vpn_id}")
    command = f"echo '{sudo_password}' | sudo -S ip link add xfrm{vpn_id} type xfrm dev {physical_dev} if_id {vpn_id}"
    success, output = run_ssh_command(command, host, username, timeout)
    if not success:
        print("Failed to create XFRM interface. Exiting test.")
        return False
        
    print("Disabling IPsec policy...")
    print(f"Command: sysctl -w net.ipv4.conf.xfrm{vpn_id}.disable_policy=1")
    command = f"echo '{sudo_password}' | sudo -S sysctl -w net.ipv4.conf.xfrm{vpn_id}.disable_policy=1"
    success, output = run_ssh_command(command, host, username, timeout)
    if not success:
        print("Failed to disable IPsec policy. Exiting test.")
        return False
        
    print("Moving interface to namespace...")
    print(f"Command: ip link set dev xfrm{vpn_id} netns {namespace}")
    command = f"echo '{sudo_password}' | sudo -S ip link set dev xfrm{vpn_id} netns {namespace}"
    success, output = run_ssh_command(command, host, username, timeout)
    if not success:
        print("Failed to move interface to namespace. Exiting test.")
        return False
        
    print("Bringing interface up...")
    print(f"Command: ip netns exec {namespace} ip link set dev xfrm{vpn_id} up")
    command = f"echo '{sudo_password}' | sudo -S ip netns exec {namespace} ip link set dev xfrm{vpn_id} up"
    success, output = run_ssh_command(command, host, username, timeout)
    if not success:
        print("Failed to bring interface up. Exiting test.")
        return False
        
    print("\nSuccessfully created and configured XFRM interface!")
    
    # Step 3: Verify the interface exists
    print("\nStep 3: Verifying interface...")
    command = f"echo '{sudo_password}' | sudo -S ip netns exec {namespace} ip link show xfrm{vpn_id}"
    success, output = run_ssh_command(command, host, username, timeout)
    if success and "xfrm" in output:
        print("Verification successful! XFRM interface exists.")
        print(f"Interface details:\n{output}")
        return True
    else:
        print("Verification failed. Interface not found.")
        return False

def test_read(host, username, sudo_password, namespace, vpn_id, timeout):
    """Test the read function of vpnif_ns primitive"""
    print_separator()
    print("TESTING READ FUNCTION")
    print_separator()
    
    print("\nChecking if XFRM interface exists in namespace...")
    print(f"Command: ip netns exec {namespace} ip link show xfrm{vpn_id}")
    command = f"echo '{sudo_password}' | sudo -S ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo 'Interface does not exist'"
    success, output = run_ssh_command(command, host, username, timeout)
    
    if success:
        if "Interface does not exist" in output:
            print(f"Interface xfrm{vpn_id} does not exist in namespace {namespace}")
            print("Read Status: Success (interface not found)")
            return True
        else:
            print(f"Interface xfrm{vpn_id} exists in namespace {namespace}")
            print("Interface details:")
            print(output)
            print("Read Status: Success (interface found)")
            return True
    else:
        print("Read operation failed")
        return False

def test_scrub(host, username, sudo_password, namespace, vpn_id, timeout):
    """Test the scrub function of vpnif_ns primitive"""
    print_separator()
    print("TESTING SCRUB FUNCTION")
    print_separator()
    
    # Check if interface exists before attempting to remove
    print("\nStep 1: Checking if interface exists...")
    print(f"Command: ip netns exec {namespace} ip link show xfrm{vpn_id}")
    command = f"echo '{sudo_password}' | sudo -S ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo 'Interface does not exist'"
    success, output = run_ssh_command(command, host, username, timeout)
    
    if success and "Interface does not exist" in output:
        print(f"Interface xfrm{vpn_id} does not exist in namespace {namespace}. Nothing to scrub.")
        print("Scrub Status: Success (no action needed)")
        return True
    else:
        print(f"Interface xfrm{vpn_id} exists. Removing it...")
        print(f"Command: ip netns exec {namespace} ip link delete dev xfrm{vpn_id}")
        command = f"echo '{sudo_password}' | sudo -S ip netns exec {namespace} ip link delete dev xfrm{vpn_id}"
        success, output = run_ssh_command(command, host, username, timeout)
        
        if success:
            # Verify removal
            command = f"echo '{sudo_password}' | sudo -S ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo 'Interface does not exist'"
            success, verify_output = run_ssh_command(command, host, username, timeout)
            
            if success and "Interface does not exist" in verify_output:
                print("Interface successfully removed!")
                print("Scrub Status: Success")
                return True
            else:
                print("Warning: Interface may still exist after removal attempt")
                print("Scrub Status: Failed")
                return False
        else:
            print("Failed to remove interface")
            print("Scrub Status: Failed")
            return False

def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Test the vpnif_ns primitive")
    parser.add_argument("--host", default="10.254.3.195", help="Target host IP address (default: 10.254.3.195)")
    parser.add_argument("--user", default="user1", help="SSH username (default: user1)")
    parser.add_argument("--namespace", default="ns1100", help="Namespace name (default: ns1100)")
    parser.add_argument("--physical-dev", help="Physical network device name (auto-detected if not specified)")
    parser.add_argument("--vpn-id", type=int, help="VPN ID (default: random number between 5000-9999)")
    parser.add_argument("--timeout", type=int, default=10, help="SSH connection timeout in seconds (default: 10)")
    parser.add_argument("--function", choices=["build", "read", "scrub", "all"], default="all", 
                      help="Function to test: build, read, scrub, or all (default: all)")
    args = parser.parse_args()
    
    # Use random VPN ID if not specified
    vpn_id = args.vpn_id if args.vpn_id else random.randint(5000, 9999)
    namespace = args.namespace
    host = args.host
    username = args.user
    timeout = args.timeout
    test_function = args.function
    
    print_separator()
    print(f"Testing vpnif_ns primitive with:")
    print(f"Host:      {host}")
    print(f"Username:  {username}")
    print(f"Namespace: {namespace}")
    print(f"VPN ID:    {vpn_id}")
    print(f"Function:  {test_function}")
    print_separator()
    
    # Set up SSH key management to avoid repeated passphrase prompts
    ssh_manager = SSHKeyManager()
    use_ssh_agent = input("Do you want to use SSH agent for key management to avoid repeated passphrase prompts? (y/n): ")
    if use_ssh_agent.lower() == 'y':
        if ssh_manager.start_ssh_agent():
            # Ask for SSH key path or use default
            custom_key_path = input("Enter path to your SSH private key or press Enter to use default (~/.ssh/id_rsa): ")
            key_path = custom_key_path if custom_key_path.strip() else None
            ssh_manager.add_key(key_path)
            print("You should now be able to SSH without entering your passphrase repeatedly.")
        else:
            print("Failed to set up SSH agent. Continuing without key management.")
    
    # Check host connectivity first
    if not check_host_connectivity(host, username, timeout):
        print("Cannot connect to the target host. Please check your network connection and host availability.")
        print("You may also want to verify the host address with: --host <ip-address>")
        return

    # Get sudo password from user
    sudo_password = getpass.getpass(f"Enter sudo password for {username} on {host}: ")

    # Get physical device if not specified
    physical_dev = args.physical_dev
    if not physical_dev:
        interfaces = get_network_interfaces(host, username, sudo_password, timeout)
        if interfaces:
            print("\nAvailable network interfaces:")
            for i, iface in enumerate(interfaces, 1):
                print(f"{i}. {iface}")
            
            try:
                choice = input("\nSelect physical device by number (or enter name directly): ")
                if choice.isdigit() and 1 <= int(choice) <= len(interfaces):
                    physical_dev = interfaces[int(choice) - 1]
                else:
                    physical_dev = choice.strip()
            except (ValueError, IndexError):
                physical_dev = "eno4"  # Default if selection fails
        else:
            physical_dev = "eno4"  # Default to eno4 if we couldn't get interfaces
            
    print(f"Using physical device: {physical_dev}")
    
    # Check if the namespace exists
    print("\nChecking if namespace exists...")
    command = f"sudo -S ip netns list | grep -w {namespace} || echo 'Namespace not found'"
    success, output = run_ssh_command(f"echo '{sudo_password}' | {command}", host, username, timeout)
    
    if "Namespace not found" in output:
        print(f"Namespace '{namespace}' does not exist. Creating it now...")
        command = f"echo '{sudo_password}' | sudo -S ip netns add {namespace}"
        success, output = run_ssh_command(command, host, username, timeout)
        if not success:
            print(f"Failed to create namespace '{namespace}'. Exiting test.")
            return
        print(f"Successfully created namespace '{namespace}'")

    # Store test results
    results = {}
    
    # Run the selected test function(s)
    if test_function == "build" or test_function == "all":
        results["build"] = test_build(host, username, sudo_password, namespace, vpn_id, physical_dev, timeout)
    
    if test_function == "read" or test_function == "all":
        results["read"] = test_read(host, username, sudo_password, namespace, vpn_id, timeout)
    
    if test_function == "scrub" or test_function == "all":
        results["scrub"] = test_scrub(host, username, sudo_password, namespace, vpn_id, timeout)
    
    # Ask if user wants to remove the namespace at the end
    if test_function == "all" or test_function == "scrub":
        response = input("\nDo you want to remove the namespace? (y/n): ")
        if response.lower() == 'y':
            print("Removing namespace...")
            command = f"echo '{sudo_password}' | sudo -S ip netns delete {namespace}"
            success, output = run_ssh_command(command, host, username, timeout)
            if success:
                print(f"Successfully removed namespace {namespace}")
            else:
                print(f"Warning: Failed to remove namespace {namespace}")
    
    # Print summary
    print_separator()
    print("TEST RESULTS SUMMARY:")
    for func, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"{func.upper()}: {status}")
    print_separator()
    print("Test completed!")

if __name__ == "__main__":
    main()