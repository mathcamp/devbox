""" Box creation helper script """
import os
import stat

import json
import shutil

from .unbox import CONF_FILE


def append(lines, filename):
    """ Append one or more lines to a file if they are not already present """
    prepend_newline = False
    if os.path.exists(filename):
        with open(filename, 'r') as infile:
            text = infile.read()
            if text and not text.endswith('\n'):
                prepend_newline = True
            file_lines = set(text.splitlines())
    else:
        file_lines = set()

    to_append = set(lines) - file_lines
    if to_append:
        with open(filename, 'a') as outfile:
            if prepend_newline:
                outfile.write('\n')
            for line in lines:
                if line in to_append:
                    outfile.write(line)
                    outfile.write('\n')


def copy_static(name, dest):
    """ Copy one of the static files to a destination """
    destfile = os.path.join(dest, name)
    srcfile = os.path.join(os.path.dirname(__file__), os.pardir, name)
    shutil.copyfile(srcfile, destfile)
    return destfile


def create(repo, standalone, template_create=None):
    """ Set up a repository with devbox """
    if not os.path.exists(repo):
        os.makedirs(repo)

    conf = {
        'dependencies': [],
        'pre_setup': [],
        'post_setup': [],
        'hooks_all': [],
        'hooks_modified': [],
    }
    pre_commit = []

    # Prohibit trailing whitespace
    pre_commit.append("git diff-index --check --cached HEAD --")

    hookdir = os.path.join(repo, 'git_hooks')
    if not os.path.exists(hookdir):
        os.makedirs(hookdir)

    if template_create is not None:
        template_create(repo, conf)

    # Construct the proper pre-commit hook command
    if standalone:
        hookfile = os.path.join(hookdir, 'hook.py')
        shutil.copyfile(os.path.join(os.path.dirname(__file__), 'hook.py'),
                        hookfile)
        if 'env' in conf:
            python = os.path.join(conf['env']['path'], 'bin', 'python')
        else:
            python = 'python'
        hook_cmd = python + ' ' + os.path.join('git_hooks', 'hook.py')
    else:
        if 'env' in conf:
            hook_cmd = os.path.join(conf['env']['path'], 'bin',
                                    'devbox-pre-commit')
            conf['post_setup'].append('pip install devbox')
        else:
            hook_cmd = 'devbox-pre-commit'

    if 'env' in conf and not os.path.isabs(conf['env']['path']):
        hook_cmd = os.path.join('.', hook_cmd)
    pre_commit.append(hook_cmd)

    # Write the pre-commit file
    precommit_file = os.path.join(hookdir, 'pre-commit')
    if not os.path.exists(precommit_file):
        pre_commit.insert(0, "#!/bin/bash -e")
    append(pre_commit, precommit_file)
    st = os.stat(precommit_file)
    os.chmod(precommit_file, st.st_mode | stat.S_IEXEC)

    # Write the conf file
    conf_file = os.path.join(repo, CONF_FILE)
    with open(conf_file, 'w') as outfile:
        json.dump(conf, outfile)


def create_python(repo, conf):
    """
    Basic python template. Runs pylint, pep8, and unit tests on commit.
    Creates a virtualenv & autoenv file.

    """
    conf['env'] = {
        'path': os.path.basename(os.path.abspath(repo)) + '_env',
        'args': [],
    }

    # Developers should install some analysis tools
    requirements = [
        'pylint',
        'pep8',
        'autopep8',
    ]
    append(requirements, os.path.join(repo, 'requirements_dev.txt'))
    conf['post_setup'].append('pip install -r requirements_dev.txt')
    conf['post_setup'].append('pip install -e .')

    # Run pylint and pep8 on modified python files
    conf['hooks_modified'].extend([
        ['*.py', ['pylint', '--rcfile=.pylintrc']],
        ['*.py', ['pep8', '--config=.pep8.ini']],
    ])
    conf['hooks_all'].append('python setup.py test')
    copy_static('.pylintrc', repo)
    copy_static('.pep8.ini', repo)

    # Add a script that runs autopep8 on repo
    autopep8 = copy_static('run_autopep8.sh', repo)
    st = os.stat(autopep8)
    os.chmod(autopep8, st.st_mode | stat.S_IEXEC)

    # Include the version_helper.py script
    copy_static('version_helper.py', repo)
    append(['include version_helper.py'],
           os.path.join(repo, 'MANIFEST.in'))

    # Add the autoenv file to activate the virtualenv
    envfile = os.path.join(repo, '.env')
    if not os.path.exists(envfile):
        with open(envfile, 'w') as outfile:
            outfile.write(r'_envdir=$(dirname "$1")')
            outfile.write(os.linesep)
            outfile.write(r'source ' + os.path.join(r'$_envdir',
                                                    conf['env']['path'], 'bin',
                                                    'activate'))

    # Write the virtualenv file to .gitignore
    append([conf['env']['path']], os.path.join(repo, '.gitignore'))


TEMPLATES = {
    'python': create_python,
    'base': None,
}


def main(args=None):
    """ Create box metadata files in a repository """
    import sys
    import argparse
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description=create.__doc__)
    parser.add_argument('repo', help="Location of the repository to box")
    parser.add_argument('-t', default='base', help="Template (default "
                        "%(default)s)", choices=list(TEMPLATES.keys()))
    parser.add_argument('-s', '--standalone', action='store_true',
                        help="Don't require devbox to be installed for the "
                        "hooks to run")
    parser.add_argument('-l', '--list-templates', action='store_true',
                        help="List all available templates")

    # Short-circuit --list-templates so it behaves like -h
    if '-l' in args or '--list-templates' in args:
        longest_name = max([len(name) for name in TEMPLATES])
        indent = os.linesep + ' ' * (longest_name + 3)
        print("Devbox templates")
        print("================")
        for name, meth in TEMPLATES.items():
            doc = (meth or create).__doc__.strip()
            doc = indent.join([line.strip() for line in doc.splitlines()])
            print("%s  %s" % ((name + ':').ljust(longest_name + 1), doc))
        return

    args = vars(parser.parse_args(args))
    # TODO: Until I upload this to pypi, always use standalone mode
    args['standalone'] = True

    create(args['repo'], args['standalone'], TEMPLATES[args['t']])
