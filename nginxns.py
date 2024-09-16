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
from cloudcix.rcc import comms_ssh, CouldNotConnectException
# local


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
        1000: f'1000: Successfully created {nginx_config_path} and started nginx process on both PodNet nodes.',
        2011: f'2011: Config file {config_file} loaded.',
        3011: f'3011: Failed to load config file {config_file}, It does not exist.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3019: f'3019: Failed to render jinja2 template for {nginx_conf_path}',
        3020: f'3020: Failed to connect to the enabled PodNet from the config file {config_file} for find_process_payload',
        3021: f'3021: Failed to run find_process_payload on the enabled PodNet. Payload exited with status ',
        3022: f'3022: Failed to connect to the enabled PodNet from the config file {config_file} for create_config_payload',
        3023: f'3023: Failed to create config file {nginx_config_path} on the enabled PodNet. Payload exited with status ',
        3024: f'3024: Failed to connect to the enabled PodNet from the config file {config_file} for reload_nginx_payload',
        3025: f'3025: Failed to run reload_nginx_payload on the enabled PodNet. Payload exited with status ',
        3026: f'3026: Failed to connect to the enabled PodNet from the config file {config_file} for start_nginx_payload',
        3027: f'3027: Failed to start nginx on the enabled PodNet. Payload exited with status ',
        3030: f'3030: Failed to connect to the enabled PodNet from the config file {config_file} for find_process_payload',
        3031: f'3031: Failed to run find_process_payload on the disabled PodNet. Payload exited with status ',
        3032: f'3032: Successfully created {nginx_config_path} and started nginx on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for create_config_payload.',
        3033: f'3033: Successfully created {nginx_config_path} and started nginx on enabled PodNet but failed to create {nginx_config_path} on the disabled PodNet. '
               'Payload exited with status ',
        3034: f'3034: Failed to connect to the disabled PodNet from the config file {config_file} for reload_nginx_payload',
        3035: f'3035: Failed to run reload_nginx_payload on the disabled PodNet. Payload exited with status ',
        3036: f'3036: Successfully created {nginx_config_path} on both PodNet nodes and started nginx on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for start_nginx_payload.',
        3037: f'3037: Successfully created {nginx_config_path} on both PodNet nodes and started nginx on enabled PodNet but failed to start nginx on the disabled PodNet. '
               'Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, messages[3011]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, messages[3012]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, messages[3013]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3014]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3015]

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, messages[3016]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, messages[3017]
    else:
        return False, messages[3018]

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

    create_config_payload = "\n".join([
        f'tee {nginx_conf_path}s <<EOF',
        nginx_conf,
        "EOF"
        ])

    # We need to check for existing process and SIGHUP its PID if one exist:
    find_process_payload = "ps auxw | grep nginx | grep {nginx_config_path}s | awk '{print $2}'"
    start_nginx_payload = f'ip netns exec {namespace} nginx -c {nginx_conf_path}s'

    # call rcc comms_ssh on enabled PodNet to find existing process
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3020]

    reload_nginx_payload = None
    if (exit_code == SUCCESS_CODE) and (stdout != ""):
        reload_nginx_payload = f'kill -HUP {stdout}s'
    else:
       return False, messages[3021] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    # call rcc comms_ssh on enabled PodNet to create config
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=create_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3022]

    if exit_code != SUCCESS_CODE:
        return False, messages[3023] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    if reload_nginx_payload is not None:
        # call rcc comms_ssh on enabled PodNet to SIGHUP existing process
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip=enabled,
                payload=reload_nginx_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3024]

        if exit_code != SUCCESS_CODE:
            return False, messages[3025]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'
    else:
        # call rcc comms_ssh on enabled PodNet
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip=enabled,
                payload=start_nginx_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3026]

        if exit_code != SUCCESS_CODE:
            return False, messages[3027]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'


    # call rcc comms_ssh on disabled PodNet to find existing process
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3030]

    reload_nginx_payload_disabled = None
    if (exit_code == SUCCESS_CODE) and (stdout != ""):
        reload_nginx_payload_enabled = f'kill -HUP {stdout}s'
    else:
       return False, messages[3031] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    # call rcc comms_ssh on disabled PodNet
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=create_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3032]

    if exit_code != SUCCESS_CODE:
        return False, messages[3033] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    if reload_nginx_payload_disabled is None:
        # call rcc comms_ssh on disabled PodNet to SIGHUP existing process
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip=disabled,
                payload=reload_nginx_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3034]

        if exit_code != SUCCESS_CODE:
            return False, messages[3035]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'
    else:
        # call rcc comms_ssh on disabled PodNet
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip=disabled,
                payload=start_nginx_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3036]

        if exit_code != SUCCESS_CODE:
            return False, messages[3037]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'


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

    nginx_config_path = '/etc/netns/{namespace}/nginx.conf'

    # Define message
    messages = {
        1100: f'1100: Successfully stopped nginx process and deleted {nginx_config_path}.',
        2111: f'2111: Config file {config_file} loaded.',
        3111: f'3111: Failed to load config file {config_file}, It does not exist.',
        3112: f'3112: Failed to get `ipv6_subnet` from config file {config_file}',
        3113: f'3113: Invalid value for `ipv6_subnet` from config file {config_file}',
        3114: f'3114: Failed to get `podnet_a_enabled` from config file {config_file}',
        3115: f'3115: Failed to get `podnet_b_enabled` from config file {config_file}',
        3116: f'3116: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3117: f'3117: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3118: f'3118: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3119: f'3119: Failed to connect to the enabled PodNet from the config file {config_file} for find_proces_payload',
        3120: f'3120: Failed to find process on the enabled PodNet. Payload exited with status ',
        3121: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for stop_nginx_payload',
        3122: f'3122: Failed to connect to the enabled PodNet from the config file {config_file} for start_nginx_payload',
        3123: f'3123: Failed to stop nginx on the enabled PodNet. Payload exited with status ',
        3124: f'3124: Failed to connect to the enabled PodNet from the config file {config_file} for remove_config_payload',
        3125: f'3125: Failed to delete config file {nginx_config_path} on the enabled PodNet. Payload exited with status ',
        3129: f'3129: Failed to run find_process_payload on the disabled PodNet. Payload exited with status ',
        3130: f'3130: Successfully created {nginx_config_path} and started nginx on enabled PodNet '
              f'but failed to connect to the disabled PodNet from the config file {config_file} for find_process_payload.',
        3131: f'3131: Successfully stopped nginx and deleted {nginx_config_path} on enabled PodNet '
              f'but failed to connect to the disabled PodNet from the config file {config_file} for stop_nginx_payload.',
        3132: f'3132: Successfully stopped nginx and deleted {nginx_config_path} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for stop_nginx_payload.',
        3133: f'3133: Successfully stopped nginx and deleted {nginx_config_path} on enabled PodNet but failed to stop nginx on the disabled PodNet. '
               'Payload exited with status ',
        3134: f'3134: Successfully stoppend nginx and deleted {nginx_config_path} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for remove_config_payload.',
        3135: f'3135: Successfully stopped nginx on both PodNet nodes and deleted {nginx_config_path} on enabled PodNet but failed to stop nginx on the disabled PodNet. '
               'Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, messages[3111]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, messages[3112]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, messages[3113]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3114]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3115]

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, messages[3116]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, messages[3117]
    else:
        return False, messages[3118]

    # define payloads
    find_process_payload = f'ps auxw | grep nginx | grep {nginx_config_path}s'
    delete_config_payload = f'rm -f {nginx_config_path}s'

    # call rcc comms_ssh on enabled PodNet to find existing process
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3119]

    if exit_code != SUCCESS_CODE:
        return False, messages[3120] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    stop_nginx_payload = None
    if (exit_code == SUCCESS_CODE) and (stdout != ""):
        stop_nginx_payload = f'kill {stdout}s'
    else:
        return False, messages[3121] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    if stop_nginx_payload is not None:
        # call rcc comms_ssh on enabled PodNet to kill existing process
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip=enabled,
                payload=stop_nginx_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3122]
        if exit_code != SUCCESS_CODE:
            return False, messages[3123]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    # call rcc comms_ssh for nginx config file removal on enabled PodNet
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=remove_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3124]

    if exit_code != SUCCESS_CODE:
        return False, messages[3125]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    # call rcc comms_ssh on disabled PodNet to find existing process
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3129]

    if exit_code != SUCCESS_CODE:
        return False, messages[3130] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    stop_nginx_payload = None
    if (exit_code == SUCCESS_CODE) and (stdout != ""):
        stop_nginx_payload = f'kill {stdout}s'
    else:
        return False, messages[3131] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    if stop_nginx_payload is not None:
        # call rcc comms_ssh on disabled PodNet to kill existing process
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip=disabled,
                payload=stop_nginx_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3132]
        if exit_code != SUCCESS_CODE:
            return False, messages[3133]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

    # call rcc comms_ssh for nginx config file removal on disabled PodNet
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=remove_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3134]

    if exit_code != SUCCESS_CODE:
        return False, messages[3135]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}'

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
    pidfile = f'/etc/netns/{namespace}/nginx.conf'

    # Define message
    messages = {
        1200: f'1200: Successfully retrieved nginx process status and {nginx_config_path}s from both PodNet nodes.',
        2211: f'2211: Config file {config_file} loaded.',
        3211: f'3211: Failed to load config file {config_file}: ',
        3212: f'3212: Failed to get `ipv6_subnet` from config file {config_file}',
        3213: f'3213: Invalid value for `ipv6_subnet` from config file {config_file}',
        3214: f'3214: Failed to get `podnet_a_enabled` from config file {config_file}',
        3215: f'3215: Failed to get `podnet_b_enabled` from config file {config_file}',
        3216: f'3216: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3217: f'3217: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3218: f'3218: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for read_config_payload',
        3222: f'3222: Failed to read config file {nginx_config_path}s on the enabled PodNet. Payload exited with status ',
        3223: f'3223: Failed to connect to the enabled PodNet from the config file {config_file} for find_process_payload',
        3223: f'3224: Failed to execute find_process_payload on the enabled PodNet node. Payload exited with status ',
        3231: f'3231: Successfully retrieved nginx process status and {nginx_config_path}s from enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for read_config_payload',
        3232: f'3232: Successfully retrieved nginx process status and {nginx_config_path}s from enabled PodNet but failed to execute read_config_payload '
               'on the disabled PodNet. Payload exited with status ',
        3233: f'3233: Successfully retrieved {nginx_config_file}s from both PodNet nodes but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for find_process_payload.',
        3234: f'3234: Successfully retrieved {nginx_config_file}s from both PodNet nodes but failed to execute find_process_payload on the disabled PodNet. '
               'Payload exited with status ',
    }

    retval = True
    data_dict = None
    message_list = ()

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Get load config from config_file
    try:
      with Path(config_file).open('r') as file:
          config = json.load(file)
    except Exception as e:
        retval = False
        message_list.append(messages[3211] + e.__str__())
        return retval, data_dict, message_list

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        retval = False
        message_list.append(messages[3212])
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        retval = False
        message_list.append(messages[3213])

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    data_dict = {}

    data_dict[podnet_a] = {
        'process_status': None,
        'config_file': None,
    }

    data_dict[podnet_b] = {
        'process_status': None,
        'config_file': None,
    }

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        retval = False
        message_list.append(messages[3214])
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        retval = False
        message_list.append(messages[3215])

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        retval = False
        message_list.append(messages[3216])
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        retval = False
        message_list.append(messages[3217])
    else:
        message_list.append(messages[3218])

    if retval == False:
        return retval, data_dict, message_list

    # define payloads
    read_config_payload = f'cat {nginx_config_path}'
    find_process_payload = f'ps auxw | grep nginx | grep {nginx_config_path}s'

    # call rcc comms_ssh for config retrieval from enabled PodNet
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=read_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        exit_code = None
        retval = False
        message_list.append(messages[3221])

    if ( exit_code is not None ) and ( exit_code != SUCCESS_CODE ):
        retval = False
        message_list.append(messages[3222] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}')

    data_dict[enabled]['config_file'] = stdout

    # call rcc comms_ssh for process_status retrieval from enabled PodNet
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        exit_code = None
        retval = False
        message_list.append(messages[3223])

    if ( exit_code is not None ) and ( exit_code != SUCCESS_CODE ):
        retval = False
        message_list.append(messages[3224]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}')

    data_dict[enabled]['process_status'] = stdout

    # call rcc comms_ssh for config retrieval from disabled PodNet
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=read_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        exit_code = None
        retval = False
        message_list.append(messages[3231])

    if ( exit_code is not None ) and ( exit_code != SUCCESS_CODE ):
        retval = False
        message_list.append(messages[3232] + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}')

    data_dict[enabled]['config_file'] = stdout

    # call rcc comms_ssh for process_status retrieval from disabled PodNet
    try:
        exit_code, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        exit_code = None
        retval = False
        message_list.append(messages[3233])

    if ( exit_code is not None ) and ( exit_code != SUCCESS_CODE ):
        retval = False
        message_list.append(messages[3234]  + f'{exit_code}s.\nSTDOUT: {stdout}\nSTDERR: {stderr}')

    data_dict[disabled]['process_status'] = stdout

    message_list.append(messages[1200])
    return retval, data_dict, message_list
