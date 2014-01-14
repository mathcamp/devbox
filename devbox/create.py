""" Box creation helper script """
import os
import stat

import json
import shutil
from pkg_resources import resource_string

from .hook import check_output
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


def copy_static(name, dest, destname=None):
    """ Copy one of the static files to a destination """
    destname = destname or name
    destfile = os.path.join(dest, destname)
    srcfile = os.path.join(os.path.dirname(__file__), os.pardir, name)
    shutil.copyfile(srcfile, destfile)
    return destfile


def render(dest, name, template, *args, **kwargs):
    """
    Render a file from the templates directory and write to a file

    Parameters
    ----------
    dest : str
        The directory into which to write the file
    name : str
        The name of the file you want written
    template : str
        Path to the template
    _package : str, optional
        The package that contains the template (default 'devbox')
    _prefix : str, optional
        A path prefix for the template (default 'templates/')
    *args : list
        Any arguments to pass to the str.format() call
    **kwargs : dict
        Any kwargs to pass to the str.format() call

    """
    pkg = kwargs.pop('_package', __package__)
    prefix = kwargs.pop('_prefix', 'templates/')
    filename = os.path.join(dest, name)
    file_dir = os.path.dirname(filename)
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    with open(filename, 'w') as outfile:
        tmpl = resource_string(pkg, prefix + template).decode('utf-8')
        outfile.write(tmpl.format(*args, **kwargs))
    return filename


def create(repo, standalone, force, template_create=None):
    """
    Set up a repository with devbox

    Parameters
    ----------
    repo : str
        Path to create the new project in
    standalone : bool
        If True, embed the hook.py script in the git_hooks directory
    force : bool
        If True, overwrite any existing files at the location
    template_create : callable, optional
        Additional function to run during setup. Takes args (repo, standalone,
        conf) where conf is the pending configuration dict.

    """
    if not os.path.exists(repo):
        os.makedirs(repo)
    elif not force:
        raise Exception("'%s' already exists! Pass in '-f' to overwrite "
                        "existing files" % repo)

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
        template_create(repo, standalone, conf)

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
        hook_cmd = os.path.join(os.path.curdir, hook_cmd)
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
        json.dump(conf, outfile, indent=2, sort_keys=True)


def create_python(repo, standalone, conf):
    """
    Basic python template. Runs pylint, pep8, and unit tests on commit.
    Creates a virtualenv & autoenv file.

    """
    package = os.path.basename(os.path.abspath(repo))
    conf['env'] = {
        'path': package + '_env',
        'args': [],
    }

    # Developers should install some analysis tools
    requirements = [
        'pylint>=1.1.0',
        'pep8',
        'autopep8',
        'tox',
    ]
    if not standalone:
        requirements.append('devbox')
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

    # Tox
    render(repo, 'tox.ini', 'python/tox.ini.template',
           package=package)

    # Attempt to pull the author name and email from git config
    author = ''
    email = ''
    try:
        author = check_output(['git', 'config', 'user.name']).strip()
    except:
        pass
    try:
        email = check_output(['git', 'config', 'user.email']).strip()
    except:
        pass

    # Write some files used by python packages
    render(repo, 'README.rst', 'python/README.rst.template',
           package=package)
    render(repo, 'CHANGES.rst', 'python/CHANGES.rst.template')
    render(repo, 'setup.py', 'python/setup.py.template',
           package=package, author=author, email=email)
    render(repo, os.path.join(package, '__init__.py'),
           'python/__init__.py.template', package=package)

    # Add a script that runs autopep8 on repo
    autopep8 = copy_static('run_autopep8.sh', repo)
    st = os.stat(autopep8)
    os.chmod(autopep8, st.st_mode | stat.S_IEXEC)

    # Include the version_helper.py script
    copy_static('version_helper.py', repo, '%s_version.py' % package)
    manifest_lines = [
        'include %s_version.py' % package,
        'include CHANGES.rst',
        'include README.rst',
    ]
    append(manifest_lines, os.path.join(repo, 'MANIFEST.in'))

    # Add the autoenv file to activate the virtualenv
    render(repo, '.env', 'python/autoenv.template', venv=conf['env']['path'])

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
    parser = argparse.ArgumentParser(description="Set up a new project with "
                                     "devbox")
    parser.add_argument('repo', help="Location of the repository to box")
    parser.add_argument('-t', '--template', default='base',
                        help="Template (default %(default)s)",
                        choices=list(TEMPLATES.keys()))
    parser.add_argument('-s', '--standalone', action='store_true',
                        help="Don't require devbox to be installed for the "
                        "hooks to run")
    parser.add_argument('-l', '--list-templates', action='store_true',
                        help="List all available templates")
    parser.add_argument('-f', '--force', action='store_true',
                        help="Overwrite existing files at location")

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

    args = parser.parse_args(args)
    # TODO: Until I upload this to pypi, always use standalone mode
    args.standalone = True

    create(args.repo, args.standalone, args.force, TEMPLATES[args.template])
