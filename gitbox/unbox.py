#!/usr/bin/env python
"""
Clone and set up a developer repository

This file was carefully constructed to have no dependencies on other files in
the ``gitbox`` package. This allows it to be downloaded separately and run
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


CONF_FILE = '.gitbox.conf'
HOME = os.environ['HOME']


def load_conf(directory=os.curdir):
    """ Load the gitbox conf file """
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


def pre_setup(conf, dest):
    """ Run any pre-setup scripts """
    with pushd(dest):
        for command in conf.get('pre_setup', []):
            if isinstance(command, basestring):
                command = shlex.split(command)
            subprocess.Popen(command)


def setup_git_hooks(dest):
    """ Set up a symlink to the git hooks directory """
    with pushd(dest):
        # Symlink to git hooks
        if os.path.exists('git_hooks') and not os.path.islink('.git/hooks'):
            print "Installing git hooks"
            shutil.rmtree('.git/hooks')
            os.symlink('../git_hooks', '.git/hooks')


def update_repo(repo, dest):
    """ Make sure the repository is up-to-date """
    with pushd(dest):
        print "Updating", repo
        # Update the repo safely (don't discard changes)
        subprocess.call(['git', 'pull', '--ff-only'])
        # Update any submodules
        subprocess.call(['git', 'submodule', 'update', '--init',
                        '--recursive'])


def create_virtualenv(conf, dest, virtualenv_cmd, parent_virtualenv, is_dep):
    """
    Create a virtualenv, or link to the correct virtualenv

    Parameters
    ----------
    conf : dict
        The gitbox conf data
    dest : str
        The name of the repository to create the virtualenv for
    virtualenv_cmd : str
        The path to the virtualenv command to use for creating a virtualenv
    parent_virtualenv : str or None
        The path to the parent's virtualenv, or None
    is_dep : bool
        If True, this repo is being set up as a dependency for another repo

    Returns
    -------
    virtualenv : str
        The path to this

    """
    if not conf.get('env'):
        return
    with pushd(dest):
        # If installing as a dependency, link to prior virtualenv
        if parent_virtualenv is not None \
                and not os.path.exists(conf['env']['path']):
            os.symlink(parent_virtualenv, conf['env']['path'])

        if not os.path.exists(conf['env']['path']):
            # If parent is defined, try to link to the parent's virtualenv
            if not is_dep and conf.get('parent'):
                parent = os.path.join(os.pardir, conf['parent'])
                if os.path.exists(parent):
                    parent_conf = load_conf(parent)
                    parent_venv = os.path.join(parent,
                                               parent_conf['env']['path'])
                    if os.path.exists(parent_venv):
                        os.symlink(parent_venv, conf['env']['path'])
            else:
                print "Creating virtualenv"
                cmd = ([virtualenv_cmd] + conf['env']['args'] +
                       [conf['env']['path']])
                subprocess.check_call(cmd)


def post_setup(conf, dest):
    """ Run any post-setup scripts """
    with pushd(dest):
        for command in conf.get('post_setup', []):
            if isinstance(command, basestring):
                command = shlex.split(command)
            kwargs = {}
            if conf.get('env', {}).get('path') is not None:
                kwargs['env'] = {
                    'PATH': os.path.join(conf['env']['path'], 'bin')
                }
            subprocess.Popen(command, **kwargs)


def unbox(repo, dest, virtualenv_cmd, parent_virtualenv, is_dep, setup_deps):
    """
    Set up a repository for development

    Parameters
    ----------
    repo : str
        The url of the git repository, or a path to the already cloned repo
    dest : str or None
        The directory to clone into, or None to use the default
    virtualenv_cmd : str
        The path to the virtualenv binary
    parent_virtualenv : str or None
        Path to the virtualenv to use for the installation. None will use the
        settings inside gitbox.conf
    is_dep : bool
        True if this repo is being installed as a dependency for another boxed
        repo
    setup_deps : bool
        If True, clone and set up any repos marks as a dependency in the conf

    """
    if os.path.exists(repo) and dest is None:
        # 'repo' is a file path, not a git url
        dest = repo
    else:
        if not dest:
            dest = repo_name_from_url(repo)

    if not os.path.exists(dest):
        print "Cloning", repo
        subprocess.check_call(['git', 'clone', repo, dest])

    update_repo(repo, dest)
    conf = load_conf(dest)
    pre_setup(conf, dest)
    setup_git_hooks(dest)
    create_virtualenv(conf, dest, virtualenv_cmd, parent_virtualenv, is_dep)

    # Install other gitbox repos, if any
    if conf.get('env'):
        virtualenv = os.path.join(os.path.pardir, dest, conf['env']['path'])
    else:
        virtualenv = None
    if setup_deps:
        for dep in conf.get('dependencies', []):
            unbox(dep, None, virtualenv_cmd, virtualenv, True, True)

    post_setup(conf, dest)


def main():
    """ Clone and set up a developer repository """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('repo', help="Git url or file path of the repository "
                        "to unbox")
    parser.add_argument('dest', nargs='?', help="Directory to clone into")
    parser.add_argument('-v', help="Virtualenv binary", default='virtualenv')
    parser.add_argument('--no-deps', action='store_true',
                        help="Do not clone and set up the dependencies")
    args = vars(parser.parse_args())

    unbox(args['repo'], args['dest'], args['v'], None, False, args['--no-deps'])


if __name__ == '__main__':
    main()
