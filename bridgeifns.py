# stdlib
from os import name
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CouldNotConnectException
# local


__all__ = [
    'build',
    'scrub',
]

SUCCESS_CODE = 0


def build(
    bridgename: str,
    namespace: str,
) -> Tuple[bool, str]:
    """
    description:
        Creates a veth link on the main namespace and connects it to a bridge.
        Then, it moves one end of the link to a VRF network namespace and sets the interface up.

    parameters:
        bridgename:
            description: The name of the bridge on the main namespace.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the veth link creation was successful,
            and the output or error message.
        type: tuple
    """
    # Define functions
    def InterfaceExists(bridgename):
        try:
            exit_code, _, _ = comms_ssh(
                host_ip='localhost',
                payload=f'ip link show {bridgename}',
                username='robot',)

            if exit_code == 0:
                return True
            else:
                return False

        except CouldNotConnectException:
            return False

    # Define message
    messages = {
        1000: f'1000: Successfully created veth link and connected it to bridge {bridgename}, moved one end to namespace {namespace}.',
        1001: f'1001: Failed to create veth link on bridge {bridgename}.',
        1002: f'1002: Failed to set interface in namespace {namespace}.',
    }


    if InterfaceExists(bridgename) or InterfaceExists(namespace):
        message = InterfaceExists(bridgename) *  f'Bridgename: {bridgename} already exists.' + InterfaceExists(namespace) * f'Namespace: {namespace} already exists.'
        return False, message
    else:
        # Step 1: Create veth link
        payload_1 = f'ip link add {bridgename}.{namespace} type veth peer name {namespace}.{bridgename}'
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_1,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[1001]

        if exit_code != SUCCESS_CODE:
            return False, messages[1001] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        # Step 2: Connect one end to the bridge
        payload_2 = f'ip link set dev {bridgename}.{namespace} master {bridgename}'
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_2,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[1001]

        if exit_code != SUCCESS_CODE:
            return False, messages[1001] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        # Step 3: Move the other end to the namespace
        payload_3 = f'ip link set dev {namespace}.{bridgename} netns {namespace}'
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_3,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[1002]

        if exit_code != SUCCESS_CODE:
            return False, messages[1002] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        # Step 4: Set the interface up in the namespace
        payload_4 = f'ip netns exec {namespace} ip link set dev {namespace}.{bridgename} up'
        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload_4,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[1002]

        if exit_code != SUCCESS_CODE:
            return False, messages[1002] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        return True, messages[1000]

def scrub(
    bridgename: str,
    namespace: str,
) -> Tuple[bool, str]:
    """
    description:
        Removes the specified veth interface from the given namespace.

    parameters:
        bridgename:
            description: The name of the bridge associated with the interface.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the interface was successfully deleted,
            and the output or error message.
        type: tuple
    """

    # Define functions
    def InterfaceExists(bridgename):
        try:
            exit_code, _, _ = comms_ssh(
                host_ip='localhost',
                payload=f'ip link show {bridgename}',
                username='robot',)

            if exit_code == 0:
                return True
            else:
                return False

        except CouldNotConnectException:
            return False
    # Define messages
    messages = {
        2000: f'2000: Successfully deleted interface {namespace}.{bridgename} from namespace {namespace}.',
        2001: f'2001: Failed to delete interface {namespace}.{bridgename} from namespace {namespace}.',
    }

    if InterfaceExists(bridgename) or InterfaceExists(namespace):
        message = InterfaceExists(bridgename) *  f'Bridgename: {bridgename} already exists.' + InterfaceExists(namespace) * f'Namespace: {namespace} already exists.'
        return False, message
    else:
        # Remove the interface from the namespace
        payload = f'ip netns exec {namespace} ip link del {namespace}.{bridgename}'

        try:
            exit_code, stdout, stderr = comms_ssh(
                host_ip='localhost',
                payload=payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[2001]

        if exit_code != SUCCESS_CODE:
            return False, messages[2001] + f'\nSTDOUT: {stdout}\nSTDERR: {stderr}'

        return True, messages[2000]

