#!/usr/bin/env python

from setuptools import setup
setup(name='awme',
      version='1.0',
      description='awme is a scalable, restful, hot cache of your Amazon host and security group metadata!',
      author='Christopher Vincelette',
      author_email='chriss@chrissvincelette.com',
      url='https://github.com/sharethis-github/awme', 
      packages=['awme',],
      scripts=[
        'scripts/awme_collector',
        'scripts/awme_server',
        ],
      setup_requires=[
      ],
      install_requires=[
        "flask",
        "networkx",
        "pickle",
        "boto"
      ],
)
