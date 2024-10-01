"""
Primitive to Build, Read and Scrub cloud-init userdata/metadata payloads on PodNet HA
"""

# stdlib
import json
import ipaddress
from pathlib import Path
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS, VALIDATION_ERROR, CONNECTION_ERROR
from cloudcix_primitives.utils import load_pod_config, SSHCommsWrapper, PodnetErrorFormatter
# local


__all__ = [
    'build',
    'scrub',
    'read',
]

SUCCESS_CODE = 0


def build(
        domain_path: str,
        metadata: dict,
        userdata: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Creates cloud-init user data and meta data files for a virtual machine on PodNet HA.

    parameters:
        domain_path:
            description: |
                path to the virtual machine's cloud-init directory.
                This must be the full path, up to and including the
                metaddata version component.
            type: string
            required: true
        metadata:
          description: data structure that contains the machine's metadata
          type: object
          required: true
          properties:
            instance_id:
              type: string
              required: true
              description: | libvirt domain name for VM. Typically composed from
                             numerical project ID and VM ID as follows:
                             `<project_id>_<domain_id>`.
            network:
              type: object
              required: true
              description: |
                  the VM's network configuration. This is a dictionary representing a netplan v2
                  configuration. Such a dictionary can be obtained by
                  deserializing a netplan v2 configuration file using a YAML
                  parser.
        config_file:
            description: path to the PodNet config.json file
            type: string
            required: false
        userdata:
            description: the cloud-init user data payload to pass into the virtual machine
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created {domain_path}/metadata and {domain_path}/userdata on both PodNet nodes.',
        3021: f'3021: Failed to connect to the enabled PodNet for create_metadata payload: ',
        3022: f'3022: Failed to run create_metadata payload on the enabled PodNet. Payload exited with status ',
        3023: f'3023: Failed to connect to the enabled PodNet for create_userdata payload: ',
        3024: f'3024: Failed to run create_userdata payload on the enabled PodNet. Payload exited with status ',

        3031: f'3021: Failed to connect to the disabled PodNet for create_metadata payload: ',
        3032: f'3022: Failed to run create_metadata payload on the disabled PodNet. Payload exited with status ',
        3033: f'3023: Failed to connect to the disabled PodNet for create_userdata payload: ',
        3034: f'3024: Failed to run create_userdata payload on the disabled PodNet. Payload exited with status ',
    }

    metadata_json = json.dumps(
        metadata,
        indent=1,
        sort_keys=True,
    )

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
            'create_metadata': "\n".join([
                f'tee {domain_path}/metadata <<EOF',
                metadata_json,
                "EOF"
            ]),

            'create_userdata': "\n".join([
                    f'tee {domain_path}/userdata <<EOF',
                    userdata,
                    "EOF"
                    ])
        }


        ret = rcc.run(payloads['create_metadata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('create_metadata', ret)

        ret = rcc.run(payloads['create_userdata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('create_userdata', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3030, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]


def scrub(
        domain_path: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Removes cloud-init user data and meta data files for a virtual machine on PodNet HA.

    parameters:
        domain_path:
            description: path to the virtual machine's cloud-init directory.
                         This must be the full path, up to and including the
                         version component.
            type: string
            required: true
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the scrub was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1100: f'Successfully removed {domain_path}/metadata and {domain_path}/userdata on both PodNet nodes.',
        3121: f'Failed to connect to the enabled PodNet for remove_metadata payload: ',
        3122: f'Failed to run remove_metadata payload on the enabled PodNet. Payload exited with status ',
        3123: f'Failed to connect to the enabled PodNet for remove_userdata payload: ',
        3124: f'Failed to run remove_userdata payload on the enabled PodNet. Payload exited with status ',

        3131: f'Failed to connect to the disabled PodNet for remove_metadata payload: ',
        3132: f'Failed to run remove_metadata payload on the disabled PodNet. Payload exited with status ',
        3133: f'Failed to connect to the disabled PodNet for remove_userdata payload: ',
        3134: f'Failed to run remove_userdata payload on the disabled PodNet. Payload exited with status ',
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
            'remove_metadata': f'rm -f {domain_path}/userdata',
            'remove_userdata': f'rm -f {domain_path}/metadata',
        }


        ret = rcc.run(payloads['remove_metadata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('remove_metadata', ret)

        ret = rcc.run(payloads['remove_userdata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('remove_userdata', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3130, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1100]

def read(
        domain_path: str,
        config_file: None
) -> Tuple[bool, dict, str]:
    """
    description:
        Reads cloud-init user data and meta data files for a virtual machine on
        PodNet HA (if any) and returns them.

    parameters:
        domain_path:
            description: |
                path to the virtual machine's cloud-init directory.  This must
                be the full path, up to and including the version component.
            type: string
            required: true
        config_file:
            description: path to the config.json file
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
                description: dict structure holding user data from machine <podnet_ip>
                  type: object
                  userdata:
                    description: |
                      The contents of the `userdata` file at domain_path. May be
                      None upon any read errors.
                    type: string
                  metadata:
                    type: string
                    description: |
                      The contents of the `metadata` file at domain_path. May be
                      None upon any read errors.
    """

    # Define message
    messages = {
        1200: f'1200: Successfully retrieved {domain_path}/, {domain_path}/metadata and {domain_path}/userdata from both PodNet nodes.',
        3221: f'Failed to connect to the enabled PodNet for read_metadata payload: ',
        3222: f'Failed to run read_metadata payload on the enabled PodNet. Payload exited with status ',
        3223: f'Failed to connect to the enabled PodNet for read_userdata payload: ',
        3224: f'Failed to read_userdata payload on the enabled PodNet. Payload exited with status ',

        3231: f'Failed to connect to the disabled PodNet for read_metadata payload: ',
        3232: f'Failed to run read_metadata payload on the disabled PodNet. Payload exited with status ',
        3233: f'Failed to connect to the disabled PodNet for read_userdata payload: ',
        3234: f'Failed to read_userdata payload on the disabled PodNet. Payload exited with status ',
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
            'read_userdata': f'cat {domain_path}/userdata',
            'read_metadata': f'cat {domain_path}/metadata'
        }
        
        ret = rcc.run(payloads['read_metadata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1} : " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2} : " + messages[prefix+2])
        else:
            data_dict[podnet_node]['metadata'] = ret["payload_message"].strip()
            fmt.add_successful('read_metadata', ret)

        ret = rcc.run(payloads['read_userdata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+3} : " + messages[prefix+3])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+4} : " + messages[prefix+4])
        else:
            data_dict[podnet_node]['userdata'] = ret["payload_message"].strip()
            fmt.add_successful('read_userdata', ret)


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
