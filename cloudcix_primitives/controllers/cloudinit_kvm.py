# stdlib
import re
# local
from cloudcix_primitives.controllers.exceptions import (
    exception_handler,
    InvalidKVMInterfaceItem,
    InvalidKVMInterfaceMacAddress,
    InvalidKVMInterfaceVlanBridge,
)


__all__ = ['KVMInterface']


def is_valid_mac(mac_address):
    # Define the regex pattern for MAC addresses
    pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'

    # Use fullmatch to check if the entire string matches the pattern, if not matches result is None
    return re.fullmatch(pattern, mac_address) is not None


def is_valid_vlan_bridge(vlan_bridge):
    # Define the regex pattern for VLAN bridges
    pattern = r'^br\d{4}$'

    # Use fullmatch to check if the entire string matches the pattern, if not matches result is None
    return re.fullmatch(pattern, vlan_bridge) is not None


class KVMInterface:
    interface: dict
    success: bool
    errors: list

    def __init__(self, interface) -> None:
        self.interface = interface
        self.success = True
        self.errors = []

    def __call__(self):
        validators = [
            self._validate_mac_address,
            self._validate_vlan_bridge,
        ]

        for validator in validators:
            error = validator()
            if error is not None:
                self.success = False
                self.errors.append(str(error))

        return self.success, self.errors

    @exception_handler
    def _validate_mac_address(self):
        mac_address = self.interface.get('mac_address', None)
        if mac_address is None:
            raise InvalidKVMInterfaceItem('mac_address')
        if is_valid_mac(mac_address) is False:
            raise InvalidKVMInterfaceMacAddress(mac_address)

    @exception_handler
    def _validate_vlan_bridge(self):
        vlan_bridge = self.interface.get('vlan_bridge', None)
        if vlan_bridge is None:
            raise InvalidKVMInterfaceItem('vlan_bridge')
        if is_valid_vlan_bridge(vlan_bridge) is False:
            raise InvalidKVMInterfaceVlanBridge(vlan_bridge)
