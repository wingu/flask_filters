"""
Setup script for flask_filters.
"""
from setuptools import setup

if __name__ == '__main__':
    setup(name='flask_filters',
          py_modules=['flask_filters'],
          install_requires=['flask'],
          version='1.0',
          description='Coroutine-based filters for Flask views',
          url='https://github.com/wingu/flask_filters',
          classifiers=['Development Status :: 5 - Production/Stable',
                       'License :: OSI Approved :: BSD License',
                       'Programming Language :: Python :: 2'])
