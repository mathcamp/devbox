"""
Helper file to generate package version numbers on the fly

Wouldn't it be great if every time you bundled a python package, it was tagged
with a unique version number that reflected the current git ref? It's almost
like that's a feature that should be available without stupid hacks.

But it's not. So here's how the stupid hacks work.

When you run ``python setup.py``, if you are running it from inside of a git
repository this script with generate a unique version number and embed it in an
auto-generated file in your package. By default the file is named
'__version__.py', and you should add it to your ``.gitignore``. Since this is a
python file and it's in your package, it will get bundled up and distributed
with your package. Then during the installation process, this script will
recognize that it is not longer being run from within a git repository and find
the version number from the file it generated earlier.

"""
import os

import subprocess


def _git_describe(describe_cmd):
    """ Describe the current revision """
    try:
        out = subprocess.check_output(describe_cmd)
        return out.strip()
    except subprocess.CalledProcessError as e:
        print "Error parsing git revision!"
        print e.output
        raise


def get_version(package,
                describe_cmd=('git', 'describe'),
                describe_args=('--tags', '--dirty', '--match=[0-9]*'),
                version_mod='__version__.py'):
    """
    Generate the version from the git revision, or retrieve it from the
    auto-generated module

    Parameters
    ----------
    package : str
        The name of the directory that contains the package's code
    describe_cmd : list
        Command passed to subprocess to generate the version (default ['git',
        'describe'])
    describe_args : list
        Arguments for ``describe_cmd`` to be passed to subprocess (default
        ['--tags', '--dirty', '--match=[0-9]*'])
    version_mod : str, optional
        The name of the file to write the version into (default '__version__.py')

    """
    here = os.path.abspath(os.path.dirname(__file__))
    version_file_path = os.path.join(here, package, version_mod)

    if os.path.isdir(os.path.join(here, '.git')):
        version = _git_describe(describe_cmd + describe_args)
        # Make sure we write the version number to the file so it gets
        # distributed with the package
        with open(version_file_path, 'w') as version_file:
            version_file.write('"""This file is auto-generated during the '
                               'package-building process"""\n')
            version_file.write("__version__ = '" + version + "'")
        return version
    else:
        # If we already have a version file, use the version there
        with open(version_file_path, 'r') as version_file:
            version_line = version_file.readlines()[1]
            version = version_line.split("'")[1]
            return version
