"""
Primitive for Public Subnet Bridge on PodNet
"""

# stdlib
import ipaddress
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import comms_lsh, CHANNEL_SUCCESS
# local
from cloudcix_primitives.utils import (
    JINJA_ENV,
    check_template_data,
    HostErrorFormatter,
)

__all__ = [
    'build',
    'read',
]

SUCCESS_CODE = 0


def build(
        address_range: str,
        bridge: str,
) -> Tuple[bool, str]:
    """
    description:
        Configures and starts service that creates a subnet bridge on the PodNet.

    parameters:
        address_range:
            description: The public subnet address range (region assignment) to be defined on the bridge
            type: str
            required: true
        bridge:
            description: Name of the bridge to be created on the PodNet, eg. BM123
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    up_script_path = f'/usr/local/bin/bridgemain_{bridge}_up.sh'
    down_script_path = f'/usr/local/bin/bridgemain_{bridge}_down.sh'
    service_file_path = f'/etc/systemd/system/bridgemain_{bridge}.service'

    # Define message
    messages = {
        1000: f'Successfully created and started bridgemain_{bridge}.service.',
        # Template
        3002: 'Failed to verify down.sh.j2 template data, One or more template fields are None',
        3003: 'Failed to verify up.sh.j2 template data, One or more template fields are None',
        3004: 'Failed to verify interface.service.sh.j2 template data, One or more template fields are None',
        # Payloads
        3021: 'Failed to connect to the local host for find_service payload: ',
        3022: 'Failed to run find_service_payload on the local host. Payload exited with status ',
        3023: 'Failed to connect to the local host for create_down_script payload: ',
        3024: 'Failed to run create_down_script payload on the local host. Payload exited with status ',
        3025: 'Failed to connect to the local host for create_up_script payload: ',
        3026: 'Failed to run create_up_script payload on the local host. Payload exited with status ',
        3027: 'Failed to connect to the local host for create_service_file payload: ',
        3028: 'Failed to run create_service_file payload on the local host. Payload exited with status ',
        3029: 'Failed to connect to the local host for reload_services payload: ',
        3030: 'Failed to run reload_services payload on the local host. Payload exited with status ',
        3031: 'Failed to connect to the local host for start_service payload: ',
        3032: 'Failed to run start_service payload on the local host. Payload exited with status ',

    }

    # template data for required script files
    template_data = {
        'address_range': address_range,
        'bridge': bridge,
        'down_script_path': down_script_path,
        'up_script_path': up_script_path,
    }

    # Templates
    # down script
    template = JINJA_ENV.get_template('bridgemain/down.sh.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3002: {messages[3002]}'
    down_script = template.render(**template_data)
    # up script
    template = JINJA_ENV.get_template('bridgemain/up.sh.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3003: {messages[3003]}'
    up_script = template.render(**template_data)
    # service file
    template = JINJA_ENV.get_template('bridgemain/interface.service.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3004: {messages[3004]}'
    service_file = template.render(**template_data)

    def run_host(host, prefix, successful_payloads):
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        payloads = {
            'create_down_script': "\n".join([
                f'tee {down_script_path} <<EOF && chmod 744 {down_script_path}',
                down_script,
                "EOF"
            ]),
            'create_up_script': "\n".join([
                f'tee {up_script_path} <<EOF && chmod 744 {up_script_path}',
                up_script,
                "EOF"
            ]),
            'create_service_file': "\n".join([
                f'tee {service_file_path} <<EOF && chmod 744 {service_file_path}',
                service_file,
                "EOF"
            ]),
            'find_service': f'systemctl status bridgemain_{bridge}.service',
            'start_service': f'systemctl restart bridgemain_{bridge}.service && '
                             f'systemctl enable bridgemain_{bridge}.service',
            'reload_services': 'systemctl daemon-reload',
        }

        ret = comms_lsh(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        create_service = True
        if ret["payload_code"] != SUCCESS_CODE:
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
        else:
            create_service = False
        fmt.add_successful('find_service', ret)

        if create_service:
            ret = comms_lsh(payloads['create_down_script'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
            fmt.add_successful('create_down_script', ret)

            ret = comms_lsh(payloads['create_up_script'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
            fmt.add_successful('create_up_script', ret)

            ret = comms_lsh(payloads['create_service_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
            fmt.add_successful('create_service_file', ret)

        ret = comms_lsh(payloads['reload_services'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 9}: {messages[prefix + 9]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 10}: {messages[prefix + 10]}'), fmt.successful_payloads
        fmt.add_successful('reload_services', ret)

        ret = comms_lsh(payloads['start_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 11}: {messages[prefix + 11]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 12}: {messages[prefix + 12]}'), fmt.successful_payloads
        fmt.add_successful('start_service', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host('localhost', 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]


def scrub(
        bridge: str,
) -> Tuple[bool, str]:
    """
    description:
        Scrubs the service and deletes the subnet bridge on the local host .

    parameters:
        bridge:
            description: Name of the bridge to be created on the PodNet, eg. BM123
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag stating if the scrub was successful or not and
            the output or error message.
        type: tuple
    """

    up_script_path = f'/usr/local/bin/bridgemain_{bridge}_up.sh'
    down_script_path = f'/usr/local/bin/bridgemain_{bridge}_down.sh'
    service_file_path = f'/etc/systemd/system/bridgemain_{bridge}.service'

    # Define message
    messages = {
        1100: f'Successfully scrubbed bridgemain_{bridge}.service on local host.',
        1101: f'bridgemain_{bridge}.service does not exists on local host',

        3121: f'Failed to connect to the local host for find_service payload: ',
        3122: f'Failed to connect to the local host for stop_service payload: ',
        3123: f'Failed to run stop_service payload on the local host. Payload exited with status ',
        3124: f'Failed to connect to the local host for delete_files payload: ',
        3125: f'Failed to run delete_files payload on the local host. Payload exited with status ',
        3126: f'Failed to connect to the local host for delete_bridge payload: ',
        3127: f'Failed to run delete_bridge payload on the local host. Payload exited with status ',
        3128: f'Failed to connect to the local host for reload_services payload: ',
        3129: f'Failed to run reload_services payload on the local host. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # define payloads
        payloads = {
            'find_service': f'systemctl status bridgemain_{bridge}.service',
            'stop_service': f'systemctl stop bridgemain_{bridge}.service && '
                            f'systemctl disable bridgemain_{bridge}.service',
            'delete_files': f'rm --force {up_script_path} {down_script_path} {service_file_path}',
            'reload_services': 'systemctl daemon-reload',
            'delete_bridge': f'ip link del {bridge}',
        }

        ret = comms_lsh(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        delete_service = True
        if ret["payload_code"] != SUCCESS_CODE:
            delete_service = False
            fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        fmt.add_successful('find_service', ret)

        if delete_service is True:
            ret = comms_lsh(payloads['stop_service'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
            fmt.add_successful('stop_service', ret)

            ret = comms_lsh(payloads['delete_files'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
            fmt.add_successful('delete_files', ret)

            ret = comms_lsh(payloads['delete_bridge'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
            fmt.add_successful('delete_files', ret)

        ret = comms_lsh(payloads['reload_services'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 9}: {messages[prefix + 9]}'), fmt.successful_payloads
        fmt.add_successful('reload_services', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host('localhost', 3120, {})
    if status is False:
        return status, msg

    return True, messages[1100]


def read(
        bridge: str,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description:
        Reads the service and the vlan tagged bridge on the host .

    parameters:
        bridge:
            description: Name of the bridge to be created on the PodNet, eg. BM123
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

    up_script_path = f'/usr/local/bin/bridgemain_{bridge}_up.sh'
    down_script_path = f'/usr/local/bin/bridgemain_{bridge}_down.sh'
    service_file_path = f'/etc/systemd/system/bridgemain_{bridge}.service'

    # Define message
    messages = {
        1200: f'Successfully read bridgemain_{bridge}.service on local host.',
        1201: f'bridgemain_{bridge}.service does not exists on local host',

        3221: 'Failed to connect to the local host for find_service payload: ',
        3222: f'Failed to connect to the local host for read_bridge payload: ',
        3223: f'Failed to run read_bridge payload on the local host. Payload exited with status ',
        3224: f'Failed to connect to the local host for read_down_script payload: ',
        3225: f'Failed to run read_down_script payload on the local host. Payload exited with status ',
        3226: f'Failed to connect to the local host for read_up_script payload: ',
        3227: f'Failed to run read_up_script payload on the local host. Payload exited with status ',
        3228: f'Failed to connect to the local host for read_service_file payload: ',
        3229: f'Failed to run read_service_file payload on the local host. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[host] = {}
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # define payloads
        payloads = {
            'find_service': f'systemctl status bridgemain_{bridge}.service',
            'read_bridge': f'ip link show {bridge}',
            'read_up_script': f'cat {up_script_path}',
            'read_down_script': f'cat {down_script_path}',
            'read_service_file': f'cat {service_file_path}',
        }

        ret = comms_lsh(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix + 1}: " + messages[prefix + 1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"1201: " + messages[1201])
        else:
            data_dict[host]['service'] = ret["payload_message"].strip()
            fmt.add_successful('find_service', ret)

        ret = comms_lsh(payloads['read_bridge'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix + 2}: " + messages[prefix + 2])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix + 3}: " + messages[prefix + 3])
        else:
            data_dict[host]['bridge'] = ret["payload_message"].strip()
            fmt.add_successful('read_bridge', ret)

        ret = comms_lsh(payloads['read_down_script'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix + 4}: " + messages[prefix + 4])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix + 5}: " + messages[prefix + 5])
        else:
            data_dict[host]['down_script'] = ret["payload_message"].strip()
            fmt.add_successful('read_down_script', ret)

        ret = comms_lsh(payloads['read_up_script'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix + 6}: " + messages[prefix + 6])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix + 7}: " + messages[prefix + 7])
        else:
            data_dict[host]['up_script'] = ret["payload_message"].strip()
            fmt.add_successful('read_up_script', ret)

        ret = comms_lsh(payloads['read_service_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix + 8}: " + messages[prefix + 8])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix + 9}: " + messages[prefix + 9])
        else:
            data_dict[host]['service_file'] = ret["payload_message"].strip()
            fmt.add_successful('read_file_service', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host('localhost', 3220, {}, {})
    message_list = list()
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [messages[1200]]
