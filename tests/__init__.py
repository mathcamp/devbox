""" Test the unboxing process """
import os

import shutil
import subprocess
from mock import patch, call, MagicMock

from devbox import unbox


try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest


# pylint: disable=E1101

class FakeFSTest(unittest.TestCase):

    """ Base test case that stubs out filesystem commands """

    def setUp(self):
        super(FakeFSTest, self).setUp()
        self.curdir = '/home/testuser'
        self.existing = set()
        patch.object(os.path, 'exists', self._exists).start()
        patch.object(os.path, 'islink').start()
        patch.object(os, 'chdir', self._chdir).start()
        patch.object(os, 'getcwd', lambda: self.curdir).start()
        patch.object(os, 'symlink').start()
        patch.object(os, 'unlink').start()
        patch.object(os, 'chmod').start()
        patch.object(os, 'stat').start()
        patch.object(shutil, 'rmtree').start()
        patch.object(subprocess, 'check_call').start()
        patch.object(subprocess, 'call').start()
        patch.object(subprocess, 'Popen').start()
        patch.object(unbox, 'urlretrieve').start()
        patch.object(unbox, 'find_executable').start()
        unbox.urlretrieve.return_value = (MagicMock(), MagicMock())
        proc = subprocess.Popen.return_value = MagicMock()
        proc.communicate.return_value = (MagicMock(), MagicMock())

    def tearDown(self):
        super(FakeFSTest, self).tearDown()
        patch.stopall()

    def _chdir(self, newdir):
        """ patch method for faking changing directory """
        if os.path.isabs(newdir):
            self.curdir = os.path.abspath(newdir)
        else:
            self.curdir = os.path.abspath(os.path.join(self.curdir, newdir))

    def _exists(self, path):
        """ patch method for checking if a file exists """
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(self.curdir, path))
        return path in self.existing

    def _add_path(self, path):
        """ Mark that a path exists """
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(self.curdir, path))
        self.existing.add(path)


class CreateVenvTest(FakeFSTest):

    """ Test the virtualenv creation process """

    def test_create_virtualenv(self):
        """ Creating a virtualenv should run the 'virtualenv' command """
        env = {
            'path': 'venv',
            'args': [],
        }
        unbox.create_virtualenv(env)
        subprocess.check_call.assert_called_with(['virtualenv', env['path']])


class UnboxTest(FakeFSTest):

    """ Test the unbox command """

    def setUp(self):
        super(UnboxTest, self).setUp()
        patch.object(unbox, 'load_conf').start()
        self.configs = {}
        unbox.load_conf.side_effect = self._getconf

    def _getconf(self, directory=None):
        """ Get the devbox config for a directory """
        if directory is None:
            directory = self.curdir
        path = os.path.abspath(os.path.join(self.curdir, directory))
        return self.configs.get(path, {})

    def _setconf(self, directory, config):
        """ Set the devbox config for a specific directory """
        path = os.path.abspath(os.path.join(self.curdir, directory))
        self.configs[path] = config

    def test_clone_repo(self):
        """ Unbox should clone the repository """
        repo = 'git@github.com:user/repository'
        unbox.main([repo])
        subprocess.check_call.assert_called_with(['git', 'clone', repo,
                                                  'repository'])

    def test_setup_git_hooks(self):
        """ Unbox should set up git hooks if present """
        repo = 'git@github.com:user/repository'
        self._add_path(os.path.join('repository', 'git_hooks'))
        os.path.islink.return_value = False
        unbox.main([repo])
        self.assertTrue(call('.git/hooks') in shutil.rmtree.call_args_list)
        self.assertTrue(call('../git_hooks', '.git/hooks') in
                        os.symlink.call_args_list)

    def test_clone_to_dest(self):
        """ Unbox should clone the repository to a specific dest """
        repo = 'git@github.com:user/repository'
        dest = 'weird_destination'
        unbox.main([repo, dest])
        subprocess.check_call.assert_called_with(['git', 'clone', repo, dest])

    def test_no_clone_if_exists(self):
        """ Unbox should not clone the repository if it already exists """
        repo = 'git@github.com:user/repository'
        self._add_path('repository')
        unbox.main([repo])
        self.assertTrue(call(['git', 'clone', repo, 'repository']) not in
                        subprocess.check_call.call_args_list)

    def test_clone_correct_dest(self):
        """ Calculate the 'dest' properly from repo urls ending with '.git' """
        repo = 'git@github.com:user/repository.git'
        unbox.main([repo])
        subprocess.check_call.assert_called_with(['git', 'clone', repo,
                                                  'repository'])

    def test_no_clone_if_dir(self):
        """ Unbox should not clone the repo if it is a directory """
        repo = 'repository'
        self._add_path(repo)
        pushd = patch.object(unbox, 'pushd').start()
        unbox.main([repo])
        self.assertTrue(call(['git', 'clone', repo, 'repository']) not in
                        subprocess.check_call.call_args_list)
        pushd.assert_called_with(repo)

    def test_run_pre_setup(self):
        """ Unboxing runs the pre_setup commands """
        repo = 'git@github.com:user/repository.git'
        self._setconf('repository', {
            'pre_setup': ['command one', 'command --two'],
        })
        unbox.main([repo])
        self.assertTrue(call(['command', 'one']) in
                        subprocess.check_call.call_args_list)
        self.assertTrue(call(['command', '--two']) in
                        subprocess.check_call.call_args_list)

    def test_run_post_setup(self):
        """ Unboxing runs the post_setup commands """
        repo = 'git@github.com:user/repository.git'
        self._setconf('repository', {
            'post_setup': ['command one', 'command --two'],
        })
        unbox.main([repo])
        self.assertTrue(call(['command', 'one']) in
                        subprocess.check_call.call_args_list)
        self.assertTrue(call(['command', '--two']) in
                        subprocess.check_call.call_args_list)

    def test_download_scripts(self):
        """ Unboxing downloads remote setup scripts to run """
        command = ['http://my.host.com/path/to/script.py', '--flag']
        commands = [command]
        unbox.run_commands(commands)
        unbox.urlretrieve.assert_called_with(command[0])
        command[0] = unbox.urlretrieve()[0]
        subprocess.check_call.assert_called_with(command)

    def test_run_post_setup_venv(self):
        """ Unboxing runs the post_setup commands with virtualenv path """
        repo = 'git@github.com:user/repository.git'
        envpath = '/virtualenv'
        self._setconf('repository', {
            'post_setup': ['command one', 'command --two'],
            'env': {
                'path': envpath,
                'args': [],
            }
        })
        unbox.main([repo])
        path = envpath + '/bin' + ':' + os.environ['PATH']
        self.assertTrue(call(['command', 'one'], env={'PATH': path}) in
                        subprocess.check_call.call_args_list)
        self.assertTrue(call(['command', '--two'], env={'PATH': path}) in
                        subprocess.check_call.call_args_list)

    def test_create_virtualenv(self):
        """ If 'env' is in conf, run create_virtualenv """
        patch.object(unbox, 'create_virtualenv').start()
        repo = 'git@github.com:user/repository.git'
        self._setconf('repository', {
            'env': {
                'path': '/virtualenv',
                'args': [],
            }
        })
        unbox.main([repo])
        self.assertTrue(unbox.create_virtualenv.called)

    def test_install_dependencies(self):
        """ Unbox all dependencies """
        repo = 'git@github.com:user/repository.git'
        nextrepo = 'git@github.com:user/nextrepo'
        self._setconf('repository', {
            'dependencies': [nextrepo],
        })
        unbox.main([repo])
        subprocess.check_call.assert_called_with(['git', 'clone', nextrepo,
                                                  'nextrepo'])

    def test_no_install_dependencies(self):
        """ Don't install dependencies if --no-deps """
        repo = 'git@github.com:user/repository.git'
        nextrepo = 'git@github.com:user/nextrepo'
        self._setconf('repository', {
            'dependencies': [nextrepo],
        })
        unbox.main([repo, '--no-deps'])
        self.assertTrue(call(['git', 'clone', nextrepo, 'nextrepo']) not in
                        subprocess.check_call.call_args_list)
