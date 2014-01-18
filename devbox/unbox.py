#!/usr/bin/env python
"""
Clone and set up a developer repository

This file was carefully constructed to have no dependencies on other files in
the ``devbox`` package. This allows it to be downloaded separately and run
directly as a script to perform the "unbox" operation.

"""
import os
import re
import stat
import sys
from distutils.spawn import find_executable  # pylint: disable=E0611,F0401

import argparse
import contextlib
import json
import logging
import shlex
import shutil
import subprocess


try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve  # pylint: disable=E0611,F0401

LOG = logging.getLogger(__name__)
CONF_FILE = '.devbox.conf'
URL_SCRIPT = re.compile(r'^(http|https|ftp)://.+$')
VENV_VERSION = '1.10.1'
VENV_URL = ("https://pypi.python.org/packages/source/v/"
            "virtualenv/virtualenv-%s.tar.gz" % VENV_VERSION)


def load_conf(directory=os.curdir):
    """ Load the devbox conf file """
    filename = os.path.join(directory, CONF_FILE)
    if os.path.exists(filename):
        with open(filename, 'r') as infile:
            return json.load(infile)
    else:
        return {}


@contextlib.contextmanager
def pushd(path):
    """ Context manager for temporarily changing directories """
    tmp = os.path.abspath(os.curdir)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(tmp)


def repo_name_from_url(url):
    """ Parse the repository name out of a git repo url """
    name_pattern = re.compile(r'[A-Za-z0-9_\-]+')
    all_words = name_pattern.findall(url)
    # Repos sometimes end with ".git"
    if all_words[-1] == 'git':
        all_words.pop()
    return all_words[-1]


def run_commands(commands, venv=None):
    """
    Run a list of setup commands

    Parameters
    ----------
    commands : list
        List of strings or lists that will be run
    venv : dict, optional
        The venv dict from the devbox config. If present, will run all commands
        inside that virtualenv.

    """
    for command in commands:
        if not isinstance(command, list):
            # Hacking around a unicode bug with shlex in old versions of python
            if sys.version_info[0] < 3:
                command = command.encode('utf-8')
            command = shlex.split(command)
        LOG.debug("Running command: %s", ' '.join(command))
        kwargs = {}
        # add the venv to the path
        if venv is not None:
            kwargs['env'] = {
                'PATH': os.path.join(os.path.curdir, venv['path'], 'bin') +
                os.pathsep + os.environ['PATH']
            }
        path = None
        # If the command is a url, download that script and run it
        if URL_SCRIPT.match(command[0]):
            path = urlretrieve(command[0])[0]
            st = os.stat(path)
            os.chmod(path, st.st_mode | stat.S_IEXEC)
            command = [path] + command[1:]

        subprocess.check_call(command, **kwargs)

        # If we downloaded a script, clean it up
        if path is not None:
            os.unlink(path)


def setup_git_hooks():
    """ Set up a symlink to the git hooks directory """
    # Symlink to git hooks
    if os.path.exists('git_hooks') and not os.path.islink('.git/hooks'):
        LOG.info("Installing git hooks")
        shutil.rmtree('.git/hooks')
        os.symlink('../git_hooks', '.git/hooks')


def update_repo(repo):
    """ Safely update repo and submodules (doesn't overwrite changes) """
    LOG.info("Updating %s", repo)
    # Update the repo safely (don't discard changes)
    subprocess.call(['git', 'pull', '--ff-only'])
    # Update any submodules
    subprocess.call(['git', 'submodule', 'update', '--init',
                    '--recursive'])


def create_virtualenv(env):
    """
    Create a virtualenv, or link to the correct virtualenv

    Parameters
    ----------
    env : dict
        The 'env' key from the config file. Contains 'path' and 'args'.

    Returns
    -------
    virtualenv : str
        The absolute path to the created virtualenv

    """
    if not os.path.exists(env['path']):
        LOG.info("Creating virtualenv %s", env['path'])
        # If virtualenv command exists, use that
        if find_executable('virtualenv') is not None:
            cmd = ['virtualenv'] + env['args'] + [env['path']]
            subprocess.check_call(cmd)
        else:
            # Otherwise, download virtualenv from pypi
            path = urlretrieve(VENV_URL)[0]
            subprocess.check_call(['tar', 'xzf', path])
            subprocess.check_call(
                [sys.executable, "virtualenv-%s/virtualenv.py" % VENV_VERSION]
                + env['args'] + [env['path']])
            os.unlink(path)
            shutil.rmtree("virtualenv-%s" % VENV_VERSION)

    return os.path.abspath(env['path'])


def unbox(repo, dest=None, no_deps=False, *parents):
    """
    Set up a repository for development

    Parameters
    ----------
    repo : str
        The url of the git repository, or a path to the already cloned repo
    dest : str or None
        The directory to clone into, or None to use the default
    no_deps : bool
        If True, don't clone and set up dependency repos
    *parents : list
        Peer repositories to install into

    """
    parents = list(parents)
    if os.path.exists(repo) and dest is None:
        # 'repo' is a file path, not a git url
        dest = repo
    else:
        if not dest:
            dest = repo_name_from_url(repo)

    if not os.path.exists(dest):
        LOG.info("Cloning %s", repo)
        subprocess.check_call(['git', 'clone', repo, dest])

    with pushd(dest):
        update_repo(repo)
        conf = load_conf()
        run_commands(conf.get('pre_setup', []))
        setup_git_hooks()

        # If python, set up a virtualenv
        if conf.get('env'):
            create_virtualenv(conf['env'])

        if 'parent' in conf:
            parents.append(conf['parent'])

    # Install other devbox repos, if any
    if not no_deps:
        for dep in conf.get('dependencies', []):
            LOG.info("Setting up dependency %s", dep)
            unbox(dep, None, no_deps, dest, *parents)

    # Install self into any parent virtualenvs
    for install_dir in [dest] + parents:
        LOG.info("Installing into %s", install_dir)
        dest_conf = load_conf(install_dir)
        venv = dest_conf.get('env')
        if venv is not None:
            venv['path'] = os.path.abspath(venv['path'])
        with pushd(dest):
            run_commands(conf.get('post_setup', []), venv)

LEVEL_MAP = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARN,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}


def main(args=None):
    """ Clone and set up a developer repository """
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('repo', help="Git url or file path of the repository "
                        "to unbox")
    parser.add_argument('dest', nargs='?', help="Directory to clone into")
    parser.add_argument('--no-deps', action='store_true',
                        help="Do not clone and set up the dependencies")
    parser.add_argument('-l', '--level', default='info',
                        choices=LEVEL_MAP.keys(), help="Logging level")

    args = vars(parser.parse_args(args))
    LOG.setLevel(LEVEL_MAP[args.pop('level')])
    logging.basicConfig()

    unbox(**args)


if __name__ == '__main__':
    main()
