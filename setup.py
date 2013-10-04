""" Setup file """
import os
import subprocess

from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(HERE, 'README.rst')).read()
CHANGES = open(os.path.join(HERE, 'CHANGES.txt')).read()

REQUIREMENTS = [
    'mock',
]

DATA = {
    'name': 'gitbox',
    'description': 'Quickly set up python repos for development',
    'long_description': README + '\n\n' + CHANGES,
    'classifiers': [
        'Programming Language :: Python',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',

    ],
    'license': 'MIT',
    'author': 'Steven Arcangeli',
    'author_email': 'steven@highlig.ht',
    'url': '',
    'zip_safe': False,
    'include_package_data': True,
    'packages': find_packages(),
    'entry_points': {
        'console_scripts': [
            'gitbox-pre-commit = gitbox.hook:precommit',
            'gitbox-create = gitbox:create',
            'gitbox-unbox = gitbox.unbox:main',
        ],
    },
    'setup_requires': [
        'nose>=1.0',
    ],
    'install_requires': REQUIREMENTS,
    'tests_require': REQUIREMENTS,
}

VERSION_MODULE = os.path.join(HERE, DATA['name'], '__version__.py')


def _git_describe():
    """ Describe the current revision """
    try:
        out = subprocess.check_output(['git', 'describe', '--tags',
                                       '--dirty', '--match=[0-9]*'])
        return out.strip()
    except subprocess.CalledProcessError as e:
        print "Error parsing git revision!"
        print e.output
        raise


def get_version():
    """
    Calculate the version from the git revision, or retrieve it from the
    auto-generated module

    """
    if os.path.isdir(os.path.join(HERE, '.git')):
        version = _git_describe()
        # Make sure we write the version number to the file so it gets
        # distributed with the package
        with open(VERSION_MODULE, 'w') as version_file:
            version_file.write('"""This file is auto-generated during the '
                               'package-building process"""\n')
            version_file.write("__version__ = '" + version + "'")
        return version
    else:
        # If we already have a version file, use the version there
        with open(VERSION_MODULE, 'r') as version_file:
            version_line = version_file.readlines()[1]
            version = version_line.split("'")[1]
            return version

DATA['version'] = get_version()

if __name__ == "__main__":
    setup(**DATA)
