""" Box creation helper script """
import importlib
import os
import inspect
import stat

import json
import shutil
from pkg_resources import resource_string, iter_entry_points

from .hook import check_output
from .unbox import CONF_FILE


class StaticResource(object):
    def __init__(self, module_name):
        self.mod, path = module_name.split('.', 1)
        self.path = path.replace('.', '/') + '/'

    def load(self, name):
        data = resource_string(self.mod, self.path + name)
        if data is not None:
            return data.decode('utf-8')

def copy_static(name, dest, destname=None):
    """ Copy one of the static files to a destination """
    destname = destname or name
    destfile = os.path.join(dest, destname)
    srcfile = os.path.join(os.path.dirname(__file__), os.pardir, name)
    shutil.copyfile(srcfile, destfile)
    return destfile


class BoxTemplate(object):
    name = None
    description = 'No description available'

    hook_dir = 'git_hooks'
    conf_file = CONF_FILE

    def __init__(self):
        self.repo = None
        self._embed = None
        self._force = None
        self.conf = {
            'dependencies': [],
            'pre_setup': [],
            'post_setup': [],
            'hooks_all': [],
            'hooks_modified': [],
        }

    @classmethod
    def walk_static_resources(cls):
        static_entry_points = iter_entry_points('devbox.' + cls.name)
        for entry_point in static_entry_points:
            yield StaticResource(entry_point.module_name)
        for superclass in cls.__bases__:
            if issubclass(superclass, BoxTemplate):
                for resource in superclass.walk_static_resources():
                    yield resource

    def options(self, parser):
        pass

    def global_options(self, parser):
        parser.add_argument('repo', help="Location of the repository to box")
        parser.add_argument('--no-embed', action='store_true',
                            help="Don't embed the hook.py file (precommit "
                            "will require devbox to be installed)")
        parser.add_argument('-f', '--force', action='store_true',
                            help="Overwrite existing files at location")

    def global_configure(self, args):
        self.repo = args.repo
        self._embed = not args.no_embed
        self._force = args.force

    def configure(self, args):
        pass

    def setup(self):
        if not os.path.exists(self.repo):
            os.makedirs(self.repo)
        elif not self._force:
            raise Exception("'%s' already exists! Pass in '-f' to overwrite "
                            "existing files" % self.repo)

    def run(self):
        raise NotImplementedError

    def finalize(self):
        # Write the conf file
        conf_file = os.path.join(self.repo, self.conf_file)
        with open(conf_file, 'w') as outfile:
            json.dump(self.conf, outfile, indent=2, sort_keys=True)

    def load(self, name):
        for resource in self.walk_static_resources():
            data = resource.load(name)
            if data is not None:
                return data
        raise ValueError("Could not find static resource '%s'" % name)

    def render(self, static_resource, **kwargs):
        data = self.load(static_resource)
        from jinja2 import Template
        template = Template(data)
        return template.render(**kwargs)

    def render_write(self, static_resource, *dest, **kwargs):
        rendered = self.render(static_resource, **kwargs)
        self.write(rendered, *dest)

    def write(self, contents, *dest):
        filename = os.path.join(*dest)
        if not os.path.isabs(filename):
            filename = os.path.join(self.repo, filename)
        directory = os.path.dirname(filename)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(filename, 'w') as outfile:
            outfile.write(contents)

    def writelines(self, lines, *dest):
        self.write('\n'.join(lines), *dest)

    def write_source(self, module, *dest):
        mod = importlib.import_module(module)
        source = inspect.getsource(mod)
        self.write(source, *dest)

    def append(self, lines, *paths):
        """ Append one or more lines to a file if they are not already present """
        filename = os.path.join(paths)
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


class SimpleTemplate(BoxTemplate):
    description = "Basic setup for any repo"

    def run(self):
        # Embed the hook.py file
        if self._embed:
            self.write_source('devbox.hook', self.hook_dir, 'hook.py')
        hookfile = os.path.join(self.hook_dir, 'hook.py')

        precommit_file = os.path.join(self.hook_dir, 'pre-commit')
        precommit_file_dest = os.path.join(self.repo, precommit_file)
        if not os.path.exists(precommit_file_dest):
            self.render_write('pre-commit.jinja2', precommit_file,
                              hookfile=hookfile)
        st = os.stat(precommit_file_dest)
        os.chmod(precommit_file_dest, st.st_mode | stat.S_IEXEC)

        if not os.path.exists(os.path.join(self.repo, '.gitignore')):
            self.render_write('gitignore.jinja2', '.gitignore',
                              embed=self._embed, hookfile=hookfile)

class PythonTemplate(SimpleTemplate):
    description = """
    Basic python template. Runs pylint, pep8, and unit tests on commit.
    Creates a virtualenv & autoenv file.

    """
    def run(self):
        package = os.path.basename(os.path.abspath(self.repo))
        venv = package + '_env'
        self.conf['env'] = {
            'path': venv,
            'args': [],
        }

        # Developers should install some analysis tools
        requirements = [
            'pylint==1.1.0',
            'pep8',
            'autopep8',
            'tox',
        ]
        if not self._embed:
            requirements.append('devbox')
        self.writelines(requirements, 'requirements_dev.txt')
        self.conf['post_setup'].append('pip install -r requirements_dev.txt')
        self.conf['post_setup'].append('pip install -e .')

        # Run pylint and pep8 on modified python files
        self.conf['hooks_modified'].extend([
            ['*.py', ['pylint', '--rcfile=.pylintrc']],
            ['*.py', ['pep8', '--config=.pep8.ini']],
        ])
        self.conf['hooks_all'].append('python setup.py test')
        copy_static('.pylintrc', self.repo)
        copy_static('.pep8.ini', self.repo)

        # Tox
        self.render_write('tox.ini.jinja2', 'tox.ini', package=package)

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
        self.render_write('README.rst.jinja2', 'README.rst', package=package)
        self.render_write('CHANGES.rst', 'CHANGES.rst')
        self.render_write('setup.py.jinja2', 'setup.py', package=package,
                          author=author, email=email)
        self.render_write('__init__.py.jinja2', package, '__init__.py',
                          package=package)

        # Add a script that runs autopep8 on repo
        autopep8 = copy_static('run_autopep8.sh', self.repo)
        st = os.stat(autopep8)
        os.chmod(autopep8, st.st_mode | stat.S_IEXEC)

        # Include the version_helper.py script
        version_helper = '%s_version.py' % package
        self.write_source('devbox.version_helper', version_helper)
        manifest = [
            'include %s' % version_helper,
            'include CHANGES.rst',
            'include README.rst',
        ]
        self.writelines(manifest, 'MANIFEST.in')

        # Add the autoenv file to activate the virtualenv
        self.render_write('autoenv.jinja2', '.env', venv=venv)

        self.render_write('gitignore.jinja2', '.gitignore', name=package)

        self.render_write('pre-commit.jinja2', self.hook_dir,
                          'pre-commit', embed=self._embed, venv=venv)
        super(PythonTemplate, self).run()


def main(args=None):
    """ Set up a new project with devbox """
    import sys
    import argparse

    if sys.version_info[0] == 3:
        print "dcreate may not work in python 3 due to dependence on jinja2"

    try:
        import jinja2
    except ImportError:
        print "dcreate requires jinja2"
        print "pip install jinja2"
        sys.exit(1)
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('-l', '--list-templates', action='store_true',
                        help="List all available templates")
    subparsers = parser.add_subparsers()

    templates = {}
    for entry_point in iter_entry_points('devbox.templates'):
        tmpl_class = entry_point.load()
        tmpl_class.name = entry_point.name
        tmpl = tmpl_class()
        subparser = subparsers.add_parser(entry_point.name)
        subparser.set_defaults(template=entry_point.name)
        tmpl.global_options(subparser)
        tmpl.options(subparser)
        templates[entry_point.name] = tmpl

    # Short-circuit --list-templates so it behaves like -h
    if '-l' in args or '--list-templates' in args:
        longest_name = max([len(name) for name in templates])
        indent = os.linesep + ' ' * (longest_name + 3)
        print("Devbox templates")
        print("================")
        for name, tmpl in sorted(templates.items()):
            doc = tmpl.description
            doc = indent.join([line.strip() for line in doc.splitlines()])
            print("%s  %s" % ((name + ':').ljust(longest_name + 1), doc))
        return

    args = parser.parse_args(args)

    # TODO: Until I upload this to pypi, always use standalone mode
    args.standalone = True

    tmpl = templates[args.template]
    tmpl.global_configure(args)
    tmpl.configure(args)
    tmpl.setup()
    tmpl.run()
    tmpl.finalize()
