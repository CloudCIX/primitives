"""
Primitive to Build and Delete directories on PodNet HA
"""

# stdlib
import json
import ipaddress
from pathlib import Path
from typing import Any, Dict, List, Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS, VALIDATION_ERROR, CONNECTION_ERROR
from cloudcix_primitives.utils import load_pod_config, SSHCommsWrapper, PodnetErrorFormatter
# local


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0


def build(path: str, config_file=None) -> Tuple[bool, str]:
    """
    description:
        Creates directory on PodNet HA.

    parameters:
        path:
            description: The path to be created on the PodNet
            type: string
            required: true
        config_file:
            description: The path to the config.json file. This will default to /opt/robot/config.json if not supplied.
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define messages
    messages = {
        1000: f'Successfully created directory {path} on both PodNet nodes.',
        3021: f'Failed to connect to the enabled PodNet node for create_path payload: ',
        3022: f'Failed to run create path payload on the enabled PodNet. Payload exited with status ',

        3031: f'Failed to connect to the disabled PodNet node for create_path payload: ',
        3032: f'Failed to run create path payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'create_path':     f"mkdir --parents {path}",
        }

        ret = rcc.run(payloads['create_path'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('create_path', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3030, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]


def read(path: str, config_file=None) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    description:
        Gets the status of the directory on PodNet HA.

    parameters:
        path:
            description: The path to be read on the PodNet
            type: string
            required: true
        config_file:
            description: The path to the config.json file
            type: string
            required: false
    return:
        description: |
            A list with 3 items: (1) a boolean status flag indicating if the
            read was successfull, (2) a dict containing the data as read from
            the both machines' current state and (3) the output or success message.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              file contents retrieved from both podnet nodes. May be None if nothing
              could be retrieved.
            properties:
              <podnet_ip>:
                description: The output from the command "stat <path>"
        message_list:
            description: A list of comma seperated messages recording any errors encountered during the request.
            type: array

    """
    # Define message
    messages = {
        1200: f'Successfully read directory {path} on both podnet nodes.',
        3221: f'Failed to connect to the enabled PodNet node for find_path payload: ',
        3222: f'Failed to run find path payload on the enabled PodNet. Payload exited with status ',

        3231: f'Failed to connect to the disabled PodNet node for find_path payload: ',
        3232: f'Failed to run find path payload on the disabled PodNet. Payload exited with status ',
    }

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, None, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[podnet_node] = {}

        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'find_path':     f"stat {path}",
        }

        ret = rcc.run(payloads['find_path'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1} : " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2} : " + messages[prefix+2])
        else:
            data_dict[podnet_node]['entry'] = ret["payload_message"].strip()
            fmt.add_successful('find_path', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval_enabled, msg_list_enabled, successful_payloads, data_dict = run_podnet(enabled, 3220, {}, {})

    retval_disabled, msg_list_disabled, successful_payloads, data_dict = run_podnet(disabled, 3230, successful_payloads, data_dict)

    msg_list = list()
    msg_list.extend(msg_list_enabled)
    msg_list.extend(msg_list_disabled)

    if not (retval_enabled and retval_disabled):
        return False, data_dict, msg_list
    else:
       return True, data_dict, (messages[1200])


def scrub(path: str, config_file=None) -> Tuple[bool, str]:
    """
    description:
        Removes directory on PodNet HA.

    parameters:
        path:
            description: The path to be removed on the PodNet
            type: string
            required: true
        config_file:
            description: The path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating the scrub was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully removed directory {path}',
        3121: f'Failed to connect to the enabled PodNet node for delete_path payload: ',
        3122: f'Failed to run delete_path payload on the enabled PodNet. Payload exited with status ',

        3131: f'Failed to connect to the disabled PodNet node for delete_path payload: ',
        3132: f'Failed to run delete_path payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'


    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'delete_directory':     f'rm --recursive --force {path}'
        }

        ret = rcc.run(payloads['delete_directory'])

        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('delete_directory', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3130, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]
