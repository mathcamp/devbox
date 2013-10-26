#!/usr/bin/env python
"""
Run selected checks on the current git index

This pre-commit hook was originally based on a hook by Lorenzo Bolla
https://github.com/lbolla/dotfiles/blob/master/githooks/pre-commit

"""
import fnmatch
import os
import sys

import contextlib
import json
import shlex
import shutil
import subprocess
import tempfile


CONF_FILE = '.gitbox.conf'


def convert_command(cmd):
    """ If a command is a string, convert it to list form for subprocess """
    if isinstance(cmd, basestring):
        return shlex.split(cmd)
    return cmd


@contextlib.contextmanager
def pushd(directory):
    """ CD into the directory inside a 'with' block """
    curdir = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(curdir)


def run_checks(conf, tmpdir):
    """ Run selected checks on the current git index """
    modified = subprocess.check_output(['git', 'diff', '--cached',
                                        '--name-only', '--diff-filter=ACMRT'])
    modified = [name.strip() for name in modified.splitlines()]
    retcode = 0
    path = os.environ['PATH']
    if 'env' in conf:
        binpath = os.path.join(os.path.abspath(conf['env']['path']), 'bin')
        path = binpath + ':' + path
    with pushd(tmpdir):
        for pattern, commands in conf.get('hooks_modified', {}).iteritems():
            for filename in modified:
                if not fnmatch.fnmatch(filename, pattern):
                    continue
                printed_filename = False
                for command in commands:
                    command = convert_command(command)
                    proc = subprocess.Popen(command + [filename],
                                            env={'PATH': path},
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
                    output, _ = proc.communicate()
                    if proc.returncode != 0:
                        if not printed_filename:
                            print filename
                            print '=' * len(filename)
                            printed_filename = True
                        print command[0]
                        print '-' * len(command[0])
                        print output
                        retcode |= proc.returncode

        for command in conf.get('hooks_all', []):
            command = convert_command(command)
            retcode |= subprocess.call(command)

    return retcode


def load_conf():
    """ Load configuration parameters from the conf file """
    if os.path.exists(CONF_FILE):
        with open(CONF_FILE, 'r') as infile:
            return json.load(infile)
    else:
        return {}


def precommit(exit=True):
    """ Run all the pre-commit checks """
    tmpdir = tempfile.mkdtemp()

    try:
        # Put the code being checked-in into the temp dir
        subprocess.check_call(['git', 'checkout-index', '-a', '--prefix=%s/' %
                              tmpdir, '--'])
        submodule_output = subprocess.check_output(['git', 'submodule'])
        # TODO: Use git clone on the submodules as well
        for line in submodule_output.splitlines():
            sub_parts = line.split()
            if len(sub_parts) > 0:
                target = os.path.join(tmpdir, sub_parts[1])
                os.rmdir(target)
                shutil.copytree(sub_parts[1], target)
        retcode = run_checks(load_conf(), tmpdir)
        if exit:
            sys.exit(retcode)
        else:
            return retcode
    finally:
        shutil.rmtree(tmpdir)

if __name__ == '__main__':
    precommit()
