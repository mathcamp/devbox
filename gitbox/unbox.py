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


def unbox():
    """ Clone and set up a developer repository """
    parser = argparse.ArgumentParser(description=unbox.__doc__)
    parser.add_argument('repo', help="Git url or file path of the repository "
                        "to unbox")
    parser.add_argument('dest', nargs='?', help="Directory to clone into")
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
    subprocess.check_call(['git', 'submodule', 'update', '--init',
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
    if 'env' in conf:
        path = conf['env']['path']
        if not os.path.exists(path):
            print "Creating virtualenv"
            cmd = args['v'] + conf['env']['args'] + [path]
            subprocess.check_call(cmd)

        pip = os.path.join(path, 'bin', 'pip')
        if os.path.exists('requirements_dev.txt'):
            print "Installing requirements"
            subprocess.check_call([pip, 'install', '-r',
                                   'requirements_dev.txt'])
        print "Installing package"
        subprocess.check_call([pip, 'install', '-e', '.'])

        if conf.get('autoenv'):
            if not os.path.exists(os.path.join(HOME, '.autoenv')):
                print "Installing autoenv"
                autoenv = os.path.join(HOME, '.autoenv')
                subprocess.check_call(['git', 'clone', AUTOENV_REPO, autoenv])

                activate = os.path.join(autoenv, 'activate.sh')
                with open(os.path.join(HOME, '.bashrc'), 'a') as outfile:
                    outfile.write('\n')
                    outfile.write('source ' + activate)

if __name__ == '__main__':
    unbox()
