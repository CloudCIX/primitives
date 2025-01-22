"""
Primitive for Virtual Machine on Windows hypervisor
"""
# stdlib
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import (
    HostErrorFormatter,
    hyperv_dictify,
    SSHCommsWrapper,
)

__all__ = [
    'build',
    'quiesce',
    'read',
    'restart',
    'scrub',
]

SUCCESS_CODE = 0


def build(
    image: str,
    cpu: int,
    domain: str,
    gateway_vlan: int,
    host: str,
    primary_storage: str,
    ram: int,
    robot_drive_url: str,
    size: int,
    domain_path=None,
    secondary_vlans=[],
) -> Tuple[bool, str]:
    """
        description:
        1. Copies <image> to the given <domain_path><primary_storage>
        2. Resizes the storage file to <size>
        3. Creates a HyperV VM

    parameters:
        image:
            description: The path to the image file that will be copied to the domain directory.
            type: string
            required: true
        cpu:
            description: CPU property of the HyperV VM
            type: integer
            required: true
        domain:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        domain_path:
            description: |
              The location or directory path where this storage image will be created
              eg. 'D:\\HyperV\\'
            type: string
            required: false
        gateway_vlan:
            description: |
                The gateway vlan of the domain connected to the gateway network
                gateway_interface = 1000
            type: integer
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        primary_storage:
            description: |
                The storage on which domain operating system is installed
                It must be an unique name used to create the storage image file on the host.
                eg '123_45_HDD_578.vhdx'
            type: string
            required: true
        ram:
            description: RAM property of the HyperV VM, must be in MBs
            type: integer
            required: true
        robot_drive_url:
            description: Robot Network Drive url to access image file, unattend and network xml files
            type: string
            required: true
        size:
            description: The size of the storage image to be created, must be in GB value
            type: integer
            required: true
        secondary_vlans:
            description: |
                List of all other vlans of the domain
                secondary_vlans = [1002,]
            type: array
            required: false
            items:
                type: integer
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # domain_path defaults to D:\\HyperV\\
    if domain_path is None:
        domain_path = f'D:\\HyperV\\'

    # Define message
    messages = {
        1000: f'Successfully created domain {domain} on Host {host}',
        # validations
        3011: 'Invalid "primary_storage", The "primary_storage" is required',
        3012: 'Invalid "primary_storage", The "primary_storage" must be a name of the storage file with extension',
        3013: 'Invalid "primary_storage", The "primary_storage" can only be either .vhd or .vhdx file formats',
        # payload execution
        3031: f'Failed to connect to the host {host} for the payload read_domain_info',
        3032: f'Failed to create domain, the requested domain {domain} already exists on the Host {host}',
        3033: f'Failed to connect the Host {host} for the payload copy_vhdx_image_file',
        3034: f'Failed to copy vhdx image file {image} to the domain directory {domain_path}{domain}\\{primary_storage}'
              f' on Host {host}.',
        3035: f'Failed to connect the Host {host} for the payload resize_primary_storage',
        3036: f'Failed to resize the primary storage image to {size}GB on Host {host}',
        3037: f'Failed to connect the Host {host} for the payload create_mount_dir',
        3038: f'Failed to create mount dir {domain_path}{domain}\\mount on Host {host}',
        3039: f'Failed to connect the Host {host} for the payload mount_primary_storage',
        3040: f'Failed to mount primary storage on Host {host}',
        3041: f'Failed to connect the Host {host} for the payload copy_unattend_file',
        3042: f'Failed to copy unattend file to {domain_path}{domain}\\mount\\ on Host {host}',
        3043: f'Failed to connect the Host {host} for the payload copy_network_file',
        3044: f'Failed to copy network file to {domain_path}{domain}\\mount\\ on Host {host}',
        3045: f'Failed to connect the Host {host} for the payload unmount_primary_storage',
        3046: f'Failed to unmount primary storage at {domain_path}{domain}\\mount on Host {host}',
        3047: f'Failed to connect the Host {host} for the payload delete_mount_dir',
        3048: f'Failed to delete mount dir {domain_path}{domain}\\mount on Host {host}',
        3049: f'Failed to connect the Host {host} for the payload create_domain',
        3050: f'Failed to create domain {domain} on Host {host}',
        3051: f'Failed to connect the Host {host} for the payload set_cpu',
        3052: f'Failed to set cpu {cpu} to domain {domain} on Host {host}',
        3053: f'Failed to connect the Host {host} for the payload set_ram',
        3054: f'Failed to set ram {ram}MB to domain {domain} on Host {host}',
        3055: f'Failed to connect the Host {host} for the remove_default_nic',
        3056: f'Failed to remove default nic from domain {domain} on Host {host}',
        3057: f'Failed to connect the Host {host} for the add_gateway_vlan',
        3058: f'Failed to add gateway vlan {gateway_vlan} to domain {domain} on Host {host}',
        3059: f'Failed to connect the Host {host} for the add_secondary_vlans',
        3060: f'Failed to add secondary vlans to domain {domain} on Host {host}',
        3061: f'Failed to connect the Host {host} for the start_domain',
        3062: f'Failed to start domain {domain} on Host {host}',
    }

    messages_list = []

    # validate primary_storage
    def validate_primary_storage(ps, msg_index):
        if ps is None:
            messages_list.append(f'{messages[msg_index + 1]}: {messages[msg_index + 1]}')
            return False

        ps_items = str(ps).split('.')
        if len(ps_items) != 2:
            messages_list.append(f'{messages[msg_index + 2]}: {messages[msg_index + 2]}')
            return False
        elif ps_items[1] not in ('vhd', 'vhdx'):
            messages_list.append(f'{messages[msg_index + 3]}: {messages[msg_index + 3]}')
            return False
        return True

    validated = validate_primary_storage(primary_storage, 3010)

    if validated is False:
        return False, '; '.join(messages_list)

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        add_secondary_vlans = ''
        for vlan in secondary_vlans:
            add_secondary_vlans += f'Add-VMNetworkAdapter -VMName {domain} -Name "vNIC-{vlan}" -SwitchName ' \
                                   f'"Virtual Switch" -DeviceNaming On; ' \
                                   f'Set-VMNetworkAdapterVlan -VMName {domain} ' \
                                   f'-VMNetworkAdapterName "vNIC-{vlan}" -Access -VlanId {vlan}; '
        mount_point = f'drive_{domain}'
        vhdx_file = f'{mount_point}:\\HyperV\\VHDXs\\{image}'
        mount_dir = f'{domain_path}{domain}\\mount'
        # required files to send to domain primary storage
        unattend_source = f'{mount_point}:\\HyperV\\VMs\\{domain}\\unattend.xml'
        unattend_destination = f'{mount_dir}\\unattend.xml'
        network_source = f'{mount_point}:\\HyperV\\VMs\\{domain}\\network.xml'
        network_destination = f'{mount_dir}\\network.xml'

        payloads = {
            # check if vm exists already
            'read_domain_info':        f'Get-VM -Name {domain} ',
            'copy_vhdx_image_file':    f'New-PSDrive -Name {mount_point} -PSProvider FileSystem -Root'
                                       f' {robot_drive_url} -Scope Global; '
                                       f'Copy-Item {vhdx_file} -Destination {domain_path}{domain}\\{primary_storage}',
            'resize_primary_storage':  f'Resize-VHD -Path {domain_path}{domain}\\{primary_storage}'
                                       f' -SizeBytes {size}GB',
            'create_mount_dir':        f'New-Item -ItemType directory -Path {mount_dir}',
            'mount_primary_storage':   f'$mountedVHD = Mount-VHD -Path {domain_path}{domain}\\{primary_storage}'
                                       f' -NoDriveLetter -Passthru; '
                                       f'Set-Disk -Number $mountedVHD.Number -IsOffline $false; '
                                       f'$partitions = Get-Partition -DiskNumber $mountedVHD.Number; '
                                       f'Add-PartitionAccessPath -InputObject $partitions[-1] -AccessPath {mount_dir};'
                                       f'[System.UInt64]$size = (Get-PartitionSupportedSize -DiskNumber'
                                       f' $mountedVHD.Number -PartitionNumber $partitions[-1].PartitionNumber).SizeMax;'
                                       f' Resize-Partition -DiskNumber $mountedVHD.Number -PartitionNumber'
                                       f' $partitions[-1].PartitionNumber -Size $size',
            'copy_unattend_file':      f'New-PSDrive -Name {mount_point} -PSProvider FileSystem -Root'
                                       f' {robot_drive_url} -Scope Global; '
                                       f'Copy-Item {unattend_source} {unattend_destination}',
            'copy_network_file':       f'New-PSDrive -Name {mount_point} -PSProvider FileSystem -Root'
                                       f' {robot_drive_url} -Scope Global; '
                                       f'Copy-Item {network_source} {network_destination}',
            'unmount_primary_storage': f'Dismount-VHD -Path {domain_path}{domain}\\{primary_storage}',
            'delete_mount_dir':        f'Remove-Item -Path {mount_dir} -Recurse -Force',
            'create_domain':           f'New-VM -Name {domain} -Path {domain_path} -Generation 2 -SwitchName'
                                       f' "Virtual Switch" -VHDPath {domain_path}{domain}\\{primary_storage}',
            'set_cpu':                 f'Set-VMProcessor {domain} -Count {cpu}',
            'set_ram':                 f'Set-VMMemory {domain} -DynamicMemoryEnabled $false -StartupBytes {ram}MB',
            'remove_default_nic':      f'Remove-VMNetworkAdapter -VMName {domain}',
            'add_gateway_vlan':        f'Add-VMNetworkAdapter -VMName {domain} -Name "vNIC-{gateway_vlan}" -SwitchName'
                                       f' "Virtual Switch" -DeviceNaming On; '
                                       f'Set-VMNetworkAdapterVlan -VMName {domain} -VMNetworkAdapterName'
                                       f' "vNIC-{gateway_vlan}" -Access -VlanId {gateway_vlan}',
            'add_secondary_vlans':     add_secondary_vlans,
            'start_domain':            f'Start-VM -Name {domain}; Wait-VM -Name {domain} -For IPAddress',
        }

        ret = rcc.run(payloads['read_domain_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            # if vm exists already then we should not build it again,
            # by mistake same vm is requested to build again so return with error
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('read_domain_info', ret)

        ret = rcc.run(payloads['copy_vhdx_image_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('copy_vhdx_image_file', ret)

        ret = rcc.run(payloads['resize_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
        fmt.add_successful('resize_primary_storage', ret)

        ret = rcc.run(payloads['create_mount_dir'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        fmt.add_successful('create_mount_dir', ret)

        ret = rcc.run(payloads['mount_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 9}: {messages[prefix + 9]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 10}: {messages[prefix + 10]}'), fmt.successful_payloads
        fmt.add_successful('mount_primary_storage', ret)

        ret = rcc.run(payloads['copy_unattend_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 11}: {messages[prefix + 11]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 12}: {messages[prefix + 12]}'), fmt.successful_payloads
        fmt.add_successful('copy_unattend_file', ret)

        ret = rcc.run(payloads['copy_network_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 13}: {messages[prefix + 13]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 14}: {messages[prefix + 14]}'), fmt.successful_payloads
        fmt.add_successful('copy_network_file', ret)

        ret = rcc.run(payloads['unmount_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 15}: {messages[prefix + 15]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 16}: {messages[prefix + 16]}'), fmt.successful_payloads
        fmt.add_successful('unmount_primary_storage', ret)

        ret = rcc.run(payloads['delete_mount_dir'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 17}: {messages[prefix + 17]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 18}: {messages[prefix + 18]}'), fmt.successful_payloads
        fmt.add_successful('delete_mount_dir', ret)

        ret = rcc.run(payloads['create_domain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 19}: {messages[prefix + 19]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 20}: {messages[prefix + 20]}'), fmt.successful_payloads
        fmt.add_successful('create_domain', ret)

        ret = rcc.run(payloads['set_cpu'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 21}: {messages[prefix + 21]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 22}: {messages[prefix + 22]}'), fmt.successful_payloads
        fmt.add_successful('set_cpu', ret)

        ret = rcc.run(payloads['set_ram'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 23}: {messages[prefix + 23]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 24}: {messages[prefix + 24]}'), fmt.successful_payloads
        fmt.add_successful('set_ram', ret)

        ret = rcc.run(payloads['remove_default_nic'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 25}: {messages[prefix + 25]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 26}: {messages[prefix + 26]}'), fmt.successful_payloads
        fmt.add_successful('remove_default_nic', ret)

        ret = rcc.run(payloads['add_gateway_vlan'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 27}: {messages[prefix + 27]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 28}: {messages[prefix + 28]}'), fmt.successful_payloads
        fmt.add_successful('add_gateway_vlan', ret)

        if add_secondary_vlans != '':
            ret = rcc.run(payloads['add_secondary_vlans'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 29}: {messages[prefix + 29]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 30}: {messages[prefix + 30]}'), fmt.successful_payloads
            fmt.add_successful('add_secondary_vlans', ret)

        ret = rcc.run(payloads['start_domain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 31}: {messages[prefix + 31]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 32}: {messages[prefix + 32]}'), fmt.successful_payloads
        fmt.add_successful('start_domain', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3030, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def quiesce(domain: str, host: str) -> Tuple[bool, str]:
    """
    description: Shutdown the VM

    parameters:
        domain:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1400: f'Successfully quiesced domain {domain} on host {host}',
        3421: f'Failed to connect to the host {host} for payload read_domstate_0',
        3422: f'Failed to read domain {domain} state from host {host}',
        3423: f'Failed to connect to the host {host} for payload shutdown_domain',
        3424: f'Failed to quiesce domain {domain} on host {host}',
        3425: f'Failed to connect to the host {host} for payload read_domstate_n',
        3426: f'Failed to read domain {domain} state from host {host}',
        3427: f'Failed to connect to the host {host} for payload turnoff_domain',
        3428: f'Failed to destroy domain {domain} on host {host}',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_domstate_0': f'Get-VM -Name {domain} ',
            'shutdown_domain': f'Stop-VM -Name {domain} ',
            'read_domstate_n': f'Get-VM -Name {domain} ',
            'turnoff_domain': f'Stop-VM -Name {domain} -TurnOff',  # force shutdown == turn off
        }

        # first read the state before shutdown the domain
        ret = rcc.run(payloads['read_domstate_0'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        quiesced = False
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            if hyperv_dictify(ret['payload_message'])['State'] == 'Off':
                quiesced = True
        fmt.add_successful('read_domstate_0', ret)

        if quiesced is True:
            return True, "", fmt.successful_payloads

        ret = rcc.run(payloads['shutdown_domain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('shutdown_domain', ret)

        # Since shutdown is run make sure it is in Off state, so read the state until it is Off
        # for max 300 seconds
        start_time = datetime.now()
        turnoff = False
        attempt = 1
        while (datetime.now() - start_time).total_seconds() < 300 and turnoff is False:
            ret = rcc.run(payloads['read_domstate_n'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                fmt.channel_error(
                    ret, f'{prefix + 5}: Attempt #{attempt}-{messages[prefix + 5]}'
                ), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                fmt.payload_error(
                    ret, f'{prefix + 6}: Attempt #{attempt}-{messages[prefix + 6]}'
                ), fmt.successful_payloads
            else:
                if hyperv_dictify(ret['payload_message'])['State'] == 'Off':
                    turnoff = True
                else:
                    # wait interval is 0.5 seconds
                    time.sleep(0.5)
            attempt += 1
            fmt.add_successful('read_domstate_n', ret)

        # After 300 seconds still domain is not shut off then force off it
        if turnoff is False:
            ret = rcc.run(payloads['turnoff_domain'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
            fmt.add_successful('turnoff_domain', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3420, {})
    if status is False:
        return status, msg

    return True, f'1400: {messages[1400]}'


def read(
        domain: str,
        host: str,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description: Gets the vm information

    parameters:
        domain:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
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
        3221: f'Failed to connect to the host {host} for payload read_domain_info',
        3222: f'Failed to read data of domain {domain} from host {host}',
    }

    # set the outputs
    data_dict = {}
    message_list = []

    def run_host(host, prefix, successful_payloads):
        retval = True
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_domain_info': f'Get-VM -Name {domain} ',
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
            data_dict[host] = hyperv_dictify(ret["payload_message"])
            fmt.add_successful('read_domain_info', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3220, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [f'1200: {messages[1200]}']


def restart(
        domain: str,
        host: str,
) -> Tuple[bool, str]:
    """
    description: Restarts the VM

    parameters:
        domain:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1500: f'Successfully restarted domain {domain} on host {host}',
        3521: f'Failed to connect to the host {host} for payload read_domstate_0',
        3522: f'Failed to read domain {domain} state from host {host}',
        3523: f'Failed to connect to the host {host} for payload restart_domain',
        3524: f'Failed to run restart command for domain {domain} on host {host}',
        3525: f'Failed to connect to the host {host} for payload read_domstate_n',
        3526: f'Failed to read domain {domain} state from host {host}',
        3527: f'Failed to restart domain {domain} on host {host}',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_domstate_0': f'Get-VM -Name {domain} ',
            'restart_domain': f'Start-VM -Name {domain} ',
            'read_domstate_n': f'Get-VM -Name {domain} ',
        }

        # First check if dommain is already running or not
        ret = rcc.run(payloads['read_domstate_0'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        running = False
        if ret["payload_code"] != SUCCESS_CODE:
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            if hyperv_dictify(ret['payload_message'])['State'] == 'Running':
                running = True
        fmt.add_successful('read_domstate_0', ret)

        if running is True:
            return True, "", fmt.successful_payloads

        ret = rcc.run(payloads['restart_domain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('restart_domain', ret)

        # Since restart is run make sure it is in running state, so read the state until it is running
        # for max 300 seconds
        running = False
        start_time = datetime.now()
        attempt = 1
        while (datetime.now() - start_time).total_seconds() < 300 and running is False:
            ret = rcc.run(payloads['read_domstate_n'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                fmt.channel_error(ret, f'{prefix + 5}: Attempt #{attempt}-{messages[prefix + 5]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                fmt.payload_error(ret, f'{prefix + 6}: Attempt #{attempt}-{messages[prefix + 6]}'), fmt.successful_payloads
            else:
                if hyperv_dictify(ret['payload_message'])['State'] == 'Running':
                    running = True
                else:
                    # wait interval is 0.5 seconds
                    time.sleep(0.5)
            attempt += 1
            fmt.add_successful('read_domstate_n', ret)

        # After 300 seconds still domain is not running then report it as failed
        if running is False:
            return False, f'{prefix + 7}: {messages[prefix + 7]}', fmt.successful_payloads

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3520, {})
    if status is False:
        return status, msg

    return True, f'1500: {messages[1500]}'


def scrub(
    domain: str,
    host: str,
    primary_storage: str,
    domain_path=None,
) -> Tuple[bool, str]:
    """
    description: Removes the VM

    parameters:
        domain:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        domain_path:
            description: The location or directory path where the primary storage is created
            type: string
            required: true
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        primary_storage:
            description: |
                The storage on which domain operating system is installed
                It must be an unique name used to create the storage image file on the host.
                eg '123_45_HDD_578.img'
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # domain_path defaults to D:\\HyperV\\
    if domain_path is None:
        domain_path = f'D:\\HyperV\\'

    # Define message
    messages = {
        1100: f'Successfully scrubbed domain {domain} on host {host}',
        3121: f'Failed to connect to the host {host} for payload read_domstate',
        3122: f'Failed to read  domain {domain} state from host {host}',
        3123: f'Failed to connect to the host {host} for payload turnoff_domain',
        3124: f'Failed to turnoff domain {domain} on host {host}',
        3125: f'Failed to connect to the host {host} for payload remove_domain',
        3126: f'Failed to remove domain {domain} on host {host}',
        3127: f'Failed to connect to the host {host} for payload remove_primary_storage',
        3128: f'Failed to remove {domain_path}{primary_storage} on host {host}',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'read_domstate': f'Get-VM -Name {domain} ',
            'turnoff_domain': f'Stop-VM -Name {domain} -TurnOff',
            'remove_domain': f'Remove-VM -Name {domain} -Force',
            'remove_primary_storage': f'Remove-Item -Path {domain_path}{domain}\\{primary_storage} '
                                      f'-Force -Confirm:$false',
        }

        ret = rcc.run(payloads['read_domstate'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        turnoff = False
        if ret["payload_code"] != SUCCESS_CODE:
            # check if already undefined/remove
            if f'Hyper-V was unable to find a virtual machine with name \"{domain}\"' in ret["payload_error"].strip():
                return True, "", fmt.successful_payloads
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            if hyperv_dictify(ret['payload_message'])['State'] == 'Off':
                turnoff = True
        fmt.add_successful('read_domstate', ret)

        if turnoff is False:
            ret = rcc.run(payloads['turnoff_domain'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
            fmt.add_successful('turnoff_domain', ret)

        ret = rcc.run(payloads['remove_domain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
        fmt.add_successful('remove_domain', ret)

        ret = rcc.run(payloads['remove_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        fmt.add_successful('remove_primary_storage', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    if status is False:
        return status, msg

    return True, f'1100: {messages[1100]}'

