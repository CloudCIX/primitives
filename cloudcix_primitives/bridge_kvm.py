"""
Primitive for Private VLAN Bridge (KVM only)
"""

# 3rd party modules
import jinja2
# stdlib
import os
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
# local
from cloudcix_primitives.utils import SSHCommsWrapper, HostErrorFormatter


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0

template_path = os.path.join(os.path.dirname(__file__), 'templates', __name__.split(".").pop())

def build(
        host: str,
        vlan: int,
        ifname: str,
) -> Tuple[bool, str]:
    """
    description:
        Configures and starts service that creates a vlan tagged bridge on the host .

    parameters:
        host:
            description: Host where the service will be created
            type: string
            required: true
        vlan:
          description: Vlan ID
          type: integer
          required: true
        ifname:
          description: Interface name to be associated with bridge
          type: string
          required: true
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    up_script_path = f'/usr/local/bin/bridge_kvm_br{vlan}_up.sh'
    down_script_path = f'/usr/local/bin/bridge_kvm_br{vlan}_down.sh'
    service_file_path= f'/etc/systemd/system/bridge_kvm_br{vlan}.service'

    # Define message
    messages = {
        1000: f'Successfully created and started bridge_kvm_br{vlan}.service on kvm {host}.',
        1001: f'bridge_kvm_br{vlan}.service already exists on kvm {host}',

        3018: f'Failed to render jinja2 template for {down_script_path}',
        3019: f'Failed to render jinja2 template for {up_script_path}',
        3020: f'Failed to render jinja2 template for {service_file_path}',

        3021: f'Failed to connect to the host {host} for find_service payload: ',
        3022: f'Failed to connect to the host {host} for create_down_script payload: ',
        3023: f'Failed to run create_down_script payload on the host {host}. Payload exited with status ',
        3024: f'Failed to connect to the host {host} for create_up_script payload: ',
        3025: f'Failed to run create_up_script payload on the host {host}. Payload exited with status ',
        3026: f'Failed to connect to the host {host} for create_service_file payload: ',
        3027: f'Failed to run create_service_file payload on the host {host}. Payload exited with status ',
        3028: f'Failed to connect to the host {host} for reload_services payload: ',
        3029: f'Failed to run reload_services payload on the host {host}. Payload exited with status ',
        3030: f'Failed to connect to the host {host} for start_service payload: ',
        3031: f'Failed to run start_service payload on the host {host}. Payload exited with status ',
    }


    try:
      jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(
          os.path.join(template_path))
      )
      template = jenv.get_template("down.sh.j2")

      down_script = template.render(
          ifname=ifname,
          vlan=vlan,
      )
    except Exception as e:
      return False, messages[3018]

    try:
      jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(
          os.path.join(template_path))
      )
      template = jenv.get_template("up.sh.j2")

      up_script= template.render(
          ifname=ifname,
          vlan=vlan,
      )
    except Exception as e:
      return False, messages[3019]
    
    try:
      jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(
          os.path.join(template_path))
      )
      template = jenv.get_template("interface.service.j2")

      service_file= template.render(
          vlan=vlan,
          down_script_path=down_script_path,
          up_script_path=up_script_path,
      )
    except Exception as e:
      return False, messages[3020]

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        down_script_path_grepsafe = down_script_path.replace('.', '\.')
        up_script_path_grepsafe = up_script_path.replace('.', '\.')
        service_file_path_grepsafe = service_file_path.replace('.', '\.')

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
            'find_service': f'systemctl status bridge_kvm_br{vlan}.service',
            'start_service': f'systemctl restart bridge_kvm_br{vlan}.service && systemctl enable bridge_kvm_br{vlan}.service',
            'reload_services': 'systemctl daemon-reload',
        }

        ret = rcc.run(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        create_service=True
        if ret["payload_code"] == SUCCESS_CODE:
            create_service=False
            fmt.payload_error(ret, f"1001: " + messages[1001]), fmt.successful_payloads
        fmt.add_successful('find_service', ret)

        if create_service:
            ret = rcc.run(payloads['create_down_script'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            fmt.add_successful('create_down_script', ret)

            ret = rcc.run(payloads['create_up_script'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            fmt.add_successful('create_up_script', ret)

            ret = rcc.run(payloads['create_service_file'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            fmt.add_successful('create_service_file', ret)
        
        ret = rcc.run(payloads['reload_services'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
        fmt.add_successful('reload_services', ret)

        ret = rcc.run(payloads['start_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+10}: " + messages[prefix+10]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+11}: " + messages[prefix+11]), fmt.successful_payloads
        fmt.add_successful('start_service', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]


def scrub(
        host: str,
        vlan: int,
) -> Tuple[bool, str]:
    """
    description:
        Scrubs the service and deletes the vlan tagged bridge on the host .

    parameters:
        host:
            description: Host where the service will be scrubbed
            type: string
            required: true
        vlan:
          description: Vlan ID
          type: integer
          required: true

    return:
        description: |
            A tuple with a boolean flag stating if the scrub was successful or not and
            the output or error message.
        type: tuple
    """

    up_script_path = f'/usr/local/bin/bridge_kvm_br{vlan}_up.sh'
    down_script_path = f'/usr/local/bin/bridge_kvm_br{vlan}_down.sh'
    service_file_path= f'/etc/systemd/system/bridge_kvm_br{vlan}.service'

    # Define message
    messages = {
        1100: f'Successfully scrubbed bridge_kvm_br{vlan}.service on kvm {host}.',
        1101: f'bridge_kvm_br{vlan}.service does not exists on kvm {host}',

        3121: f'Failed to connect to the host {host} for find_service payload: ',
        3122: f'Failed to connect to the host {host} for stop_service payload: ',
        3123: f'Failed to run stop_service payload on the host {host}. Payload exited with status ',
        3124: f'Failed to connect to the host {host} for delete_files payload: ',
        3125: f'Failed to run delete_files payload on the host {host}. Payload exited with status ',
        3126: f'Failed to connect to the host {host} for reload_services payload: ',
        3127: f'Failed to run reload_services payload on the host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # define payloads
        payloads = {
            'find_service': f'systemctl status bridge_kvm_br{vlan}.service',
            'stop_service': f'systemctl stop bridge_kvm_br{vlan}.service && systemctl disable bridge_kvm_br{vlan}.service',
            'delete_files': f'rm --force {up_script_path} {down_script_path} {service_file_path}',
            'reload_services': 'systemctl daemon-reload',
        }

        ret = rcc.run(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        delete_service=True
        if ret["payload_code"] != SUCCESS_CODE:
            delete_service=False
            fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        fmt.add_successful('find_service', ret)

        if delete_service:
            ret = rcc.run(payloads['stop_service'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            fmt.add_successful('stop_service', ret)

            ret = rcc.run(payloads['delete_files'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            fmt.add_successful('delete_files', ret)
        
        ret = rcc.run(payloads['reload_services'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
        fmt.add_successful('reload_services', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})
    if status is False:
        return status, msg

    return True, messages[1100]


def read(
        host: str,
        vlan: int,
) -> Tuple[bool, dict, str]:
    """
    description:
        Reads the service and the vlan tagged bridge on the host .

    parameters:
        host:
            description: Host where the service will be read
            type: string
            required: true
        vlan:
          description: Vlan ID
          type: integer
          required: true

    return:
        description: |
            A tuple with a boolean flag stating if the read was successful or not and
            the output or error message.
        type: tuple
    """

    up_script_path = f'/usr/local/bin/bridge_kvm_br{vlan}_up.sh'
    down_script_path = f'/usr/local/bin/bridge_kvm_br{vlan}_down.sh'
    service_file_path= f'/etc/systemd/system/bridge_kvm_br{vlan}.service'

    # Define message
    messages = {
        1200: f'Successfully read bridge_kvm_br{vlan}.service on kvm {host}.',
        1201: f'bridge_kvm_br{vlan}.service does not exists on kvm {host}',

        3221: f'Failed to connect to the host {host} for find_service payload: ',
        3222: f'Failed to connect to the host {host} for read_bridge payload: ',
        3223: f'Failed to run read_bridge payload on the host {host}. Payload exited with status ',
        3224: f'Failed to connect to the host {host} for read_down_script payload: ',
        3225: f'Failed to run read_down_script payload on the host {host}. Payload exited with status ',
        3226: f'Failed to connect to the host {host} for read_up_script payload: ',
        3227: f'Failed to run read_up_script payload on the host {host}. Payload exited with status ',
        3228: f'Failed to connect to the host {host} for read_service_file payload: ',
        3229: f'Failed to run read_service_file payload on the host {host}. Payload exited with status ',
    }

    def run_host(host, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[host] = {}

        rcc = SSHCommsWrapper(comms_ssh, host, 'robot')
        fmt = HostErrorFormatter(
            host,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # define payloads
        payloads = {
            'find_service': f'systemctl status bridge_kvm_br{vlan}.service',
            'read_bridge': f'ip link show br{vlan}',
            'read_up_script': f'cat {up_script_path}',
            'read_down_script': f'cat {down_script_path}',
            'read_service_file': f'cat {service_file_path}',
        }

        ret = rcc.run(payloads['find_service'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"1201: " + messages[1201])
        else:
            data_dict[host]['service'] = ret["payload_message"].strip()
            fmt.add_successful('find_service', ret)

        ret = rcc.run(payloads['read_bridge'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3])
        else:
            data_dict[host]['bridge'] = ret["payload_message"].strip()
            fmt.add_successful('read_bridge', ret)

        ret = rcc.run(payloads['read_down_script'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5])
        else:
            data_dict[host]['down_script'] = ret["payload_message"].strip()
            fmt.add_successful('read_down_script', ret)

        ret = rcc.run(payloads['read_up_script'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7])
        else:
            data_dict[host]['up_script'] = ret["payload_message"].strip()
            fmt.add_successful('read_up_script', ret)

        ret = rcc.run(payloads['read_service_file'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.channel_error(ret, f"{prefix+8}: " + messages[prefix+8])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.payload_error(ret, f"{prefix+9}: " + messages[prefix+9])
        else:
            data_dict[host]['service_file'] = ret["payload_message"].strip()
            fmt.add_successful('read_file_service', ret)


        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(host, 3220, {}, {})
    message_list = list()
    message_list.extend(msg_list)


    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, [messages[1200]]