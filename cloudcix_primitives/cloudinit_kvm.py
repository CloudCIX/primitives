"""
Primitive for Cloud-init VM on KVM hosts
"""

# stdlib
import time
from datetime import datetime
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
    'quiesce',
    'read',
    'restart',
    'scrub',
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
        1000: f'Successfully created domain {domain} on Host {host}',
        # validations
        3011: 'Invalid "gateway_interface", The "gateway_interface" cannot be None',
        3012: 'Invalid "gateway_interface", The "gateway_interface" must be a dictionary object',
        3013: 'Invalid "gateway_interface", one of the field is invalid, Errors: ',
        3014: 'Invalid "primary_storage", The "primary_storage" is required',
        3015: 'Invalid "primary_storage", The "primary_storage" is must be a string type',
        3016: 'Invalid "primary_storage", The "primary_storage" must be a name of the storage file with extension',
        3017: 'Invalid "primary_storage", The "primary_storage" can only be either .img or .qcow2 file formats',
        3018: 'Invalid "secondary_interfaces", The "secondary_interfaces" must be a list object',
        3019: 'Invalid "secondary_interfaces", one of the field is invalid, Errors: ',
        3020: 'Invalid "secondary_storages", every item in "secondary_storages" must be of string type',
        3021: 'Invalid "secondary_storages", one or more items are invalid, Errors: ',
        # payload execution
        3031: f'Failed to connect to the host {host} for the payload read_storage_file',
        3032: f'Failed to create domain, the requested domain {domain} already exists on the Host {host}',
        3033: f'Failed to connect the Host {host} for the payload copy_cloudimage',
        3034: f'Failed to copy cloud image {cloudimage} to the domain directory {domain_path}{primary_storage}'
              f' on Host {host}.',
        3035: f'Failed to connect the Host {host} for the payload resize_copied_file',
        3036: f'Failed to resize the copied storage image to {size}GB on Host {host}',
        3037: f'Failed to connect the Host {host} for the payload virt_install_cmd',
        3038: f'Failed to create domain {domain} on Host {host}'
    }

    messages_list = []
    validated = True

    # validate gateway_interface
    def validate_gateway_interface(gif, msg_index):
        valid_gif = True
        if gif is None:
            messages_list.append(f'{messages[msg_index]}: {messages[msg_index]}')
            return False

        if type(gif) is not dict:
            messages_list.append(f'{messages[msg_index + 1]}: {messages[msg_index + 1]}')
            return False

        controller = KVMInterface(gif)
        success, errs = controller()
        if success is False:
            valid_gif = False
            messages_list.append(f'{messages[msg_index + 2]}: {messages[msg_index + 2]} {";".join(errs)}')
        return valid_gif

    validated = validate_gateway_interface(gateway_interface, 3011)

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
        elif ps_items[1] not in ('img', 'qcow2'):
            messages_list.append(f'{messages[msg_index + 3]}: {messages[msg_index + 3]}')
            return False
        return True

    validated = validate_primary_storage(primary_storage, 3014)

    # validate secondary interfaces
    def validate_secondary_interfaces(sifs, msg_index):
        if type(sifs) is not list:
            messages_list.append(f'{messages[msg_index]}: {messages[msg_index]}')
            return False

        errors = []
        valid_sifs = True
        for interface in secondary_interfaces:
            controller = KVMInterface(interface)
            success, errs = controller()
            if success is False:
                valid_sifs = False
                errors.extend(errs)
        if valid_sifs is False:
            messages_list.append(f'{messages[msg_index + 1]}: {messages[msg_index + 1]} {";".join(errors)}')

        return valid_sifs

    if secondary_interfaces:
        validated = validate_secondary_interfaces(secondary_interfaces, 3018)
    else:
        secondary_interfaces = []

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
                elif stg_items[1] not in ('img', 'qcow2'):
                    errors.append(
                        f'Invalid secondary_storage {storage}, it can only be either .img or .qcow2 file format',
                    )
                    valid_sstgs = False

        if valid_sstgs is False:
            messages_list.append(f'{messages[msg_index + 1]}: {messages[msg_index + 1]} {";".join(errors)}')

        return valid_sstgs

    if secondary_storages:
        validated = validate_secondary_storages(secondary_storages, 3020)
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
        # Virt-install automatically connects to the guest VM console for any interactions and waits until VM is reboots
        # Don't automatically try to connect to the guest console. The VM will be created without asking for any
        # interaction and 'virt-install' will exit quickly.
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
            # check if vm exists already
            'read_domain_info': f'virsh dominfo {domain} ',
            'copy_cloudimage': f'cp {cloudimage} {domain_path}{primary_storage}',
            'resize_copied_file': f'qemu-img resize {domain_path}{primary_storage} {size}G',
            'virt_install_cmd': cmd,
        }

        ret = rcc.run(payloads['read_domain_info'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            # if vm exists already then we should not build it again,
            # by mistake same vm is requested to build again so return with error
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        fmt.add_successful('read_domain_info', ret)

        ret = rcc.run(payloads['copy_cloudimage'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        fmt.add_successful('copy_cloudimage', ret)

        ret = rcc.run(payloads['resize_copied_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
        fmt.add_successful('resize_copied_file', ret)

        ret = rcc.run(payloads['virt_install_cmd'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        fmt.add_successful('virt_install_cmd', ret)

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
            description: Unique identification name for the Cloud-init VM on the KVM Host.
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
        3427: f'Failed to connect to the host {host} for payload destroy_domain',
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
            'read_domstate_0': f'virsh domstate {domain} ',
            'shutdown_domain': f'virsh shutdown {domain} ',
            'read_domstate_n': f'virsh domstate {domain} ',
            'destroy_domain': f'virsh destroy {domain} ',  # force shutdown = destroy
        }

        # first read the state before shutdown the domain
        ret = rcc.run(payloads['read_domstate_0'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        quiesced = False
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            if 'shut off' in ret["payload_message"].strip():
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

        # Since shutdown is run make sure it is in shutoff state, so read the state until it is shutoff
        # for max 300 seconds
        start_time = datetime.now()
        shutoff = False
        attempt = 1
        while (datetime.now() - start_time).total_seconds() < 300 and shutoff is False:
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
                if 'shut off' in ret["payload_message"].strip():
                    shutoff = True
                else:
                    # wait interval is 0.5 seconds
                    time.sleep(0.5)
            attempt += 1
            fmt.add_successful('read_domstate_n', ret)

        # After 300 seconds still domain is not shut off then force off it
        if shutoff is False:
            ret = rcc.run(payloads['destroy_domain'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
            fmt.add_successful('destroy_domain', ret)

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
            description: Unique identification name for the Cloud-init VM on the KVM Host.
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
        3221: f'Failed to connect to the host {host} for payload domain_info',
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


def restart(
        domain: str,
        host: str,
) -> Tuple[bool, str]:
    """
    description: Restarts the VM

    parameters:
        domain:
            description: Unique identification name for the Cloud-init VM on the KVM Host.
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
            'read_domstate_0': f'virsh domstate {domain} ',
            'restart_domain': f'virsh start {domain} ',
            'read_domstate_n': f'virsh domstate {domain} ',
        }

        # First check if dommain is already running or not
        ret = rcc.run(payloads['read_domstate_0'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        running = False
        if ret["payload_code"] != SUCCESS_CODE:
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            if 'running' in ret["payload_message"].strip():
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
                if 'running' in ret["payload_message"].strip():
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
        domain_path: str,
        host: str,
        primary_storage: str,
) -> Tuple[bool, str]:
    """
    description: Removes the VM

    parameters:
        domain:
            description: Unique identification name for the Cloud-init VM on the KVM Host.
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
    # Define message
    messages = {
        1100: f'Successfully scrubbed domain {domain} on host {host}',
        3121: f'Failed to connect to the host {host} for payload read_domstate',
        3122: f'Failed to read  domain {domain} state from host {host}',
        3123: f'Failed to connect to the host {host} for payload destroy_domain',
        3124: f'Failed to destroy domain {domain} on host {host}',
        3125: f'Failed to connect to the host {host} for payload undefine_domain',
        3126: f'Failed to undefine domain {domain} on host {host}',
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
            'read_domstate': f'virsh domstate {domain} ',
            'destroy_domain': f'virsh destroy {domain} ',
            'undefine_domain': f'virsh undefine {domain} --nvram ',
            'remove_primary_storage': f'rm --force {domain_path}{primary_storage}'
        }

        ret = rcc.run(payloads['read_domstate'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        shutoff = False
        if ret["payload_code"] != SUCCESS_CODE:
            # check if already undefined/remove
            if f'failed to get domain \'{domain}\'' in ret["payload_error"].strip():
                return True, "", fmt.successful_payloads
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            if 'shut off' in ret["payload_message"].strip():
                shutoff = True
        fmt.add_successful('read_domstate', ret)

        if shutoff is False:
            ret = rcc.run(payloads['destroy_domain'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
            fmt.add_successful('destroy_domain', ret)

        ret = rcc.run(payloads['undefine_domain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
        fmt.add_successful('undefine_domain', ret)

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
