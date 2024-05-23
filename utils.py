# stdlib
import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple
# libs
from jinja2 import Environment, meta, FileSystemLoader, Template
# local
from .exceptions import (
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


def load_pod_config(config_filepath: str) -> Dict[str, Any]:
    """
    Checks for pod config.json from supplied config_filepath or the current working directory and
    Loads into a json object and return the object
    :return data: object with podnet config
    """
    file_path = Path(config_filepath)
    if not file_path.exists():
        raise FileNotFoundError
    with file_path.open('r') as json_file:
        return json.load(json_file)


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
