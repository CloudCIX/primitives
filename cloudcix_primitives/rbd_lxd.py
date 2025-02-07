"""
Primitive for RadOS Block Device in Ceph Cluster on KVM
"""
# stdlib
from typing import Tuple
# lib
# local


__all__ = [
    'build',
    'read',
    'scrub',
]


def build() -> Tuple[bool, str]:
    return(False, 'Not Implemented')


def read() -> Tuple[bool, dict, str]:
    return(False, {}, 'Not Implemented')


def scrub() -> Tuple[bool, str]:
    return(False, 'Not Implemented')
