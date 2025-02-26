"""
Primitive for Virtual Machine on Windows hypervisor
"""
# stdlib
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_lsh, comms_ssh
# local
from cloudcix_primitives.utils import (
    check_template_data,
    HostErrorFormatter,
    hyperv_dictify,
    JINJA_ENV,
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
    host: str,
    vm_identifier: str,
    storage_identifier: str,
    image: str,
    administrator_password: str,
    cpu: int,
    ram: int,
    gb: int,
    region_url: str,
    gateway_network: dict,
    secondary_networks=[],
    local_mount_path='/mnt/images'
) -> Tuple[bool, str]:
    """
        description:
        1. Copies <image> to the given <vm_identifier><storage_identifier>
        2. Resizes the storage file to <gb>
        3. Creates a HyperV VM

    parameters:
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        storage_identifier:
            description: Unique identification name for the Primary Storage image of the HyperV VM.
            type: string
            required: true
        image:
            description: The path to the image file that will be copied to the domain directory.
            type: string
            required: true
        administrator_password:
            description: Required to supply to the unattended.xml file to build the VM
            type: string
            required: true
        cpu:
            description: Number of CPUs for the HyperV VM
            type: integer
            required: true
        ram:
            description: Number of RAM, in GBs, for the HyperV VM
            type: integer
            required: true
        gb:
            description: The size of the primary storage image to be created
            type: integer
            required: true
        region_url:
            description: Region Network Drive url to access image file, unattend and network xml files
            type: string
            required: true
        gateway_network:
            type: object
            properties:
                vlan: 
                    description: The VLAN ID of the gateway network of the VM
                    type: integer
                    required: true
                ips: 
                    type: object
                    properties:
                        ip: 
                            description: An IP address to be configured on the gateway network
                            type: string
                            required: true
                        netmask: 
                            description: The netmask of the IP 
                            type: integer
                            required: true
                        gateway: 
                            description: The Gateway IP address for the network
                            type: string
                            required: true
                        dns: 
                            description: A commma seperated string of the DNS nameserver for the gateway network
                            type: string
                            required: true
            required: true
        secondary_networks:
            type: array
            items:
                type: object
                properties:
                    vlan: 
                        description: The VLAN ID of a secondary network of the VM
                        type: integer
                        required: true
                    ips: 
                        type: object
                        properties:
                            ip: 
                                description: An IP address to be configured on this secondary network
                                type: string
                                required: true
                            netmask: 
                                description: The netmask of the IP
                                type: integer
                                required: true
            required: false
        local_mount_path:
            description: |
                The path to the NFS mount point for the primitive to write the xml files to. 
                This will default to "/mnt/images" if not provided. 
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Path Variables required by the payloads to build a VM.
    vm_path = f'D:\\HyperV\\{vm_identifier}'
    storage_path = f'{vm_path}\\{storage_identifier}.vhdx'
    host_mount_path = f'\\\\{region_url}\\etc\\cloudcix\\robot'
    vm_local_mount_path = f'{local_mount_path}/HyperV/VMs/{vm_identifier}'

    # Define message
    messages = {
        1000: f'Successfully created VM {vm_identifier} on Host {host}',
        # templates
        3010: 'Failed to render jinja2 template for unattend.xml',
        3011: 'Failed to render jinja2 template for network.xml',
        # payload execution
        3031: f'Failed to connect to the host {host} for the payload read_vm_info',
        3032: f'Failed to create VM, the requested VM {vm_identifier} already exists on the Host {host}',
        3033: f'Failed to connect the Host {host} for the payload create_dir_structure',
        3034: f'Failed to create directory {vm_path}/mount on Host {host}',
        3035: f'Failed to connect the Host {host} for the payload create_primary_storage',
        3036: f'Failed to create primary storage vhdx image file {image} in {storage_path} on Host {host}.',
        3037: f'Failed to connect the Host {host} for the payload resize_primary_storage',
        3038: f'Failed to resize the primary storage image to {gb}GB on Host {host}',
        3039: f'Failed to connect the Host {host} for the payload mount_primary_storage',
        3040: f'Failed to mount primary storage on Host {host}',
        3041: f'Failed to create directory for {vm_identifier} in {vm_local_mount_path} ',
        3042: f'Failed to create unattend.xml file in {vm_local_mount_path}.',
        3043: f'Failed to create network.xml file in {vm_local_mount_path}.',
        3044: f'Failed to connect the Host {host} for the payload copy_unattend_file',
        3045: f'Failed to copy unattend.xml to {vm_path}\\mount on Host {host}',
        3046: f'Failed to connect the Host {host} for the payload copy_network_file',
        3047: f'Failed to copy network.xml to {vm_path}\\mount on Host {host}',
        3048: f'Failed to connect the Host {host} for the payload dismount_primary_storage',
        3049: f'Failed to dismount primary storage at {vm_path}\\mount on Host {host}',
        3050: f'Failed to connect the Host {host} for the payload remove_mount_dir',
        3051: f'Failed to remove mount dir {vm_path}\\mount on Host {host}',
        3052: f'Failed to remoce directory for {vm_identifier} in {vm_local_mount_path}.',
        3053: f'Failed to connect the Host {host} for the payload create_vm',
        3054: f'Failed to create VM {vm_identifier} on Host {host}',
        3055: f'Failed to connect the Host {host} for the payload set_cpu',
        3056: f'Failed to set CPU for VM {vm_identifier} on Host {host}',
        3057: f'Failed to connect the Host {host} for the payload set_ram',
        3058: f'Failed to set RAM for VM {vm_identifier} on Host {host}',
        3059: f'Failed to connect the Host {host} for the remove_default_nic',
        3060: f'Failed to remove default nic from VM {vm_identifier} on Host {host}',
        3061: f'Failed to connect the Host {host} for the gateway_vlan_payload',
        3062: f'Failed to add gateway VLAN to VM {vm_identifier} on Host {host}',
        3063: f'Failed to connect the Host {host} for the secondary_vlan_payload',
        3064: f'Failed to add secondary VLAN to VM {vm_identifier} on Host {host}',
        3065: f'Failed to connect the Host {host} for the start_vm',
        3066: f'Failed to start VM {vm_identifier} on Host {host}',
    }

    # template data for required files
    template_data = {
        'gateway_network': gateway_network,
        'secondary_networks': secondary_networks,
        'administrator_password': administrator_password,
    }
    # unattend.xml file
    template = JINJA_ENV.get_template('hyperv/unattend.xml.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3019: {messages[3010]}'

    unattend_xml = template.render(**template_data)

    # network.xml file
    template = JINJA_ENV.get_template('hyperv/network.xml.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3020: {messages[3011]}'

    network_xml = template.render(**template_data)

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'administrator')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            # check if vm exists already
            'read_vm_info':             f'Get-VM -Name {vm_identifier} ',
            'create_dir_structure':     f'New-Item -ItemType Directory -Path {vm_path}\\mount -Force',
            'create_primary_storage':   f'New-PSDrive -Name drive_{vm_identifier} -PSProvider FileSystem -Root {host_mount_path}; '
                                        f'Copy-Item drive_{vm_identifier}:\\HyperV\\VHDXs\\{image}  -Destination {storage_path}',
            'resize_primary_storage':   f'Resize-VHD -Path {storage_path} -SizeBytes {gb}GB',
            'mount_primary_storage':    f'$mountedVHD = Mount-VHD -Path {storage_path} -NoDriveLetter -Passthru; '
                                        'Set-Disk -Number $mountedVHD.Number -IsOffline $false; '
                                        '$partitions = Get-Partition -DiskNumber $mountedVHD.Number; '
                                        f'Add-PartitionAccessPath -InputObject $partitions[-1] -AccessPath {vm_path}\\mount; '
                                        '[System.UInt64]$size = (Get-PartitionSupportedSize -DiskNumber $mountedVHD.Number '
                                        '-PartitionNumber $partitions[-1].PartitionNumber).SizeMax; '
                                        'Resize-Partition -DiskNumber $mountedVHD.Number -PartitionNumber $partitions[-1].PartitionNumber -Size $size',
            'create_local_mount_dir':   f'mkdir --parents {vm_local_mount_path}',
            'create_unattend_file':     f'cat > /{vm_local_mount_path}/unattend.xml <<EOF\n{unattend_xml}',
            'create_network_file':      f'cat > /{vm_local_mount_path}/network.xml <<EOF\n{network_xml}',
            'copy_unattend_file':       f'New-PSDrive -Name drive_{vm_identifier} -PSProvider FileSystem -Root {host_mount_path}; '
                                        f'Copy-Item drive_{vm_identifier}:\\HyperV\\VMs\\{vm_identifier}\\unattend.xml {vm_path}\\mount\\unattend.xml',
            'copy_network_file':        f'New-PSDrive -Name drive_{vm_identifier} -PSProvider FileSystem -Root {host_mount_path}; '
                                        f'Copy-Item drive_{vm_identifier}:\\HyperV\\VMs\\{vm_identifier}\\network.xml {vm_path}\\mount\\network.xml',
            'dismount_primary_storage': f'Dismount-VHD -Path {storage_path}',
            'remove_mount_dir':         f'Remove-Item -Path {vm_path}\\mount -Recurse -Force',
            'remove_local_mount_dir':   f'rm --force --recursive {vm_local_mount_path}',
            'create_vm':                f'New-VM -Name {vm_identifier} -Path {vm_path} -Generation 2 -SwitchName "Virtual Switch" -VHDPath {storage_path}',
            'set_cpu':                  f'Set-VMProcessor {vm_identifier} -Count {cpu}',
            'set_ram':                  f'Set-VMMemory {vm_identifier} -DynamicMemoryEnabled $false -StartupBytes {ram}GB',
            'remove_default_nic':       f'Remove-VMNetworkAdapter -VMName {vm_identifier}',
            'add_vlan_template':        f'Add-VMNetworkAdapter -VMName {vm_identifier} -Name "vNIC-%(vlan)s" -SwitchName "Virtual Switch" -DeviceNaming On; '
                                        f'Set-VMNetworkAdapterVlan -VMName {vm_identifier} -VMNetworkAdapterName "vNIC-%(vlan)s" -Access -VlanId %(vlan)s',
            'start_vm':                 f'Start-VM -Name {vm_identifier}; Wait-VM -Name {vm_identifier} -For IPAddress',
        }

        ret = rcc.run(payloads['read_vm_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            # if vm exists already then we should not build it again,
            # by mistake same vm is requested to build again so return with error
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('read_vm_info', ret)

        ret = rcc.run(payloads['create_dir_structure'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('create_dir_structure', ret)

        ret = rcc.run(payloads['create_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
        fmt.add_successful('create_primary_storage', ret)

        ret = rcc.run(payloads['resize_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        fmt.add_successful('resize_primary_storage', ret)

        ret = rcc.run(payloads['mount_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 9}: {messages[prefix + 9]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 10}: {messages[prefix + 12]}'), fmt.successful_payloads
        fmt.add_successful('mount_primary_storage', ret)

        ret = comms_lsh(payloads['create_local_mount_dir'])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 11}: {messages[prefix + 11]}'), fmt.successful_payloads
        fmt.add_successful('create_local_mount_dir', ret)

        ret = comms_lsh(payloads['create_unattend_file'])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 12}: {messages[prefix + 12]}'), fmt.successful_payloads
        fmt.add_successful('create_unattend_file', ret)

        ret = comms_lsh(payloads['create_network_file'])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 13}: {messages[prefix + 13]}'), fmt.successful_payloads
        fmt.add_successful('create_network_file', ret)

        ret = rcc.run(payloads['copy_unattend_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 14}: {messages[prefix + 14]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 15}: {messages[prefix + 15]}'), fmt.successful_payloads
        fmt.add_successful('copy_unattend_file', ret)

        ret = rcc.run(payloads['copy_network_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 16}: {messages[prefix + 16]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 17}: {messages[prefix + 17]}'), fmt.successful_payloads
        fmt.add_successful('copy_network_file', ret)

        ret = rcc.run(payloads['dismount_primary_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 18}: {messages[prefix + 18]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 19}: {messages[prefix + 19]}'), fmt.successful_payloads
        fmt.add_successful('dismount_primary_storage', ret)

        ret = rcc.run(payloads['remove_mount_dir'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 20}: {messages[prefix + 20]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 21}: {messages[prefix + 21]}'), fmt.successful_payloads
        fmt.add_successful('remove_mount_dir', ret)

        ret = comms_lsh(payloads['remove_local_mount_dir'])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 22}: {messages[prefix + 22]}'), fmt.successful_payloads
        fmt.add_successful('remove_local_mount_dir', ret)

        ret = rcc.run(payloads['create_vm'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 23}: {messages[prefix + 23]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 24}: {messages[prefix + 24]}'), fmt.successful_payloads
        fmt.add_successful('create_vm', ret)

        ret = rcc.run(payloads['set_cpu'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 25}: {messages[prefix + 25]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 26}: {messages[prefix + 26]}'), fmt.successful_payloads
        fmt.add_successful('set_cpu', ret)

        ret = rcc.run(payloads['set_ram'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 27}: {messages[prefix + 27]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 28}: {messages[prefix + 28]}'), fmt.successful_payloads
        fmt.add_successful('set_ram', ret)

        ret = rcc.run(payloads['remove_default_nic'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 29}: {messages[prefix + 29]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 30}: {messages[prefix + 30]}'), fmt.successful_payloads
        fmt.add_successful('remove_default_nic', ret)

        gateway_vlan_payload = payloads['add_vlan_template'] % {'vlan': gateway_network['vlan']}
        ret = rcc.run(gateway_vlan_payload)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 31}: {messages[prefix + 31]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 32}: {messages[prefix + 32]}'), fmt.successful_payloads
        fmt.add_successful('add_vlan_template(%s)' % gateway_vlan_payload, ret)

        for network in secondary_networks:
            secondary_vlan_payload = payloads['add_vlan_template'] % {'vlan': network['vlan']}

            ret = rcc.run(secondary_vlan_payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 33}: {messages[prefix + 33]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 34}: {messages[prefix + 34]}'), fmt.successful_payloads
            fmt.add_successful('add_vlan_template(%s)' % secondary_vlan_payload, ret)

        ret = rcc.run(payloads['start_vm'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 35}: {messages[prefix + 35]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 36}: {messages[prefix + 36]}'), fmt.successful_payloads
        fmt.add_successful('start_vm', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3030, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def quiesce(host: str, vm_identifier: str) -> Tuple[bool, str]:
    """
    description: Shutdown the VM

    parameters:
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
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
        1400: f'Successfully quiesced VM {vm_identifier} on host {host}',
        3421: f'Failed to connect to the host {host} for payload shutdown_vm',
        3422: f'Failed to quiesce VM {vm_identifier} on host {host}',
        3423: f'Failed to connect to the host {host} for payload get_state',
        3424: f'Failed to read VM {vm_identifier} state from host {host}',
        3425: 'Expected State of VM after shutdown_vm payload is not "Off", it is ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'shutdown_vm':  f'try {{ Stop-VM -Name {vm_identifier} }} catch {{}}; $timeout=300; $interval=1; $elapsed=0; '
                            f'while($elapsed -lt $timeout -and (Get-VM -Name {vm_identifier}).State -ne "Off")'
                            '{{ Start-Sleep -Seconds $interval; $elapsed+=$interval; }}; '
                            f'if((Get-VM -Name {vm_identifier}).State -ne "Off"){{ Stop-VM -Name $vmName -TurnOff }}',
            'get_state':    f'$state = Get-VM -Name "{vm_identifier}"; $state.State',
        }

        ret = rcc.run(payloads['shutdown_vm'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('shutdown_vm', ret)

        ret = rcc.run(payloads['get_state'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('get_state', ret)

        if ret['payload_message'].strip() != "Off":
            return False, f'{prefix + 5}: {messages[prefix + 5]} {ret["payload_message"]}', fmt.successful_payloads

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3420, {})

    if status is False:
        return status, msg

    return True, f'1400: {messages[1400]}'


def read(host: str, vm_identifier: str) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description: Gets the vm information

    parameters:
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
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
        1200: f'Successfully read xml data of VM {vm_identifier} from host {host}',
        3221: f'Failed to connect to the host {host} for payload read_vm_info',
        3222: f'Failed to read data of VM {vm_identifier} from host {host}',
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
            'read_vm_info': f'Get-VM -Name {vm_identifier} ',
        }

        ret = rcc.run(payloads['read_vm_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            # Load the domain info(in XML) into dict
            data_dict[host] = hyperv_dictify(ret["payload_message"])
            fmt.add_successful('read_vm_info', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3220, {})
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [f'1200: {messages[1200]}']


def restart(host: str, vm_identifier: str) -> Tuple[bool, str]:
    """
    description: Restarts the VM

    parameters:
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
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
        1500: f'Successfully restarted VM {vm_identifier} on host {host}',
        3521: f'Failed to connect to the host {host} for payload restart_vm',
        3522: f'Failed to run restart command for VM {vm_identifier} on host {host}',
        3523: f'Failed to connect to the host {host} for payload get_state',
        3524: f'Failed to read VM {vm_identifier} state from host {host}',
        3525: 'Expected State of VM after restart_vm payload is not "Running", it is ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'restart_vm': f'Start-VM -Name "{vm_identifier}"; Wait-VM "{vm_identifier}" -Timeout 300 -For IPAddress',
            'get_state':  f'$state = Get-VM -Name "{vm_identifier}"; $state.State',
        }

        ret = rcc.run(payloads['restart_vm'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('restart_vm', ret)

        ret = rcc.run(payloads['get_state'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('get_state', ret)

        if ret['payload_message'].strip() != "Running":
            return False, f'{prefix + 5}: {messages[prefix + 5]} {ret["payload_message"]}', fmt.successful_payloads

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3520, {})
    if status is False:
        return status, msg

    return True, f'1500: {messages[1500]}'


def scrub(
    host: str,
    vm_identifier: str,
    storage_identifier: str,
) -> Tuple[bool, str]:
    """
    description: Removes the VM

    parameters:
        host:
            description: The dns or ipadddress of the Host on which the domain is built
            type: string
            required: true
        vm_identifier:
            description: Unique identification name for the HyperV VM on the HyperV Host.
            type: string
            required: true
        storage_identifier:
            description: Unique identification name for the Primary Storage image of the HyperV VM.
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Path Variables required by the payloads to build a VM.
    vm_path = f'D:\\HyperV\\{vm_identifier}'
    storage_path = f'{vm_path}\\{storage_identifier}.vhdx'

    # Define message
    messages = {
        1100: f'Successfully scrubbed VM {vm_identifier} on host {host}',
        3121: f'Failed to connect to the host {host} for payload shutdown_vm',
        3122: f'Failed to turnoff VM {vm_identifier} on host {host}',
        3123: f'Failed to connect to the host {host} for payload remove_vm',
        3124: f'Failed to remove VM {vm_identifier} on host {host}',
        3125: f'Failed to connect to the host {host} for payload remove_storage',
        3126: f'Failed to remove {storage_path} on host {host}',
        3127: f'Failed to connect to the host {host} for payload remove_dir',
        3128: f'Failed to remove {vm_path} on host {host}',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'shutdown_vm': f'Stop-VM -Name {vm_identifier} -TurnOff',
            'remove_vm': f'Remove-VM -Name {vm_identifier} -Force',
            'remove_storage': f'Remove-Item -Path {storage_path} -Force -Confirm:$false',
            'remove_dir': f'Remove-Item -LiteralPath {vm_path} -Force -Recurse'
        }

        ret = rcc.run(payloads['shutdown_vm'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('shutdown_vm', ret)

        ret = rcc.run(payloads['remove_vm'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('remove_vm', ret)

        ret = rcc.run(payloads['remove_storage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
        fmt.add_successful('remove_storage', ret)

        ret = rcc.run(payloads['remove_dir'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        fmt.add_successful('remove_dir', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    if status is False:
        return status, msg

    return True, f'1100: {messages[1100]}'

