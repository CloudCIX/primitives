"""
Primitive to Build, Read and Scrub dnsmasq for VRF name space DHCP on PodNet HA
"""
# stdlib
import json
import os
from typing import Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
# local
from cloudcix_primitives.utils import (
    check_template_data,
    load_pod_config,
    JINJA_ENV,
    PodnetErrorFormatter,
    SSHCommsWrapper,
)


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0


def build(
        namespace: str,
        dhcp_ranges: list,
        dhcp_hosts: list,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Configures and starts a dnsmasq instance to act as DHCP server inside a VRF network name space on a PodNet node.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        dhcp_ranges:
          type: array
        dhcp_hosts:
          type: array
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    dnsmasq_config_path = f'/etc/netns/{namespace}/dnsmasq.conf'
    dnsmasq_hosts_path = f'/etc/netns/{namespace}/dnsmasq.hosts'
    pidfile= f'/etc/netns/{namespace}/dnsmasq.pid'

    # Define message
    messages = {
        1000: f'1000: Successfully created {dnsmasq_config_path} and started dnsmasq process on both PodNet nodes.',
        3019: f'3019: Failed to render jinja2 template for {dnsmasq_config_path}',
        3020: f'3020: Failed to render jinja2 template for {dnsmasq_hosts_path}',

        3021: f'Failed to connect to the enabled PodNet for find_process payload: ',
        3022: f'Failed to connect to the enabled PodNet for create_config payload: ',
        3023: f'Failed to run create_config payload on the enabled PodNet. Payload exited with status ',
        3024: f'Failed to connect to the enabled PodNet for create_hosts payload: ',
        3025: f'Failed to run create_hosts payload on the enabled PodNet. Payload exited with status ',
        3026: f'Failed to connect to the enabled PodNet for reload_dnsmasq payload: ',
        3027: f'Failed to run reload_dnsmasq payload on the enabled PodNet. Payload exited with status ',
        3028: f'Failed to connect to the enabled PodNet for start_dnsmasq payload: ',
        3029: f'Failed to run start_dnsmasq payload on the enabled PodNet. Payload exited with status ',

        3061: f'Failed to connect to the disabled PodNet for find_process payload: ',
        3062: f'Failed to connect to the disabled PodNet for create_config payload: ',
        3063: f'Failed to run create_config payload on the disabled PodNet. Payload exited with status ',
        3064: f'Failed to connect to the disabled PodNet for create_hosts payload: ',
        3065: f'Failed to run create_hosts payload on the disabled PodNet. Payload exited with status ',
        3066: f'Failed to connect to the disabled PodNet for reload_dnsmasq payload: ',
        3067: f'Failed to run reload_dnsmasq payload on the disabled PodNet. Payload exited with status ',
        3068: f'Failed to connect to the disabled PodNet for start_dnsmasq payload: ',
        3069: f'Failed to run start_dnsmasq payload on the disabled PodNet. Payload exited with status ',

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

    # template data for required files
    template_data = {
        'hosts': dhcp_hosts,
        'hostsfile': dnsmasq_hosts_path,
        'pidfile': pidfile,
        'ranges': dhcp_ranges,
    }
    # Templates
    # dnsmasq.conf file
    template = JINJA_ENV.get_template('dchp_ns/dnsmasq.conf.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3019: {messages[3019]}'

    dnsmasq_conf = template.render(**template_data)

    # dnsmasq.hosts file
    template = JINJA_ENV.get_template('dchp_ns/dnsmasq.hosts.j2')
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        return False, f'3020: {messages[3020]}'

    dnsmasq_hosts = template.render(**template_data)


    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        dnsmasq_config_path_grepsafe = dnsmasq_config_path.replace('.', '\.')
        dnsmasq_hosts_path_grepsafe = dnsmasq_hosts_path.replace('.', '\.')

        payloads = {
            'create_config': "\n".join([
                f'tee {dnsmasq_config_path} <<EOF',
                dnsmasq_conf,
                "EOF"
            ]),
            'create_hosts': "\n".join([
                f'tee {dnsmasq_hosts_path} <<EOF',
                dnsmasq_hosts,
                "EOF"
            ]),
            'find_process': "ps auxw | grep dnsmasq | grep -v grep | grep '%s' | awk '{print $2}'" % dnsmasq_config_path_grepsafe,
            'start_dnsmasq': f'ip netns exec {namespace} dnsmasq --conf-file={dnsmasq_config_path}',
            'reload_dnsmasq': 'kill -HUP %s',
        }

        ret = rcc.run(payloads['find_process'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        start_dnsmasq = True
        if ret["payload_code"] == SUCCESS_CODE:
            if ret["payload_message"] != "":
                # No need to start dnsmasq if it runs already
                start_dnsmasq = False
                payloads['reload_dnsmasq'] = payloads['reload_dnsmasq'] % ret['payload_message'].strip()
        fmt.add_successful('find_process', ret)

        ret = rcc.run(payloads['create_config'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('create_config', ret)

        ret = rcc.run(payloads['create_hosts'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        fmt.add_successful('create_hosts', ret)

        if start_dnsmasq:
            ret = rcc.run(payloads['start_dnsmasq'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
            fmt.add_successful('start_dnsmasq', ret)
        else:
            ret = rcc.run(payloads['reload_dnsmasq'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            fmt.add_successful('reload_dnsmasq', ret)


        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3060, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]


def read(
        namespace: str,
        config_file=None
) -> Tuple[bool, dict, str]:
    """
    description:
        Checks configuration file and process status of dnsmasq process providing DHCP from a VRF namespace on the PodNet node.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        config_file:
            description: path to the config.json file
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
                      The contents of the dnsmasq.hosts file for this namespace.
                      May be None upon any read errors.
                    type: string
                  config_file:
                    type: string
                    description: |
                      The contents of the nginx configuration file. May be
                      None upon any read errors.
                  config_file:
                    type: string
                    description: |
                      The contents of the nginx hosts file. May be
                      None upon any read errors.
          errors:
            type: array
            description: List of success/error messages produced while reading state
            items:
              type: string
    """

    dnsmasq_config_path = f'/etc/netns/{namespace}/dnsmasq.conf'
    dnsmasq_hosts_path = f'/etc/netns/{namespace}/dnsmasq.hosts'
    pidfile= f'/etc/netns/{namespace}/dnsmasq.pid'

    # Define message
    messages = {
        1200: f'dnsmasq is running on both PodNet nodes.',

        3221: f'Failed to connect to the enabled PodNet for read_config payload: ',
        3222: f'Failed to run read_config payload on the enabled PodNet. Payload exited with status ',
        3223: f'Failed to connect to the enabled PodNet for read_hosts payload: ',
        3224: f'Failed to run read_hosts payload on the enabled PodNet. Payload exited with status ',
        3225: f'Failed to connect to the enabled PodNet for read_pidfile payload: ',
        3226: f'Failed to run read_pidfile payload on the enabled PodNet. Payload exited with status ',
        3227: f'Failed to connect to the enabled PodNet for find_process payload: ',
        3228: f'Failed to execute find_process payload on the enabled PodNet node. Payload exited with status ',

        3251: f'Failed to connect to the disabled PodNet for read_config payload: ',
        3252: f'Failed to run read_config payload on the disabled PodNet. Payload exited with status ',
        3253: f'Failed to connect to the disabled PodNet for read_hosts payload: ',
        3254: f'Failed to run read_hosts payload on the disabled PodNet. Payload exited with status ',
        3255: f'Failed to connect to the disabled PodNet for read_pidfile payload: ',
        3256: f'Failed to run read_pidfile payload on the disabled PodNet. Payload exited with status ',
        3257: f'Failed to connect to the disabled PodNet for find_process payload: ',
        3258: f'Failed to execute find_process payload on the disabled PodNet node. Payload exited with status ',

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


        dnsmasq_config_path_grepsafe = dnsmasq_config_path.replace('.', '\.')
        dnsmasq_hosts_path_grepsafe = dnsmasq_hosts_path.replace('.', '\.')


        # define payloads

        payloads = {
          'read_config': f'cat {dnsmasq_config_path}',
          'read_hosts': f'cat {dnsmasq_hosts_path}',
          'read_pidfile': f'cat {pidfile}',
          'find_process': "ps auxw | grep dnsmasq | grep -v grep | grep '%s' | awk '{print $2}'" % dnsmasq_config_path_grepsafe,
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

        ret = rcc.run(payloads['read_hosts'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+3}: " + messages[prefix+3])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+4}: " + messages[prefix+4])
        else:
            data_dict[podnet_node]['hosts'] = ret["payload_message"].strip()
            fmt.add_successful('read_hosts', ret)

        ret = rcc.run(payloads['read_pidfile'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+5}: " + messages[prefix+3])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+6}: " + messages[prefix+4])
        else:
            data_dict[podnet_node]['pidfile'] = ret["payload_message"].strip()
            fmt.add_successful('read_pidfile', ret)

        ret = rcc.run(payloads['find_process'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+7}: " + messages[prefix+5])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+8}: " + messages[prefix+6])
        else:
            pid = ret["payload_message"].strip()
            if pid == "":
                fmt.store_payload_error(ret, f"{prefix+8}: " + messages[prefix+6])
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



def scrub(
        namespace: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description: |
        Stops a dnsmasq instance that acts as a DHCP server inside a VRF
        network name space on a PodNet node and removes its configuration.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    dnsmasq_config_path = f'/etc/netns/{namespace}/dnsmasq.conf'
    dnsmasq_hosts_path = f'/etc/netns/{namespace}/dnsmasq.hosts'
    pidfile = f'/etc/netns/{namespace}/dnsmasq.pid'

    # Define message
    messages = {
        1100: f'Successfully stopped dnsmasq process and deleted {dnsmasq_config_path}, {dnsmasq_hosts_path}.',

        3121: f'Failed to connect to the enabled PodNet for find_process payload: ',
        3122: f'Failed to connect to the enabled PodNet for delete_config payload: ',
        3123: f'Failed to run delete_config payload on the enabled PodNet. Payload exited with status ',
        3124: f'Failed to connect to the enabled PodNet for stop_dnsmasq payload: ',
        3125: f'Failed to run stop_dnsmasq payload on the enabled PodNet. Payload exited with status ',

        3161: f'Failed to connect to the disabled PodNet for find_process payload: ',
        3162: f'Failed to connect to the disabled PodNet for delete_config payload: ',
        3163: f'Failed to run delete_config payload on the disabled PodNet. Payload exited with status ',
        3164: f'Failed to connect to the disabled PodNet for stop_dnsmasq payload: ',
        3165: f'Failed to run stop_dnsmasq payload on the disabled PodNet. Payload exited with status ',
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

        dnsmasq_config_path_grepsafe = dnsmasq_config_path.replace('.', '\.')

        # define payloads
        payloads = {
           'find_process': "ps auxw | grep dnsmasq | grep -v grep | grep %s | awk '{print $2}'" % dnsmasq_config_path_grepsafe,
           'delete_config': f'rm -f {dnsmasq_config_path} {dnsmasq_hosts_path} {pidfile}',
           'stop_dnsmasq': 'kill -TERM %s',
        }

        ret = rcc.run(payloads['find_process'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        stop_dnsmasq = False
        if ret["payload_code"] == SUCCESS_CODE:
            if ret["payload_message"] != "":
                # No need to start dnsmasq if it runs already
                stop_dnsmasq = True
                payloads['stop_dnsmasq'] = payloads['stop_dnsmasq'] % ret['payload_message'].strip()
        fmt.add_successful('find_process', ret)

        ret = rcc.run(payloads['delete_config'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('delete_config', ret)

        if stop_dnsmasq:
            ret = rcc.run(payloads['stop_dnsmasq'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            fmt.add_successful('stop_dnsmasq', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3160, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1100]

