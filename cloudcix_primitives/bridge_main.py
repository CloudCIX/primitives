"""
Primitive for Public Subnet Bridge on PodNet
"""

# stdlib
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import comms_lsh, CHANNEL_SUCCESS
# local
from cloudcix_primitives.utils import (
    check_template_data,
    HostErrorFormatter,
    JINJA_ENV,
)

__all__ = [
    'build',
    'read',
    'scrub',
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

    up_script_path = f'/usr/local/bin/bridge_main_{bridge}_up.sh'
    down_script_path = f'/usr/local/bin/bridge_main_{bridge}_down.sh'
    service_file_path = f'/etc/systemd/system/bridge_main_{bridge}.service'

    # Define message
    messages = {
        1000: f'Successfully created and started bridge_main_{bridge}.service.',
        # Template
        3002: 'Failed to verify down.sh.j2 template data, One or more template fields are None',
        3003: 'Failed to verify up.sh.j2 template data, One or more template fields are None',
        3004: 'Failed to verify interface.service.sh.j2 template data, One or more template fields are None',
        # Payloads
        3021: 'Failed to connect to the local host for find_service payload: ',
        3022: 'Failed to connect to the local host for create_down_script payload: ',
        3023: 'Failed to run create_down_script payload on the local host. Payload exited with status ',
        3024: 'Failed to connect to the local host for create_up_script payload: ',
        3025: 'Failed to run create_up_script payload on the local host. Payload exited with status ',
        3026: 'Failed to connect to the local host for create_service_file payload: ',
        3027: 'Failed to run create_service_file payload on the local host. Payload exited with status ',
        3028: 'Failed to connect to the local host for reload_services payload: ',
        3029: 'Failed to run reload_services payload on the local host. Payload exited with status ',
        3030: 'Failed to connect to the local host for start_service payload: ',
        3031: 'Failed to run start_service payload on the local host. Payload exited with status ',

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
    template = JINJA_ENV.get_template('bridge_main/down.sh.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3002: {messages[3002]}'
    down_script = template.render(**template_data)
    # up script
    template = JINJA_ENV.get_template('bridge_main/up.sh.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3003: {messages[3003]}'
    up_script = template.render(**template_data)
    # service file
    template = JINJA_ENV.get_template('bridge_main/interface.service.j2')
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
            'find_service': f'systemctl status bridge_main_{bridge}.service',
            'start_service': f'systemctl restart bridge_main_{bridge}.service && '
                             f'systemctl enable bridge_main_{bridge}.service',
            'reload_services': 'systemctl daemon-reload',
        }

        ret = comms_lsh(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        create_service = True
        if ret["payload_code"] == SUCCESS_CODE:
            create_service = False
        fmt.add_successful('find_service', ret)

        if create_service:
            ret = comms_lsh(payloads['create_down_script'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
            fmt.add_successful('create_down_script', ret)

            ret = comms_lsh(payloads['create_up_script'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
            fmt.add_successful('create_up_script', ret)

            ret = comms_lsh(payloads['create_service_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
            fmt.add_successful('create_service_file', ret)

        ret = comms_lsh(payloads['reload_services'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 9}: {messages[prefix + 9]}'), fmt.successful_payloads
        fmt.add_successful('reload_services', ret)

        ret = comms_lsh(payloads['start_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 10}: {messages[prefix + 10]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 11}: {messages[prefix + 11]}'), fmt.successful_payloads
        fmt.add_successful('start_service', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host('localhost', 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]


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

    up_script_path = f'/usr/local/bin/bridge_main_{bridge}_up.sh'
    down_script_path = f'/usr/local/bin/bridge_main_{bridge}_down.sh'
    service_file_path = f'/etc/systemd/system/bridge_main_{bridge}.service'

    # Define message
    messages = {
        1200: f'Successfully read bridge_main_{bridge}.service on local host.',
        3221: 'Failed to connect to the local host for find_service payload: ',
        3222: f'Failed  to find serivce bridge_main_{bridge}.service, does not exists on local host',
        3223: 'Failed to connect to the local host for read_bridge payload: ',
        3224: 'Failed to run read_bridge payload on the local host. Payload exited with status ',
        3225: 'Failed to connect to the local host for read_down_script payload: ',
        3226: 'Failed to run read_down_script payload on the local host. Payload exited with status ',
        3227: 'Failed to connect to the local host for read_up_script payload: ',
        3228: 'Failed to run read_up_script payload on the local host. Payload exited with status ',
        3229: 'Failed to connect to the local host for read_service_file payload: ',
        3230: 'Failed to run read_service_file payload on the local host. Payload exited with status ',
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
            'find_service': f'systemctl status bridge_main_{bridge}.service',
            'read_bridge': f'ip link show {bridge}',
            'read_up_script': f'cat {up_script_path}',
            'read_down_script': f'cat {down_script_path}',
            'read_service_file': f'cat {service_file_path}',
        }

        ret = comms_lsh(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}')
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f'{prefix + 2}: {messages[prefix + 2]}')
        else:
            data_dict[host]['service'] = ret["payload_message"].strip()
            fmt.add_successful('find_service', ret)

        ret = comms_lsh(payloads['read_bridge'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f'{prefix + 3}: {messages[prefix + 3]}')
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f'{prefix + 4}: {messages[prefix + 4]}')
        else:
            data_dict[host]['bridge'] = ret["payload_message"].strip()
            fmt.add_successful('read_bridge', ret)

        ret = comms_lsh(payloads['read_down_script'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f'{prefix + 5}: {messages[prefix + 5]}')
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f'{prefix + 6}: {messages[prefix + 6]}')
        else:
            data_dict[host]['down_script'] = ret["payload_message"].strip()
            fmt.add_successful('read_down_script', ret)

        ret = comms_lsh(payloads['read_up_script'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f'{prefix + 7}: {messages[prefix + 7]}')
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f'{prefix + 8}: {messages[prefix + 8]}')
        else:
            data_dict[host]['up_script'] = ret["payload_message"].strip()
            fmt.add_successful('read_up_script', ret)

        ret = comms_lsh(payloads['read_service_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f'{prefix + 9}: {messages[prefix + 9]}')
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f'{prefix + 10}: {messages[prefix + 10]}')
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

    up_script_path = f'/usr/local/bin/bridge_main_{bridge}_up.sh'
    down_script_path = f'/usr/local/bin/bridge_main_{bridge}_down.sh'
    service_file_path = f'/etc/systemd/system/bridge_main_{bridge}.service'

    # Define message
    messages = {
        1100: f'Successfully scrubbed bridge_main_{bridge}.service on local host.',
        1101: f'bridge_main_{bridge}.service does not exists on local host',

        3121: 'Failed to connect to the local host for find_service payload: ',
        3122: 'Failed to connect to the local host for stop_service payload: ',
        3123: 'Failed to run stop_service payload on the local host. Payload exited with status ',
        3124: 'Failed to connect to the local host for check_up_file payload: ',
        3125: 'Failed to run check_up_file payload on the local host. Payload exited with status ',
        3126: 'Failed to connect to the local host for delete_up_file payload: ',
        3127: 'Failed to run delete_up_file payload on the local host. Payload exited with status ',
        3128: 'Failed to connect to the local host for check_down_file payload: ',
        3129: 'Failed to run check_down_file payload on the local host. Payload exited with status ',
        3130: 'Failed to connect to the local host for delete_up_file payload: ',
        3131: 'Failed to run delete_down_file payload on the local host. Payload exited with status ',
        3132: 'Failed to connect to the local host for check_service_file payload: ',
        3133: 'Failed to run check_service_file payload on the local host. Payload exited with status ',
        3134: 'Failed to connect to the local host for delete_up_file payload: ',
        3135: 'Failed to run delete_service_file payload on the local host. Payload exited with status ',
        3136: 'Failed to connect to the local host for reload_services payload: ',
        3137: 'Failed to run reload_services payload on the local host. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # define payloads
        payloads = {
            'find_service': f'systemctl status bridge_main_{bridge}.service',
            'stop_service': f'systemctl stop bridge_main_{bridge}.service && '
                            f'systemctl disable bridge_main_{bridge}.service',
            'check_up_file': f'if [ -f "{up_script_path}" ]; then exit 0; else exit 1; fi',
            'delete_up_file': f'rm --force {up_script_path}',
            'check_down_file': f'if [ -f "{down_script_path}" ]; then exit 0; else exit 1; fi',
            'delete_down_file': f'rm --force {down_script_path}',
            'check_service_file': f'if [ -f "{service_file_path}" ]; then exit 0; else exit 1; fi',
            'delete_service_file': f'rm --force {service_file_path}',
            'reload_services': 'systemctl daemon-reload',
        }

        ret = comms_lsh(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 1}: {messages[prefix + 1]}'), fmt.successful_payloads
        stop_service = True
        if ret["payload_code"] != SUCCESS_CODE:
            stop_service = False
            fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        fmt.add_successful('find_service', ret)

        if stop_service is True:
            ret = comms_lsh(payloads['stop_service'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 2}: {messages[prefix + 2]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 3}: {messages[prefix + 3]}'), fmt.successful_payloads
            fmt.add_successful('stop_service', ret)

        ret = comms_lsh(payloads['check_up_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 4}: {messages[prefix + 4]}'), fmt.successful_payloads
        delete_up_file = True
        if ret["payload_code"] != SUCCESS_CODE:
            delete_up_file = False
            fmt.payload_error(ret, f'{prefix + 5}: {messages[prefix + 5]}'), fmt.successful_payloads
        fmt.add_successful('check_up_file', ret)

        if delete_up_file is True:
            ret = comms_lsh(payloads['delete_up_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 6}: {messages[prefix + 6]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 7}: {messages[prefix + 7]}'), fmt.successful_payloads
            fmt.add_successful('delete_up_file', ret)

        ret = comms_lsh(payloads['check_down_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 8}: {messages[prefix + 8]}'), fmt.successful_payloads
        delete_down_file = True
        if ret["payload_code"] != SUCCESS_CODE:
            delete_down_file = False
            fmt.payload_error(ret, f'{prefix + 9}: {messages[prefix + 9]}'), fmt.successful_payloads
        fmt.add_successful('check_down_file', ret)

        if delete_down_file is True:
            ret = comms_lsh(payloads['delete_down_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 10}: {messages[prefix + 10]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 11}: {messages[prefix + 11]}'), fmt.successful_payloads
            fmt.add_successful('delete_down_file', ret)

        ret = comms_lsh(payloads['check_service_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 12}: {messages[prefix + 12]}'), fmt.successful_payloads
        delete_service_file = True
        if ret["payload_code"] != SUCCESS_CODE:
            delete_service_file = False
            fmt.payload_error(ret, f'{prefix + 13}: {messages[prefix + 13]}'), fmt.successful_payloads
        fmt.add_successful('check_service_file', ret)

        if delete_service_file is True:
            ret = comms_lsh(payloads['delete_service_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f'{prefix + 14}: {messages[prefix + 14]}'), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f'{prefix + 15}: {messages[prefix + 15]}'), fmt.successful_payloads
            fmt.add_successful('delete_service_file', ret)

        ret = comms_lsh(payloads['reload_services'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix + 16}: {messages[prefix + 16]}'), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix + 17}: {messages[prefix + 17]}'), fmt.successful_payloads
        fmt.add_successful('reload_services', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host('localhost', 3120, {})
    if status is False:
        return status, msg

    return True, messages[1100]
