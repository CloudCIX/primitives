# stdlib
import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple
# libs
from jinja2 import Environment, meta, FileSystemLoader, Template
# local
from cloudcix_primitives.exceptions import (
    CouldNotFindPodNets,
    InvalidPodNetPrivate,
    InvalidPodNetMgmt,
    InvalidPodNetOOB,
    InvalidPodNetPublic,
    InvalidPodNetIPv4CPE,
    InvalidPodNetMgmtIPv6,
)


__all__ = [
    'check_template_data',
    'JINJA_ENV',
    'primitives_directory',
    'load_pod_config',
    'SSHCommsWrapper',
    'PodnetErrorFormatter',
]


primitives_directory = os.path.dirname(os.path.abspath(__file__))
JINJA_ENV = Environment(
    loader=FileSystemLoader(f'{primitives_directory}/templates'),
    trim_blocks=True,
)


def check_template_data(template_data: Dict[str, Any], template: Template) -> Tuple[bool, str]:
    """
    Verifies for any key in template_data is missing.
    :param template_data: dictionary object that must have all the template_keys.
    :param template: The template to be verified
    :return: tuple of boolean flag, success and the error string if any
    """
    with open(str(template.filename), 'r') as fp:
        template_source = fp.read()

    parsed = JINJA_ENV.parse(source=template_source)
    required_keys = meta.find_undeclared_variables(parsed)
    err = ''
    for k in required_keys:
        if k not in template_data:
            err += f'Key `{k}` not found in template data.\n'

    success = '' == err
    return success, err


def load_pod_config(config_file=None, prefix=4000) -> Dict[str, Any]:
    """
    Checks for pod config.json from supplied config_file loads into a json
    object and returns the object.

    :param config_file: the file to read PodNet configuration from
    :param prefix: an integer that is used as base for error numbers, i.e.
        error numbers will be added to this value. Defaults to 4000.
    :return: data dict with podnet config
    """

    messages = {
      10: 'Config file {config_file} loaded.',
      11: 'Failed to open {config_file}: ',
      12: 'Failed to parse {config_file}: ',
      13: 'Failed to get `ipv6_subnet from config_file.',
      14: 'Invalid value for `ipv6_subnet` from config file {config_file}',
      15: 'Failed to get `podnet_a_enabled` from config file {config_file}',
      16: 'Failed to get `podnet_b_enabled` from config file {config_file}',
      17: 'Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
      18: 'Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
      19: 'Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
    }

    config_data = {
      'raw': None,
      'processed': {}
    }

    config = None

    # Load config from config_file
    try:
        with Path(config_file).open('r') as file:
            config = json.load(file)
    except OSError as e:
            return False, config_data, ("%d: " % (prefix+11)) + messages[11] + e.__str__()
    except Exception as e:
            return False, config_data, ("%d: " % (prefix+12)) + messages[12] + e.__str__()

    config_data['raw'] = config

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, config_data, ("%d: " % (prefix+13)) + messages[13]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, config_data, messages[14]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    config_data['processed']['podnet_a'] = podnet_a
    config_data['processed']['podnet_b'] = podnet_b

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, config_data, ("%d: " % (prefix+15)) + messages[15]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, config_data, ("%d: " % (prefix+16)) + messages[16]

    # Determine enabled and disabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, config_data, ("%d: " % (prefix+17)) + messages[17]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, config_data, ("%d: " % (prefix+18)) + messages[18]
    else:
        return False, config_data, ("%d: " % (prefix+19)) + messages[19]

    config_data['processed']['enabled'] = enabled
    config_data['processed']['disabled'] = disabled

    return True, config_data, ("%d: " % (prefix+10)) + messages[10]

def get_podnets(config_filepath):
    data = load_pod_config(config_filepath)
    podnets = [
        value for key, value in data.items() if key in ['podnet_1', 'podnet_2']
    ]
    if len(podnets) == 0:
        raise CouldNotFindPodNets
    for podnet in podnets:
        if podnet.get('mgmt', '') == '':
            raise InvalidPodNetMgmt
        if podnet.get('oob', '') == '':
            raise InvalidPodNetOOB
        if podnet.get('private', '') == '':
            raise InvalidPodNetPrivate
        if podnet.get('public', '') == '':
            raise InvalidPodNetPublic
        if podnet.get('ipv4_cpe', '') == '':
            raise InvalidPodNetIPv4CPE
    return podnets


def get_mgmt_ipv6(mgmt):
    if mgmt in ['', None]:
        raise InvalidPodNetMgmt
    mgmt_ipv6 = ''
    for ip in mgmt['ips']:
        address = str(ip['network_address'])
        if ipaddress.ip_address(address).version == 6:
            mgmt_ipv6 = address
    if mgmt_ipv6 == '':
        raise InvalidPodNetMgmtIPv6
    return mgmt_ipv6


class SSHCommsWrapper:
    """
    Wraps RCC (Reliable Communications Channel) function to remember parameters
    that do not change over a set of multiple invocations.

    :param comm_function: RCC function to call, e.g. cloudcix.rcc.comms_ssh()
    :param host_ip: Target Host for RCC function
    :param username: User name for RCC function to use
    """
    def __init__(self, comm_function, host_ip, username):
        self.comm_function = comm_function
        self.host_ip = host_ip
        self.username = username

    def run(self, payload):
        """
        Runs a command through RCC.
        :param payload: the command to run.
        """
        return self.comm_function(
            host_ip=self.host_ip,
            payload=payload,
            username=self.username
        )

class PodnetErrorFormatter:
    """Formats error messages occuring on PodNet nodes and keeps error/success message state if needed"""

    def __init__(self, config_file, podnet_node, enabled, payload_channels, successful_payloads={}):
        """
        Creates a new errorFormatter.
        :param config_file: Config file the PodNet configuration originates from.
        :param podnet_node: PodNet node the errors occur on.
        :param enabled: Boolean status code indicating whether podnet_node is enabled
        :param payload_channels: dict assigning names to the payload_error and
                                 payload_message keys returned by RCC. For
                                 rcc_ssh you might use 
                                 {'payload_message': 'STDOUT', 'payload_error':
                                 'STDERR'}, for instance. These names will be
                                 used by format_payload_error(). and
                                 store_payload_error().
        :param successful_payloads: dict keyed by PodNet node (may be empty).
                                    Each key contains a list of successful
                                    payload names as created by
                                    add_successful() this can be used to carry
                                    over succesful payloads from a different
                                    instance of this class.
        """
        self.config_file = config_file
        self.podnet_node = podnet_node
        self.enabled = enabled
        self.payload_channels = payload_channels
        self.successful_payloads = successful_payloads
        self.successful_payloads[self.podnet_node] = list()
        self.message_list = list()

    def add_successful(self, payload_name, rcc_return=None):
        """
        Records a payload as having run successfully on this podnet node

        :param payload_name: the payload's name (str)
        :param rcc_return: [optional] data structure returned from RCC. This will be
                           recorded as well and can be used for debugging.
        """
        self.successful_payloads[self.podnet_node].append({
            'payload_name': payload_name,
            'rcc_return': rcc_return
            }
        )


    def channel_error(self, rcc_return, msg_index):
        """
        Formats an error message for a channel error (e.g. network connectivity
        problem or authentication error) and returns it as a string. This multi
        line message will include the error code, the channel's channel_message
        and channel_error and any relevant context, such as the Podnet
        config.json used, the PodNet node it failed on and a list of previous
        successful payloads.
        """
        return self._format_channel_error(rcc_return, msg_index)

    def payload_error(self, rcc_return, msg_index):
        """
        Formats an error message for a payload error (e.g. a failed command)
        and returns it as a string. This multi line message will include the
        error code, the channel's channel_message and channel_error and any
        relevant context, such as the Podnet config.json used, the PodNet node
        it failed on and a list of previous successful payloads.
        """
        return self._format_payload_error(rcc_return, msg_index)

    def store_channel_error(self, rcc_return, msg_index):
        """
        Formats an error message for a channel error (e.g. network connectivity
        problem or authentication error) and stores it in the object for later
        use. This multi line message will include the error code, the channel's
        channel_message and channel_error and any relevant context, such as the
        Podnet config.json used, the PodNet node it failed on and a list of
        previous successful payloads.
        """
        self.message_list.append(self._format_channel_error(rcc_return, msg_index))

    def store_payload_error(self, rcc_return, msg_index):
        """
        Formats an error message for a payload error (e.g. a failed command)
        and stores it in the object for later use. This multi line message will
        include the error code, the channel's channel_message and channel_error
        and any relevant context, such as the Podnet config.json used, the
        PodNet node it failed on and a list of previous successful payloads.
        """
        self.message_list.append(self._format_payload_error(rcc_return, msg_index))

    def _payloads_context(self):
        context = list("")
        context.append(f'Config file: {self.config_file}')
        context.append(f'PodNet: {self.podnet_node} (enabled: {self.enabled})')
        context.append("")
        context.append("Successful payloads:")
        for k in sorted(self.successful_payloads.keys()):
            context.append(f'  {k}: ')
            for payload in self.successful_payloads[k]:
                context.append(f'    {payload["payload_name"]}: ' )
                if payload["rcc_return"] is not None:
                    context.append(f'      status: %s' % payload['rcc_return']['payload_code'] )
                    context.append(f'      %s: ' % self.payload_channels['payload_message'] )
                    context.append('        ' + payload['rcc_return']['payload_message'])
                    context.append(f'      %s: ' % self.payload_channels['payload_error'] )
                    context.append('        ' + payload['rcc_return']['payload_error'])
            context.append("")
            context.append("")
        return "\n".join(context)

    def _format_channel_error(self, rcc_return, msg):
        msg = msg + "channel_code: %s\nchannel_message: %s\nchannel_error: %s\n\n" % (
            rcc_return['channel_code'],
            rcc_return['channel_error'],
            rcc_return['channel_message']
        )
        msg = msg + self._payloads_context()
        return msg

    def _format_payload_error(self, rcc_return, msg):
        msg = msg + "payload code: %s\n%s: %s\n%s: %s\n\n" % (
            rcc_return['payload_code'],
            self.payload_channels['payload_error'],
            rcc_return['payload_error'],
            self.payload_channels['payload_message'],
            rcc_return['payload_message']
        )
        msg = msg + self._payloads_context()
        return msg
