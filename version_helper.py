"""
Summary
========
Helper file to generate package version numbers for you

Notes
=====
You're probably already using git tags to tag releases of your project. If you
aren't, you really should. Wouldn't it be great if your python package
automatically updated its version number using ``git describe``? You know, so
you don't have to do it manually all the time? It's almost like that's a
feature that should be available without stupid hacks.

But it's not. So here's how to do it with stupid hacks.

There are two modes of operation for version helper: static versioning and
dynamic versioning.

Static Versioning
-----------------
This is the simplest option. In this mode, you specify the version number in
you setup.py and ``__init__.py`` files by hand. Version helper provides a
script that will automatically update those for you. Your ``setup.py`` file
should look like this::

    from mypackage_version import UpdateVersion

    setup(
        name='mypackage',
        version='unknown',
        cmdclass={'update_version': UpdateVersion},
        ...
    )

No, really, the formatting is important. Your ``__init__.py`` file should have
a line in it that declares the version number::

    __version__ = 'unknown'

The command to update these values will be exposed as the value specified in
``cmdclass``::

    python setup.py update_version

This makes it easy to tag and upload your package to pypi::

    python setup.py update_version
    python setup.py test sdist upload

Note that you should not combine the 'update' and 'upload' commands because
setuptools will upload it with the old version number.

Dynamic Versioning
------------------
This option will auto-generate unique per-commit version numbers and stick them
in your project.

When you run ``python setup.py``, if you are running it from inside of a git
repository this script with generate a unique version number and embed it in an
auto-generated file in your package. By default the file is named
'_version.py', and you should add it to your ``.gitignore``. Since this is a
python file and it's in your package, it will get bundled up and distributed
with your package. During the installation process, this script will recognize
that it is not inside a git repository and will parse the version from the
``_version.py`` file.

Your setup.py file should look like this::

    from version_helper import git_version

    setup(
        name='mypackage',
        version=git_version(),
        ...
    )

You're done! To view the auto-generated version number of your package, run::

    python setup.py -V

If you want to embed the version as __version__ (PEP 396), put the following
lines into your package's __init__.py file::

    try:
        from ._version import __version__
    except ImportError:
        __version__ = 'unknown'

This method, while hacked, is useful if you need a CI server to continuously
build and upload your package to an internal pypi.

Hybrid Versioning
-----------------
You *can* use the two methods together. If you combine the two formats for the
``setup.py`` file::

    from version_helper import git_version, UpdateVersion

    setup(
        name='mypackage',
        version=git_version(),
        cmdclass={'update_version': UpdateVersion},
        ...
    )

This will auto-tag your builds. Then when you want to strip out all the fuckery
and just use static version strings you can run the update_version command::

    python setup.py update_version

"""
from __future__ import print_function

import locale
import os
import re
from distutils.core import Command
from distutils.errors import DistutilsOptionError, DistutilsError

import fileinput
import subprocess
from setuptools import find_packages


GIT_DESCRIBE = ('git', 'describe')
GIT_DESCRIBE_ARGS = ('--tags', '--dirty', '--abbrev=40', '--long')


class UpdateVersion(Command):

    """ Setup command that updates hardcoded versions from git tags """

    description = "Update the version number inside _version.py and setup.py"

    user_options = [
        ('package=', 'p', "Name of the package (if ambiguous)"),
        ('tag-prefix=', 't', "Strip this prefix off the git tag"),
        ('match=', 'm', "--match argument passed to 'git describe' "
         "(default [0-9]*)"),
        ('pre', None, "Don't fail on prerelease versions"),
        ('dev', None, "Don't fail on development versions"),
        ('strict', None, "Convert development version strings to follow "
         "PEP440"),
        ('no-strip', None, "Don't attempt to remove all references to "
         "version helper"),
        ('version-mod', None, "The file to write version constants to "
         "(default _version.py) (hybrid mode only)"),
    ]
    boolean_options = ['strict', 'pre', 'dev', 'no-strip']

    def initialize_options(self):
        self.tag_match = None
        self.tag_prefix = ''
        self.strict = 0
        self.pre = 0
        self.dev = 0
        self.no_strip = 0
        self.package = None
        self.version_mod = '_version.py'

    def finalize_options(self):
        if self.tag_match is None:
            self.tag_match = self.tag_prefix + '[0-9]*'
        if self.package is None:
            self.package = find_package()

    def strip_tag(self, version_data):
        """ Strip a prefix off the git tag """
        version_data['tag'] = version_data['tag'][len(self.tag_prefix):]

    def run(self):
        version_data = version_data_from_git(self.tag_match, self.strip_tag,
                                             self.strict)
        if version_data['is_dev']:
            if not self.dev:
                raise DistutilsError("Development version '%(version)s' "
                                     "blocked! Use --dev to override." %
                                     version_data)
        elif not self.pre and version_data['is_prerelease']:
            raise DistutilsError("Prerelease version '%(version)s' blocked! "
                                 "Use --pre to override." % version_data)
        data = {
            'version': version_data['version']
        }
        is_hybrid = replace_dynamic_with_static(version_data['version'])
        if not self.no_strip:
            print("Removing %s from setup.py and MANIFEST.in" % __name__)
            remove_all_references()
        if is_hybrid:
            mod_file = os.path.join(os.path.curdir, self.package,
                                    self.version_mod)
            write_constants_to_mod(mod_file, data)
            print("Set version: %(version)s" % version_data)
        else:
            write_constants_to_setup(data)
            write_constants_to_init(self.package, data)


def find_package():
    """
    Find the correct package

    Returns
    -------
    package_dir : str
        The name of the directory that contains the python package

    Raises
    ------
    error : :class:`distutils.errors.DistutilsOptionError`
        If a single package cannot be found

    """
    candidates = find_packages(exclude=['*.*'])
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) == 0:
        raise DistutilsOptionError("No package found")
    else:
        raise DistutilsOptionError("Multiple possible packages found! "
                                   "Please specify one: %s" % (candidates,))


def parse_constants_from_mod(filename):
    """ Parse python constants from a file """
    if not os.path.exists(filename):
        return {
            'source_label': 'NOTAG',
            'version': 'unknown',
        }
    constants = {}
    with open(filename, 'r') as infile:
        for line in infile:
            components = line.split('=')
            if len(components) <= 1:
                continue
            key = components[0].strip(' _')
            value = '='.join(components[1:]).strip().strip('\'\"')
            if key != 'all':
                constants[key] = value
    return constants


def write_constants_to_mod(filename, constants):
    """ Write python constants to a special 'version' module """
    with open(filename, 'w') as outfile:
        outfile.write('""" This file is auto-generated during the '
                      'package-building process """%s' % os.linesep)
        for key, value in constants.items():
            outfile.write("__%s__ = '%s'%s" % (key, value, os.linesep))
        outfile.write('__all__ = %s%s' % (['__%s__' % key for key in
                                           constants], os.linesep))


def write_constants_to_setup(constants):
    """ Replace constant values in ``setup.py`` """
    filename = os.path.join(os.path.curdir, 'setup.py')
    replace_in_file(filename, constants,
                    r'^(\s*)%s\s*=\s*[\'"].*?[\'"]\s*,?\s*$',
                    r"\1%s='%s',")


def write_constants_to_init(package, constants):
    """ Replace constant values in ``__init__.py`` """
    filename = os.path.join(os.path.curdir, package, '__init__.py')
    replace_in_file(filename, constants,
                    r'^__%s__\s*=\s*["\'].*?["\']\s*$',
                    r"__%s__ = '%s',")


def replace_dynamic_with_static(version):
    """
    If git_version() is being called inside setup.py, replace it and return
    True

    """
    replaced = False
    filename = os.path.join(os.path.curdir, 'setup.py')
    for line in fileinput.FileInput(filename, inplace=True):
        if 'git_version' in line:
            replaced = True
            if 'import' in line:
                pass
            else:
                print(re.sub(r'git_version\s*\(.+\)', "'%s'" % version, line), end='')
        else:
            print(line, end='')
    return replaced


def remove_all_references():
    """ Remove all references to version helper from this package """
    filename = os.path.join(os.path.curdir, 'setup.py')
    import_line = re.compile(r'^(from {0} import|import {0})'.format(__name__))
    cmd_line = re.compile(r'^\s*cmdclass\s*=')
    for line in fileinput.FileInput(filename, inplace=True):
        if not import_line.match(line) and not cmd_line.match(line):
            print(line, end='')

    manifest_file = os.path.join(os.path.curdir, 'MANIFEST.in')
    for line in fileinput.FileInput(manifest_file, inplace=True):
        print(re.sub(r'^include (%s.py)' % __name__, r'exclude \1', line), end='')


def replace_in_file(filename, constants, pattern, replace_pattern):
    """ Replace constant values in a file using regexes """

    sub_args = []
    for key, val in constants.iteritems():
        sub_args.append((
            pattern % key,
            replace_pattern % (key, val),
        ))

    for line in fileinput.FileInput(filename, inplace=True):
        modified = False
        for pattern, replacement in sub_args:
            new_line = re.sub(pattern, replacement, line)
            if new_line != line:
                print(new_line)
                modified = True
                break
        if not modified:
            print(line, end='')


def git_describe(describe_args):
    """
    Pull the version information from git

    Parameters
    ----------
    describe_args : list
        Arguments for ``describe_cmd`` to be passed to subprocess

    Returns
    -------
    data : dict
        Dictionary of repo data. The fields are listed below

    tag : str
        The git tag for this version
    description : str
        The output of ``git describe``
    is_dev : bool
        True if is_dirty or if addl_commits > 0
    is_dirty : bool
        True if the git repo is dirty
    addl_commits : int
        The number of additional commits on top of the tag ref
    ref : str
        The ref for the current commit
    dirty_suffix : str
        The string that would denote that the working copy is dirty

    Raises
    ------
    error : :class:`subprocess.CalledProcessError`
        If there is an error running ``git describe``

    """
    encoding = locale.getdefaultlocale()[1] or 'utf-8'
    proc = subprocess.Popen(GIT_DESCRIBE + describe_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    output = proc.communicate()[0]
    description = output.decode(encoding).strip()
    if proc.returncode != 0:
        print("Error parsing git revision! Make sure that you have tagged a "
              "commit, and that the tag matches the 'tag_match' argument")
        print("Git output: " + description)
        return {
            'tag': 'unknown',
            'description': 'unknown',
            'is_dirty': False,
            'is_dev': True,
            'is_prerelease': True,
            'addl_commits': 0,
            'ref': 'unknown',
            'dirty_suffix': '-dirty',
        }

    components = description.split('-')
    # trim off the dirty suffix
    dirty_suffix = '-dirty'
    is_dirty = False
    for arg in describe_args:
        if arg.startswith('--dirty='):
            dirty_suffix = arg.split('=')[1]
            break
    if dirty_suffix.startswith('-') and components[-1] == dirty_suffix[1:]:
        components = components[:-1]
        is_dirty = True
    elif components[-1].endswith(dirty_suffix):
        components[-1] = components[-1][:-len(dirty_suffix)]
        is_dirty = True

    ref = components[-1][1:]
    addl_commits = int(components[-2])
    tag = '-'.join(components[:-2])
    return {
        'tag': tag,
        'description': description,
        'is_dirty': is_dirty,
        'is_dev': is_dirty or addl_commits > 0,
        'addl_commits': addl_commits,
        'ref': ref,
        'dirty_suffix': dirty_suffix,
    }


def version_data_from_git(tag_match, post_process, strict):
    """
    Convert the raw ``git describe`` data into version info

    Parameters
    ----------
    tag_match : str
        Match only tags with this format (default '[0-9]*'). Note that this
        uses glob matching, not PCRE.
    post_process : callable or None
        A function that accepts the output of :meth:`.git_describe` and
        optionally mutates it. This can be used to convert custom tags into
        version numbers (ex. 'v0.1' => '0.1') (default None)
    strict : bool
        If true, create a PEP 440 compatible version number for development
        versions (default False)

    Returns
    -------
    version_data : dict
        Data dict with all the values from :meth:`~.git_describe` plus the keys
        below

    version : str
        The finalized version string
    is_prerelease : bool
        True if the version is considered 'prerelease'

    """
    describe_args = GIT_DESCRIBE_ARGS
    if tag_match is not None:
        describe_args += ('--match=%s' % tag_match,)
    version_data = git_describe(describe_args)
    if post_process is not None:
        post_process(version_data)
    if version_data['is_dev']:
        if strict:
            version = (version_data['tag'] +
                       ".post0.dev%(addl_commits)d" % version_data)
        else:
            version = "{tag}-{addl_commits}-g{ref:<.7}".format(**version_data)
            if version_data['is_dirty']:
                version += version_data['dirty_suffix']
    else:
        version = version_data['tag']
    version_data['version'] = version
    version_data['is_prerelease'] = bool(re.match(r'^\d+(\.\d+)*$', version))

    return version_data


def git_version(package=None,
                tag_match='[0-9]*',
                version_mod='_version.py',
                post_process=None,
                strict=False):
    """
    Generate the version from the git revision, or retrieve it from the
    auto-generated module

    Parameters
    ----------
    package : str, optional
        The name of the directory that contains the package's code. If not
        specified, it will be inferred.
    tag_match : str, optional
        Match only tags with this format (default '[0-9]*'). Note that this
        uses glob matching, not PCRE.
    version_mod : str, optional
        The name of the file to write the version into (default '_version.py')
    post_process : callable, optional
        A function that accepts the output of :meth:`.git_describe` and
        optionally mutates it. This can be used to convert custom tags into
        version numbers (ex. 'v0.1' => '0.1') (default None)
    strict : bool, optional
        If true, create a PEP 440 compatible version number for development
        versions (default False)

    Returns
    -------
    version : str

    """
    here = os.path.abspath(os.path.dirname(__file__))

    if package is None:
        package = find_package()
    mod_file = os.path.join(here, package, version_mod)

    if not os.path.isdir(os.path.join(here, '.git')):
        data = parse_constants_from_mod(mod_file)
    else:
        version_data = version_data_from_git(tag_match, post_process, strict)
        data = {
            'version': version_data['version']
        }
        write_constants_to_mod(mod_file, data)
    return data['version']
