"""
Primitive for LXC Snapshot on LXD hosts
"""
# stdlib
from typing import Tuple
# lib
# local


__all__ = [
    'build',
    'read',
    'scrub',
    'update',
]


def build() -> Tuple[bool, str]:
    return(False, 'Not Implemted')


def read() -> Tuple[bool, dict, str]:
    return(False, {}, 'Not Implemted')


def scrub() -> Tuple[bool, str]:
    return(False, 'Not Implemted')


def update() -> Tuple[bool, str]:
    return(False, 'Not Implemted')
