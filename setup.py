# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
try: # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements
import re, ast

# get version from __version__ variable in erpnext_foxycart_integration/__init__.py
_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('erpnext_foxycart_integration/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

requirements = parse_requirements("requirements.txt", session="")
# Generator must be converted to list, or we will only have one chance to read each element, meaning that the first requirement will be skipped.
requirements = list(requirements)
try:
    requirements = [str(ir.req) for ir in install_reqs]
except:
    requirements = [str(ir.requirement) for ir in install_reqs]

setup(
	name='erpnext_foxycart_integration',
	version=version,
	description='An integration app to capture orders processed from FoxyCart into ERPNext',
	author='David Menting',
	author_email='david@dato.mu',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=[str(ir.req) for ir in requirements],
	dependency_links=[str(ir._link) for ir in requirements if ir._link]
)
