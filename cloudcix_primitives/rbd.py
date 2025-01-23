"""
Primitive for RadOS Block Device on Ceph cluster
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


def updateq() -> Tuple[bool, str]:
    return(False, 'Not Implemted')
