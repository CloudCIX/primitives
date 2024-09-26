"""
Primitive for Cloud-init VM on KVM hosts
"""

# stdlib
from typing import Tuple
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
) -> Tuple[bool, str]:
    """
    description:
        Copies <cloudimage> to the given <domain_path><storage> and resizes the storage file to <size>.

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

    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created domain {domain} on Host {host}.',
        3011: f'3011: Gateway interface cannot be None.',
        3012: f'3012: Failed to Validate Gateway interface {gateway_interface}.',
        3013: f'3013: Failed to Validate Secondary interfaces {secondary_interfaces}.',
        3021: f'3021: Failed to connect the Host {host} for payload copy_cloudimage',
        3022: f'3022: Failed to copy cloud image {cloudimage} to the domain directory {domain_path}{primary_storage}'
              f' on Host {host}.',
        3023: f'3023: Failed to connect the Host {host} for payload resize_copied_file',
        3024: f'3024: Failed to resize the copied storage image to {size}GB on Host {host}.',
        3025: f'3025: Failed to connect the Host {host} for payload virt_install_cmd',
        3026: f'3026: Failed to create domain {domain} on Host {host}.'
    }

    messages_list = []
    validated = True

    # validate gateway_interface
    if gateway_interface is None:
        return False, messages[3011]

    controller = KVMInterface(gateway_interface)
    success, errs = controller()
    if success is False:
        validated = False
        messages_list.append(f'{messages[3012]} {";".join(errs)}')

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
            messages_list.append(f'{messages[3013]} {";".join(errors)}')

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
        cmd = f'virt-install --autostart --graphics vnc --os-variant generic --boot uefi'
        # cloudinit datasource
        cmd += f'--sysinfo smbios,system.product=CloudCIX '
        # name
        cmd += f'--name {domain} '
        # ram
        cmd += f'--memory {ram} '
        # cpu
        cmd += f'--vcpus {cpu} '
        # primary storage
        cmd += f'--disk path="{domain_path}{primary_storage},device=disk,bus=virtio"'
        # secondary storages
        for storage in secondary_storages:
            cmd += f'--disk path="{domain_path}{storage},device=disk,bus=virtio"'
        # gateway interface
        cmd += f'--network bridge={gateway_interface["vlan_bridge"]},model=virtio,mac={gateway_interface["mac_address"]}'
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
            return False, fmt.channel_error(ret, messages[prefix + 1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 2]), fmt.successful_payloads
        fmt.add_successful('copy_cloudimage', ret)

        ret = rcc.run(payloads['resize_copied_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 4]), fmt.successful_payloads
        fmt.add_successful('resize_copied_file', ret)

        ret = rcc.run(payloads['virt_install_cmd'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix + 5]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, messages[prefix + 6]), fmt.successful_payloads
        fmt.add_successful('virt_install_cmd', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]
