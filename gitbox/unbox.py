#!/usr/bin/env python
""" Clone and set up a developer repository """
import os
import re

import argparse
import json
import shutil
import subprocess


CONF_FILE = 'gitbox.conf'
AUTOENV_REPO = 'git://github.com/kennethreitz/autoenv.git'
HOME = os.environ['HOME']


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


def unbox():
    """ Clone and set up a developer repository """
    parser = argparse.ArgumentParser(description=unbox.__doc__)
    parser.add_argument('repo', help="Git url or file path of the repository "
                        "to unbox")
    parser.add_argument('dest', nargs='?', help="Directory to clone into")
    parser.add_argument('-y', action='store_true', help="Auto-yes")
    parser.add_argument('-v', help="Virtualenv binary", default='virtualenv')
    args = vars(parser.parse_args())

    if os.path.exists(args['repo']) and args['dest'] is None:
        # 'repo' is a file path, not a git url
        args['dest'] = args['repo']
    else:
        name_pattern = re.compile(r'[A-Za-z0-9_\-]+')
        if not args['dest']:
            all_words = name_pattern.findall(args['repo'])
            if all_words[-1] == 'git':
                all_words.pop()
            args['dest'] = all_words[-1]

    if not os.path.exists(args['dest']):
        print "Cloning repository"
        subprocess.check_call(['git', 'clone', args['repo'], args['dest']])

    os.chdir(args['dest'])
    print "Updating repository"
    # Update the repo safely (don't discard changes)
    subprocess.call(['git', 'pull', '--ff-only'])
    # Update any submodules
    subprocess.call(['git', 'submodule', 'update', '--init',
                     '--recursive'])

    # Symlink to git hooks
    if os.path.exists('git_hooks') and not os.path.islink('.git/hooks'):
        print "Installing git hooks"
        shutil.rmtree('.git/hooks')
        os.symlink('../git_hooks', '.git/hooks')

    if not os.path.exists(CONF_FILE):
        return

    with open(CONF_FILE, 'r') as infile:
        conf = json.load(infile)

    # Create virtualenv
    path = conf['env']['path']
    if not os.path.exists(path):
        print "Creating virtualenv"
        cmd = [args['v']] + conf['env']['args'] + [path]
        subprocess.check_call(cmd)

    # Install requirements if present
    pip = os.path.join(path, 'bin', 'pip')
    if os.path.exists('requirements_dev.txt'):
        print "Installing requirements"
        subprocess.check_call([pip, 'install', '-r',
                               'requirements_dev.txt'])
    print "Installing package"
    subprocess.check_call([pip, 'install', '-e', '.'])

    # Install autoenv if necessary
    if conf.get('autoenv'):
        if not os.path.exists(os.path.join(HOME, '.autoenv')):
            if args['y'] or \
                    promptyn("Would you like to install autoenv?", True):
                print "Installing autoenv"
                autoenv = os.path.join(HOME, '.autoenv')
                subprocess.check_call(['git', 'clone', AUTOENV_REPO, autoenv])

                activate = os.path.join(autoenv, 'activate.sh')
                with open(os.path.join(HOME, '.bashrc'), 'a') as outfile:
                    outfile.write('\n')
                    outfile.write('source ' + activate)

    # Run any post-setup commands
    if conf.get('post_setup'):
        for command in conf.get('post_setup'):
            subprocess.Popen(command, env={'PATH': os.path.join(path, 'bin')})


if __name__ == '__main__':
    unbox()
