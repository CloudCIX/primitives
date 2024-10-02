"""
Primitive to Build, Read and Scrub nginx for cloud-init userdata/metadata delivery on PodNet HA
"""
# 3rd party modules
import jinja2
# stdlib
import json
import ipaddress
import os
from pathlib import Path
from textwrap import dedent
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS, VALIDATION_ERROR, CONNECTION_ERROR
# local
from cloudcix_primitives.utils import load_pod_config, SSHCommsWrapper, PodnetErrorFormatter


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0

template_path = os.path.join(os.path.dirname(__file__), 'templates', __name__.split(".").pop())

def build(
        namespace: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Configures and starts an nginx instance for serving cloud-init userdata/metadata inside a VRF network name space on a PodNet node.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        config_file:
            description: |
                path to the config.json file. Defaults to /opt/robot/config.json
                if unspecified.
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    nginx_config_path = f'/etc/netns/{namespace}/nginx.conf'
    pidfile= f'/etc/netns/{namespace}/nginx.pid'

    # Define message
    messages = {
        1000: f'Successfully created {nginx_config_path} and started nginx process on both PodNet nodes.',
        3019: f'Failed to render jinja2 template for {nginx_config_path}',

        3021: f'Failed to connect to the enabled PodNet for create_config payload: ',
        3022: f'Failed to run create_config payload on the enabled PodNet. Payload exited with status ',
        3023: f'Failed to connect to the enabled PodNet for find_process_payload: ',
        3024: f'Failed to connect to the enabled PodNet for start_nginx payload: ',
        3025: f'Failed to run start_nginx payload on the enabled PodNet. Payload exited with status ',
        3026: f'Failed to run start_nginx payload on the enabled PodNet: Stderr not empty. Payload exited with status ',
        3027: f'Failed to connect to the enabled PodNet for reload_nginx payload: ',
        3028: f'Failed to run reload_nginx payload on the enabled PodNet. Payload exited with status ',

        3051: f'Failed to connect to the disabled PodNet for create_config payload: ',
        3052: f'Failed to run create_config payload on the disabled PodNet. Payload exited with status ',
        3053: f'Failed to connect to the disabled PodNet for find_process_payload: ',
        3054: f'Failed to connect to the disabled PodNet for start_nginx payload: ',
        3055: f'Failed to run start_nginx payload on the disabled PodNet. Payload exited with status ',
        3056: f'Failed to run start_nginx payload on the disabled PodNet: Stderr not empty. Payload exited with status ',
        3057: f'Failed to connect to the disabled PodNet for reload_nginx payload: ',
        3058: f'Failed to run reload_nginx payload on the disabled PodNet. Payload exited with status ',

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

    try:
      jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(
          os.path.join(template_path))
      )
      template = jenv.get_template("nginx.conf.j2")

      nginx_conf = template.render(
          namespace=namespace,
          pidfile=pidfile
      )
    except Exception as e:
        return False, messages[3019]


    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        nginx_config_path_grepsafe = nginx_config_path.replace('.', '\.')

        payloads = {
            'create_config': "\n".join([
                f'tee {nginx_config_path} <<EOF',
                nginx_conf,
                "EOF"
            ]),
            'find_process': "ps auxw | grep nginx | grep -v grep | grep '%s' | awk '{print $2}'" % nginx_config_path_grepsafe,
            'start_nginx': f'ip netns exec {namespace} nginx -c {nginx_config_path}',
            'reload_nginx': 'kill -HUP %s',
        }

        ret = rcc.run(payloads['create_config'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('create_config', ret)

        ret = rcc.run(payloads['find_process'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        start_nginx = True
        if ret["payload_code"] == SUCCESS_CODE:
            if ret["payload_message"] != "":
                # No need to start nginx if it runs already
                start_nginx = False
                payloads['reload_nginx'] = payloads['reload_nginx'] % ret['payload_message'].strip()
        fmt.add_successful('find_process', ret)

        if start_nginx:
            ret = rcc.run(payloads['start_nginx'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            # nginx will ocassionally start if there are less than serious problems, but it will repart them on
            # standard error. Therefore we fail if there's anything on stderr.
            if ret["payload_error"] != "":
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            fmt.add_successful('start_nginx', ret)
        else:
            ret = rcc.run(payloads['reload_nginx'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
            fmt.add_successful('reload_nginx', ret)


        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg




    return True, messages[1000]


def scrub(
        namespace: str,
        config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Removes an nginx instance for serving cloud-init userdata/metadata from a VRF network name space

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        config_file:
            description: |
                path to the config.json file. Defaults to /opt/robot/config.json
                if unspecified.
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    nginx_config_path = f'/etc/netns/{namespace}/nginx.conf'
    pidfile= f'/etc/netns/{namespace}/nginx.pid'

    # Define message
    messages = {
        1100: f'1100: Successfully stopped nginx process and deleted {nginx_config_path}.',

        3121: f'Failed to connect to the enabled PodNet for find_proces payload: ',
        3122: f'Failed to connect to the enabled PodNet for stop_nginx payload: ',
        3123: f'Failed to run stop_nginx payload on the enabled PodNet. Payload exited with status ',
        3124: f'Failed to connect to the enabled PodNet for remove_config payload: ',
        3125: f'Failed to run remove_config payload on the enabled PodNet. Payload exited with status ',
        3126: f'Failed to connect to the enabled PodNet for remove_pidfile payload: ',
        3127: f'Failed to run remove_pidfile payload on the enabled PodNet. Payload exited with status ',

        3151: f'Failed to connect to the disabled PodNet for find_proces payload: ',
        3152: f'Failed to connect to the disabled PodNet for stop_nginx payload: ',
        3153: f'Failed to run stop_nginx payload on the disabled PodNet. Payload exited with status ',
        3154: f'Failed to connect to the disabled PodNet for remove_config payload: ',
        3155: f'Failed to run remove_config payload on the disabled PodNet. Payload exited with status ',
        3156: f'Failed to connect to the disabled PodNet for remove_pidfile payload: ',
        3157: f'Failed to run remove_pidfile payload on the disabled PodNet. Payload exited with status ',
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

        nginx_config_path_grepsafe = nginx_config_path.replace('.', '\.')

        payloads = {
            'find_process':  "ps auxw | grep nginx | grep -v grep | grep '%s' | awk '{print $2}'" % nginx_config_path_grepsafe,
            'remove_config': f'rm -f {nginx_config_path}',
            'remove_pidfile': f'rm -f {pidfile}',
            'stop_nginx':    'kill -TERM %s',
        }

        ret = rcc.run(payloads['find_process'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        stop_nginx = False
        if ret["payload_code"] == SUCCESS_CODE:
            if ret["payload_message"] != "":
                # No need to start nginx if it runs already
                stop_nginx = True
                payloads['stop_nginx'] = payloads['stop_nginx'] % ret['payload_message'].strip()
        fmt.add_successful('find_process', ret)

        if stop_nginx:
            ret = rcc.run(payloads['stop_nginx'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            fmt.add_successful('stop_nginx', ret)

        ret = rcc.run(payloads['remove_config'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        fmt.add_successful('remove_config', ret)

        ret = rcc.run(payloads['remove_pidfile'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
        fmt.add_successful('remove_pidfile', ret)

        return True, "", fmt.successful_payloads


    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1100]

def read(
        namespace: str,
        config_file=None
) -> Tuple[bool, dict, str]:
    """
    description:
        Checks configuration file and process status of nginx process serving cloud-init userdata/metadata in a VRF namespace on the PodNet node.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        config_file:
            description: |
                path to the config.json file. Defaults to /opt/robot/config.json
                if unspecified.
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              process status and file contents retrieved from both podnet nodes. May be None if nothing
              could be retrieved.
            properties:
              <podnet_ip>:
                description: structure holding process status/config file contents from machine <podnet_ip>
                type: object
                  process_status:
                  type: string
                    description: |
                      The contents of the `userdata` file at domain_path. May be
                      None upon any read errors.
                    type: string
                  config_file:
                    type: string
                    description: |
                      The contents of the nginx configuration file. May be
                      None upon any read errors.
          errors:
            type: array
            description: List of success/error messages produced while reading state
            items:
              type: string
    """

    nginx_config_path = f'/etc/netns/{namespace}/nginx.conf'
    pidfile = f'/etc/netns/{namespace}/nginx.pid'

    # Define message
    messages = {
        1200: f'Successfully retrieved nginx process status and {nginx_config_path}s from both PodNet nodes.',

        3221: f'Failed to connect to the enabled PodNet for read_config payload: ',
        3222: f'Failed to run read_config payload on the enabled PodNet. Payload exited with status ',
        3223: f'Failed to connect to the enabled PodNet for find_process payload: ',
        3224: f'Failed to run find_process payload on the enabled PodNet node. Payload exited with status ',
        3225: f'find_process payload on the enabled PodNet node did not find a nginx process. Payload exited with status ',

        3251: f'Failed to connect to the enabled PodNet for read_config payload: ',
        3252: f'Failed to run read_config payload on the enabled PodNet. Payload exited with status ',
        3253: f'Failed to connect to the enabled PodNet for find_process payload: ',
        3254: f'Failed to run find_process payload on the enabled PodNet node. Payload exited with status ',
        3255: f'find_process payload on the disabled PodNet node did not find a nginx process. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

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


        nginx_config_path_grepsafe = nginx_config_path.replace('.', '\.')

        # define payloads
        payloads = {
            'find_process': "ps auxw | grep nginx | grep -v grep | grep '%s' | awk '{print $2}'" % nginx_config_path_grepsafe,
            'read_config': f'cat {nginx_config_path}'
        }

        ret = rcc.run(payloads['read_config'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
        else:
            data_dict[podnet_node]['config'] = ret["payload_message"].strip()
            fmt.add_successful('read_config', ret)

        ret = rcc.run(payloads['find_process'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+3}: " + messages[prefix+3])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+4}: " + messages[prefix+4])
        else:
            pid = ret["payload_message"].strip()
            if pid == "":
                fmt.store_payload_error(ret, f"{prefix+5}: " + messages[prefix+5])
            else:
                data_dict[podnet_node]['pid'] = pid
                fmt.add_successful('find_process', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval_enabled, msg_list_enabled, successful_payloads, data_dict = run_podnet(enabled, 3220, {}, {})

    retval_disabled, msg_list_disabled, successful_payloads, data_dict = run_podnet(disabled, 3250, successful_payloads, data_dict)

    msg_list = list()
    msg_list.extend(msg_list_enabled)
    msg_list.extend(msg_list_disabled)

    if not (retval_enabled and retval_disabled):
        return False, data_dict, msg_list
    else:
       return True, data_dict, (messages[1200])

