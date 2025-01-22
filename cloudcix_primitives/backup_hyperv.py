"""
Primitive for Virtual Machine Backup on HyperV hosts
"""
# stdlib
from typing import Tuple
# lib
# local

__all__ = [
    'build',
    'scrub',
    'read',
]


def build() -> Tuple[bool, str]:
    return(False, 'Not Implemted')


def read() -> Tuple[bool, str]:
    return(False, 'Not Implemted')


def scrub() -> Tuple[bool, str]:
    return(False, 'Not Implemted')
