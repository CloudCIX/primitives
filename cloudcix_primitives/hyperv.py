"""
Primitive for Virtual Machine on Windows hypervisor
"""
# stdlib
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
# local
from cloudcix_primitives.utils import (
    SSHCommsWrapper,
    HostErrorFormatter,
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
        gateway_vlan: dict,
        host: str,
        primary_storage: str,
        ram: int,
        size: int,
        secondary_vlans=None,
        secondary_storages=None,
) -> Tuple[bool, str]:
    """
        description:
        1. Copies <image> to the given <domain_path><storage>
        2. Resizes the storage file to <size>
        3. Creates a HyperV VM

    parameters:
        image:
            description: The path to the image file that will be copied to the domain directory.
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
        size:
            description: The size of the storage image to be created, must be in GB value
            type: integer
            required: true
        secondary_storages:
            description: |
                The list of all secondary storages that are attached to domain
                the names of storages must be unique.
                e.g secondary_storages = ['564_45_HDD_909.vhdx',]
            type: array
            required: false
            items:
                type: string
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

    # Define message
    messages = {
        1000: f'Successfully created domain {domain} on Host {host}',
        # validations
        3011: 'Invalid "primary_storage", The "primary_storage" is required',
        3012: 'Invalid "primary_storage", The "primary_storage" is must be a string type',
        3013: 'Invalid "primary_storage", The "primary_storage" must be a name of the storage file with extension',
        3014: 'Invalid "primary_storage", The "primary_storage" can only be either .img or .qcow2 file formats',
        3015: 'Invalid "secondary_storages", every item in "secondary_storages" must be of string type',
        3016: 'Invalid "secondary_storages", one or more items are invalid, Errors: ',
        # payload execution
        3031: f'Failed to connect to the host {host} for the payload read_domain_info',
        3032: f'Failed to create domain, the requested domain {domain} already exists on the Host {host}',
        3033: f'Failed to connect the Host {host} for the payload copy_vhdx_image_file',
        3034: f'Failed to copy vhdx image file {image} to the domain directory D:\\HyperV\\{domain}{primary_storage}'
              f' on Host {host}.',
        3035: f'Failed to connect the Host {host} for the payload resize_primary_storage',
        3036: f'Failed to resize the primary storage image to {size}GB on Host {host}',
        3037: f'Failed to connect the Host {host} for the payload create_mount_dir',
        3038: f'Failed to create mount dir D:\\HyperV\\{domain}\\mount on Host {host}',
        3039: f'Failed to connect the Host {host} for the payload mount_primary_storage',
        3040: f'Failed to mount primary storage on Host {host}',
        3041: f'Failed to connect the Host {host} for the payload copy_unattend_file',
        3042: f'Failed to copy unattend file to D:\\HyperV\\{domain}\\mount\\ on Host {host}',
        3043: f'Failed to connect the Host {host} for the payload copy_network_file',
        3044: f'Failed to copy network file to D:\\HyperV\\{domain}\\mount\\ on Host {host}',
        3045: f'Failed to connect the Host {host} for the payload unmount_primary_storage',
        3046: f'Failed to unmount primary storage at D:\\HyperV\\{domain}\\mount on Host {host}',
        3047: f'Failed to connect the Host {host} for the payload delete_mount_dir',
        3048: f'Failed to delete mount dir D:\\HyperV\\{domain}\\mount on Host {host}',
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
        3061: f'Failed to connect the Host {host} for the add_secondary_storages',
        3062: f'Failed to add secondary storages to domain {domain} on Host {host}',
        3063: f'Failed to connect the Host {host} for the start_domain',
        3064: f'Failed to start domain {domain} on Host {host}',
    }

    messages_list = []

    # validate primary_storage
    def validate_primary_storage(ps, msg_index):
        if ps is None:
            messages_list.append(f'{messages[msg_index]}: {messages[msg_index]}')
            return False
        if type(primary_storage) is not str:
            messages_list.append(f'{messages[msg_index + 1]}: {messages[msg_index + 1]}')
            return False

        ps_items = ps.split('.')
        if len(ps_items) != 2:
            messages_list.append(f'{messages[msg_index + 2]}: {messages[msg_index + 2]}')
            return False
        elif ps_items[1] not in ('vhd', 'vhdx'):
            messages_list.append(f'{messages[msg_index + 3]}: {messages[msg_index + 3]}')
            return False
        return True

    validated = validate_primary_storage(primary_storage, 3011)

    # validate secondary storages
    def validate_secondary_storages(sstgs, msg_index):
        if type(sstgs) is not list:
            messages_list.append(f'{messages[msg_index]}: {messages[msg_index]}')
            return False

        errors = []
        valid_sstgs = True
        for storage in secondary_storages:
            if type(storage) is not str:
                errors.append(f'Invalid secondary_storage {storage}, it must be string type')
                valid_sstgs = False
            else:
                stg_items = storage.split('.')
                if len(stg_items) != 2:
                    errors.append(
                        f'Invalid secondary_storage {storage}, it must be the name of the storage file with extension',
                    )
                    valid_sstgs = False
                elif stg_items[1] not in ('vhd', 'vhdx'):
                    errors.append(
                        f'Invalid secondary_storage {storage}, it can only be either .img or .qcow2 file format',
                    )
                    valid_sstgs = False

        if valid_sstgs is False:
            messages_list.append(f'{messages[msg_index + 1]}: {messages[msg_index + 1]} {";".join(errors)}')

        return valid_sstgs

    if secondary_storages:
        validated = validate_secondary_storages(secondary_storages, 3015)
    else:
        secondary_storages = []

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

        add_secondary_storages = ''
        for storage in secondary_storages:
            #  create new drive: it is done in storage_hyperv, just keeping here for my clarity, will remove it
            #        add_secondary_storages += f'New-VHD -Path {domain_path}{storage["name"]}
            #        -SizeBytes [int64]{storage["gb"]}*1GB -Dynamic'
            # attach to the domain
            add_secondary_storages += f'Add-VMHardDiskDrive -VMName {domain} -Path D:\\HyperV\\{storage}; '

        robot_drive_url = '\\\\robot.devtest.cloudcix.com\\etc\\cloudcix\\robot'
        mount_point = f'drive_{domain}'
        vhdx_file = f'{mount_point}:\\HyperV\\VHDXs\\{image}'
        mount_dir = f'D:\\HyperV\\mount'
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
                                       f'Copy-Item {vhdx_file} -Destination D:\\HyperV\\{primary_storage}',
            'resize_primary_storage':  f'Resize-VHD -Path D:\\HyperV\\{primary_storage}'
                                       f' -SizeBytes {size}GB',
            'create_mount_dir':        f'New-Item -ItemType directory -Path {mount_dir}',
            'mount_primary_storage':   f'$mountedVHD = Mount-VHD -Path D:\\HyperV\\{primary_storage} -NoDriveLetter'
                                       f' -Passthru; '
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
            'unmount_primary_storage': f'Dismount-VHD -Path D:\\HyperV\\{primary_storage}',
            'delete_mount_dir':        f'Remove-Item -Path {mount_dir} -Recurse -Force',
            'create_domain':           f'New-VM -Name {domain} -Path D:\\HyperV -Generation 2 -SwitchName'
                                       f' "Virtual Switch" -VHDPath D:\\HyperV\\{primary_storage}',
            'set_cpu':                 f'Set-VMProcessor {domain} -Count {cpu}',
            'set_ram':                 f'Set-VMMemory {domain} -DynamicMemoryEnabled $false -StartupBytes {ram}MB',
            'remove_default_nic':      f'Remove-VMNetworkAdapter -VMName {domain}',
            'add_gateway_vlan':        f'Add-VMNetworkAdapter -VMName {domain} -Name "vNIC-{gateway_vlan}" -SwitchName'
                                       f' "Virtual Switch" -DeviceNaming On; '
                                       f'Set-VMNetworkAdapterVlan -VMName {domain} -VMNetworkAdapterName'
                                       f' "vNIC-{gateway_vlan}" -Access -VlanId {gateway_vlan}',
            'add_secondary_vlans':     add_secondary_vlans,
            'add_secondary_storages':  add_secondary_storages,
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

        if add_secondary_storages != '':
            ret = rcc.run(payloads['add_secondary_storages'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 31}: {messages[prefix + 31]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 32}: {messages[prefix + 32]}'), fmt.successful_payloads
            fmt.add_successful('add_secondary_storages', ret)

        ret = rcc.run(payloads['start_domain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 33}: {messages[prefix + 33]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 34}: {messages[prefix + 34]}'), fmt.successful_payloads
        fmt.add_successful('start_domain', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3030, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def read():
    return False, 'Not Implemented'


def quiesce():
    return(False, 'Not Implemted')


def restart():
    return(False, 'Not Implemted')


def scrub():
    return(False, 'Not Implemted')


def scrubprep():
    return(False, 'Not Implemted')


def updatequiesced():
    return(False, 'Not Implemted')


def updaterunning():
    return(False, 'Not Implemted')
