#! /usr/bin/env python3
# -*-python-*-

from setuptools import setup, find_packages

setup(
    name="cloudcix_primitives",
    version='0.1.1',
    author="CloudCIX",
    author_email="developers@cloudcix.com",
    maintainer="CloudCIX",
    maintainer_email="developers@cloudcix.com",
    license="Apache 2.0",
    install_requires=[
        "cloudcix>=0.15.2",
        "jinja2"
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'cloudcix_primitives': ['templates/**/*.j2'],
    },
    platforms="platform-independent",
    url="https://www.github.com/cloudcix/primitives/",
    description="Primitives and associated utilities for CloudCIX Drivers to use.",
    long_description="""This module contains a library of primitives that
    CloudCIX drivers use to effect changes on the cloud's infrastructure (e.g.
    PodNet nodes, hypervisors).""",
    classifiers=[
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: Unix",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3.7",
    "Topic :: Software Development :: Libraries",
    ],
    )
