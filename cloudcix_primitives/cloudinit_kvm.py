"""
Primitive for Cloud-init VM on KVM hosts
"""

# stdlib
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
# local
from .controllers import KVMInterface
from cloudcix_primitives.utils import (
    SSHCommsWrapper,
    HostErrorFormatter,
)

__all__ = [
    'build',
]

SUCCESS_CODE = 0


def build(
        cloudimage: str,
        cpu: int,
        domain: str,
        domain_path: str,
        gateway_interface: dict,
        host: str,
        primary_storage: str,
        ram: int,
        size: int,
        secondary_interfaces=None,
        secondary_storages=None,
        osvariant='generic',
) -> Tuple[bool, str]:
    """
    description:
        1. Copies <cloudimage> to the given <domain_path><storage>
        2. Resizes the storage file to <size>
        3. Creates a Cloud-init VM

    parameters:
        cloudimage:
            description: The path to the cloud image file that will be copied to the domain directory.
            type: string
            required: true
        cpu:
            description: CPU property of the KVM VM
            type: integer
            required: true
        domain:
            description: Unique identification name for the Cloud-init VM on the KVM Host.
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage image will be created
            type: string
            required: true
        gateway_interface:
            description: |
                The gateway interface of the domain connected to the gateway network
                gateway_interface = {
                    'mac_address': 'aa:bb:cc:dd:ee:f0',
                    'vlan_bridge': 'br1000',
                }
            type: dictionary
            required: true
            properties:
                mac_address:
                    description: mac_address of the interface
                    type: string
                    required: true
                vlan_bridge:
                    description: name of the vlan bridge to which the gateway interface is connected to
                    type: string
                    required: true
        host:
            description: The dns or ipadddress of the Host on which this storage image will be created
            type: string
            required: true
        primary_storage:
            description: |
                The storage on which domain operating system is installed
                It must be an unique name used to create the storage image file on the host.
                eg '123_45_HDD_578.img'
            type: string
            required: true
        ram:
            description: RAM property of the KVM VM, must be in MBs
            type: integer
            required: true
        size:
            description: The size of the storage image to be created, must be in GB value
            type: integer
            required: true
        secondary_storages:
            description: |
                The list of all secondary storages that are attached to domain
                the names of storages must be unique.
                e.g secondary_storages = ['564_45_HDD_909.img',]
            type: array
            required: false
            items:
                type: string
        secondary_interfaces:
            description: |
                List of all other interfaces of the domain
                secondary_interfaces = [{
                    'mac_address': 'aa:bb:cc:dd:ee:f0',
                    'vlan_bridge': 'br1004',
                },]
            type: array
            required: false
            items:
                type: dictionary
                properties:
                    mac_address:
                        description: mac_address of the interface
                        type: string
                        required: true
                    vlan_bridge:
                        description: name of the vlan bridge to which the interface is connected to
                        type: integer
                        required: true
        osvariant:
            description: |
                specifies the type of operating system (OS) the virtual machine will run.
                Defaults to generic, generic is used when there isn’t a specific OS variant in mind or
                when the OS is not recognized by the system.
                e.g 'ubuntu24.04', 'rhel9.0'
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully created domain {domain} on Host {host}.',
        3011: f'Gateway interface cannot be None.',
        3012: f'Failed to Validate Gateway interface {gateway_interface}.',
        3013: f'Failed to Validate Secondary interfaces {secondary_interfaces}.',
        3021: f'Failed to connect the Host {host} for payload copy_cloudimage',
        3022: f'Failed to copy cloud image {cloudimage} to the domain directory {domain_path}{primary_storage}'
              f' on Host {host}.',
        3023: f'Failed to connect the Host {host} for payload resize_copied_file',
        3024: f'Failed to resize the copied storage image to {size}GB on Host {host}.',
        3025: f'Failed to connect the Host {host} for payload virt_install_cmd',
        3026: f'Failed to create domain {domain} on Host {host}.'
    }

    messages_list = []
    validated = True

    # validate gateway_interface
    if gateway_interface is None:
        return False, f'3011: {messages[3011]}'

    controller = KVMInterface(gateway_interface)
    success, errs = controller()
    if success is False:
        validated = False
        messages_list.append(f'3012: {messages[3012]} {";".join(errs)}')

    # validate secondary interfaces
    if secondary_interfaces is not None:
        errors = []
        valid_interface = True
        for interface in secondary_interfaces:
            controller = KVMInterface(interface)
            success, errs = controller()
            if success is False:
                valid_interface = False
                errors.extend(errs)
        if valid_interface is False:
            validated = False
            messages_list.append(f'3013: {messages[3013]} {";".join(errors)}')

    if validated is False:
        return False, '; '.join(messages_list)

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        #  define virt install payload
        cmd = 'virt-install '
        # When KVM host reboots, then VM starts if it was running before KVM host was rebooted
        cmd += '--autostart '
        # To view the VM via Virt Manager
        cmd += '--graphics vnc '
        # To boot as UEFI, a modern firmware interface
        cmd += '--boot uefi '
        # To import an existing disk image(cloud image),for Non .ISO installations
        cmd += '--import '
        # To avoid waiting forever until VM completes installation and reboots, usually VM doesn't reboot so
        # without this option, command hangs forever
        cmd += '--noautoconsole '
        # cloudinit datasource
        cmd += '--sysinfo smbios,system.product=CloudCIX '
        # name
        cmd += f'--name {domain} '
        # ram
        cmd += f'--memory {ram} '
        # cpu
        cmd += f'--vcpus {cpu} '
        # os variant
        cmd += f'--os-variant {osvariant} '
        # primary storage
        cmd += f'--disk path="{domain_path}{primary_storage},device=disk,bus=virtio" '
        # secondary storages
        for storage in secondary_storages:
            cmd += f'--disk path="{domain_path}{storage},device=disk,bus=virtio" '
        # gateway interface
        cmd += f'--network bridge={gateway_interface["vlan_bridge"]},'
        cmd += f'model=virtio,mac={gateway_interface["mac_address"]} '
        # secondary interface
        for interface in secondary_interfaces:
            cmd += f'--network bridge={interface["vlan_bridge"]},model=virtio,mac={interface["mac_address"]}'

        payloads = {
            'copy_cloudimage': f'cp {cloudimage} {domain_path}{primary_storage}',
            'resize_copied_file': f'qemu-img resize {domain_path}{primary_storage} {size}G',
            'virt_install_cmd': cmd,
        }

        ret = rcc.run(payloads['copy_cloudimage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix+1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('copy_cloudimage', ret)

        ret = rcc.run(payloads['resize_copied_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix+3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('resize_copied_file', ret)

        ret = rcc.run(payloads['virt_install_cmd'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix+5}: {messages[prefix + 5]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+6}: {messages[prefix + 6]}'), fmt.successful_payloads
        fmt.add_successful('virt_install_cmd', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def read(
        domain: str,
        host: str,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description: Gets the vm information

    parameters:
        domain:
            description: Unique identification name for the Cloud-init VM on the KVM Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which this storage image will be created
            type: string
            required: true
    return:
        description: |
            A list with 3 items: (1) a boolean status flag indicating if the
            read was successful, (2) a dict containing the data as read from
            the both machine's current state and (3) the list of debug and or error messages.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              file contents retrieved from Host. May be None if nothing
              could be retrieved.
            properties:
              <host>:
                description: read output data from machine <host>
                  type: string
          messages:
            description: list of errors and debug messages collected before failure occurred
            type: array
            items:
              <message>:
                description: exact message of the step, either debug, info or error type
                type: string
    """
    # Define message
    messages = {
        1200: f'Successfully read xml data of domain {domain} from host {host}',
        3221: f'Failed to connect to the host {host} for payload domain_info',
        3222: f'Failed to read data of domain {domain} from host {host}',
    }

    # set the outputs
    data_dict = {}
    message_list = []

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_domain_info': f'virsh dominfo {domain} ',
        }

        ret = rcc.run(payloads['read_domain_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            # Load the domain info(in XML) into dict
            data_dict[host] = ret["payload_message"].strip()
            fmt.add_successful('read_domain_info', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3220, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [f'1200: {messages[1200]}']
