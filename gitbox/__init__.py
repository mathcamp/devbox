""" Box creation helper script """
import os
import stat

import argparse
import json
import shutil
from collections import defaultdict

from .hook import CONF_FILE


def prompt(msg, default=None, arg_type=str):
    """ Prompt the user for input """
    value = raw_input(msg + ' ')
    if not value.strip():
        return default
    return arg_type(value)


def promptyn(msg, default=None):
    """ Display a blocking prompt until the user confirms """
    while True:
        yes = "Y" if default else "y"
        if default or default is None:
            no = "n"
        else:
            no = "N"
        confirm = raw_input("%s [%s/%s] " % (msg, yes, no))
        confirm = confirm.lower().strip()
        if confirm == "y" or confirm == "yes":
            return True
        elif confirm == "n" or confirm == "no":
            return False
        elif len(confirm) == 0 and default is not None:
            return default


def copy_static(name, dest):
    """ Copy one of the static files to a destination """
    src = os.path.join(os.path.dirname(__file__), os.pardir, 'pylint')
    # Check the paths so there's no crash when gitbox boxes itself
    if os.path.abspath(src) != os.path.abspath(dest):
        shutil.copyfile(os.path.join(src, name), os.path.join(dest, name))


def configure(repo):
    """ Prompt user for default values """
    standalone = promptyn("If standalone mode is disabled, your pre-commit "
                          "hooks will require gitbox to be "
                          "installed\nStandalone mode?", True)

    conf = {'all': []}

    env = prompt("Path of virtualenv (relative to repository root)? "
                 "[venv]", 'venv')
    conf['env'] = {
        'path': env,
        'args': [],
    }
    conf['autoenv'] = promptyn("Use autoenv?", True)

    modified = defaultdict(list)
    requirements = []
    install_pylintrc = False
    install_pep8 = False
    check_whitespace = False
    if promptyn("Run pylint on commit?", True):
        modified['*.py'].append(['pylint', '--rcfile=pylint/pylintrc'])
        requirements.append('pylint')
        install_pylintrc = True

    if promptyn("Run PEP8 on commit?", True):
        modified['*.py'].append(['pep8', '--config=pylint/pep8.ini'])
        install_pep8 = True
        requirements.append('pep8')

    if promptyn("Run pyflakes on commit?", False):
        modified['*.py'].append(['pyflakes'])
        requirements.append('pyflakes')

    if promptyn("Prohibit trailing whitespace?", True):
        check_whitespace = True

    if promptyn("Pylint entire package on commit? (slooooow)", False):
        conf['all'].append(['pylint', '--rcfile=pylint/pylintrc',
                            repo])
        install_pylintrc = True

    hookdir = os.path.join(repo, 'git_hooks')
    if not os.path.exists(hookdir):
        os.makedirs(hookdir)

    if standalone:
        hookfile = os.path.join(hookdir, 'hook.py')
        shutil.copyfile(os.path.join(os.path.dirname(__file__), 'hook.py'),
                        hookfile)
        python = os.path.join(env, 'bin', 'python')
        hook_cmd = python + ' ' + os.path.join('git_hooks', 'hook.py')
    else:
        hook_cmd = os.path.join(env, 'bin', 'gitbox-pre-commit')

    if not os.path.isabs(env):
        hook_cmd = os.path.join('.', hook_cmd)

    precommit = os.path.join(hookdir, 'pre-commit')
    with open(precommit, 'w') as outfile:
        outfile.write("#!/bin/bash -e\n")
        if check_whitespace:
            outfile.write("git diff-index --check --cached HEAD --\n")
        outfile.write(hook_cmd)
    st = os.stat(precommit)
    os.chmod(precommit, st.st_mode | stat.S_IEXEC)

    # Write the required packages to a file
    if requirements:
        require_file = os.path.join(repo, 'requirements_dev.txt')
        with open(require_file, 'w') as outfile:
            outfile.write('\n'.join(requirements))

    # Create the pylint & pep8 config files
    if install_pylintrc or install_pep8:
        pylintdir = os.path.join(repo, 'pylint')
        if not os.path.exists(pylintdir):
            os.makedirs(pylintdir)
        if install_pylintrc:
            copy_static('pylintrc', pylintdir)
        if install_pep8:
            copy_static('pep8.ini', pylintdir)

    if conf.get('autoenv'):
        with open(os.path.join(repo, '.env'), 'w') as outfile:
            if os.path.isabs(env):
                outfile.write(r'source ' + os.path.join(env, 'bin',
                                                    'activate'))
            else:
                outfile.write(r"_envdir=$(dirname "
                              r"${_files[_file-__array_offset]})")
                outfile.write('\n')
                outfile.write(r'source $_envdir/' + os.path.join(env, 'bin',
                                                   'activate'))

    conf['modified'] = dict(modified)
    conf_file = os.path.join(repo, CONF_FILE)
    with open(conf_file, 'w') as outfile:
        json.dump(conf, outfile)

    print "Box files created! Now just add and commit them."


def create():
    """ Create box metadata files in a repository """
    parser = argparse.ArgumentParser(description=create.__doc__)
    parser.add_argument('repo', help="Location of the repository to box")
    args = vars(parser.parse_args())
    try:
        configure(args['repo'])
    except KeyboardInterrupt:
        print
