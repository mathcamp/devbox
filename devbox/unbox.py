#!/usr/bin/env python
"""
Clone and set up a developer repository

This file was carefully constructed to have no dependencies on other files in
the ``devbox`` package. This allows it to be downloaded separately and run
directly as a script to perform the "unbox" operation.

"""
import os
import re

import argparse
import contextlib
import shlex
import json
import shutil
import subprocess


CONF_FILE = '.devbox.conf'
HOME = os.environ['HOME']


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
    if all_words[-1] == 'git':
        all_words.pop()
    return all_words[-1]


def pre_setup(conf):
    """ Run any pre-setup scripts """
    for command in conf.get('pre_setup', []):
        if not isinstance(command, list):
            command = shlex.split(command)
        subprocess.check_call(command)


def setup_git_hooks():
    """ Set up a symlink to the git hooks directory """
    # Symlink to git hooks
    if os.path.exists('git_hooks') and not os.path.islink('.git/hooks'):
        print("Installing git hooks")
        shutil.rmtree('.git/hooks')
        os.symlink('../git_hooks', '.git/hooks')


def update_repo(repo):
    """ Make sure the repository is up-to-date """
    print("Updating", repo)
    # Update the repo safely (don't discard changes)
    subprocess.call(['git', 'pull', '--ff-only'])
    # Update any submodules
    subprocess.call(['git', 'submodule', 'update', '--init',
                    '--recursive'])


def create_virtualenv(env, venv_bin, venv, parent):
    """
    Create a virtualenv, or link to the correct virtualenv

    Parameters
    ----------
    env : dict
        The 'env' key from the config file. Contains 'path' and 'args'.
    venv_bin : str
        The path to the virtualenv command to use for creating a virtualenv
    venv : str or None
        The path to the parent's virtualenv, or None
    parent : str or None
        If present, search for a repo named this as a peer of the current repo,
        and symlink to that repo's virtualenv if present.

    Returns
    -------
    virtualenv : str
        The absolute path to the created virtualenv

    """
    # If installing as a dependency, link to prior virtualenv
    if venv is not None and not os.path.exists(env['path']):
        os.symlink(venv, env['path'])

    # If parent is defined, try to link to the parent's virtualenv
    if parent is not None and not os.path.exists(env['path']):
        parent_path = os.path.join(os.pardir, parent)
        if os.path.exists(parent_path):
            parent_conf = load_conf(parent_path)
            venv = os.path.join(parent_path,
                                parent_conf['env']['path'])
            if os.path.exists(venv):
                os.symlink(venv, env['path'])

    # Otherwise, create a new virtualenv
    if not os.path.exists(env['path']):
        print("Creating virtualenv")
        cmd = ([venv_bin] + env['args'] +
               [env['path']])
        subprocess.check_call(cmd)

    return os.path.abspath(env['path'])


def post_setup(conf):
    """ Run any post-setup scripts """
    for command in conf.get('post_setup', []):
        if not isinstance(command, list):
            command = shlex.split(command)
        kwargs = {}
        if conf.get('env', {}).get('path') is not None:
            kwargs['env'] = {
                'PATH': os.path.join(os.path.curdir, conf['env']['path'],
                                     'bin') + ':' + os.environ['PATH']
            }
        subprocess.check_call(command, **kwargs)


def unbox(repo, dest=None, no_deps=False, venv_bin='virtualenv', venv=None):
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
    venv_bin : str
        The path to the virtualenv binary
    venv : str or None
        If not None, symlink to this path instead of creating a virtualenv

    """
    if os.path.exists(repo) and dest is None:
        # 'repo' is a file path, not a git url
        dest = repo
    else:
        if not dest:
            dest = repo_name_from_url(repo)

    if not os.path.exists(dest):
        print("Cloning", repo)
        subprocess.check_call(['git', 'clone', repo, dest])

    with pushd(dest):
        update_repo(repo)
        conf = load_conf()
        pre_setup(conf)
        setup_git_hooks()

        # If python, set up a virtualenv
        if conf.get('env'):
            venv = create_virtualenv(conf['env'], venv_bin, venv,
                                     conf.get('parent'))

    # Install other devbox repos, if any
    if not no_deps:
        for dep in conf.get('dependencies', []):
            unbox(dep, None, no_deps, venv_bin, venv)

    with pushd(dest):
        post_setup(conf)


def main():
    """ Clone and set up a developer repository """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('repo', help="Git url or file path of the repository "
                        "to unbox")
    parser.add_argument('dest', nargs='?', help="Directory to clone into")
    parser.add_argument('--no-deps', action='store_true',
                        help="Do not clone and set up the dependencies")

    group = parser.add_argument_group('python')
    group.add_argument('--venv-bin', help="Virtualenv binary "
                       "(default '%(default)s')",
                       default='virtualenv')
    group.add_argument('--venv', help="Path to virtualenv to install into. "
                       "Will symlink to this virtualenv instead of creating "
                       "a new one.")

    args = vars(parser.parse_args())

    unbox(**args)


if __name__ == '__main__':
    main()
