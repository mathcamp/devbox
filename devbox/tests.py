""" Test the unboxing process """
import os

import shutil
import subprocess
import tempfile
from mock import patch, call, ANY, MagicMock
from unittest import TestCase

from . import unbox, hook, create


# pylint: disable=E1101

class FakeFSTest(TestCase):

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
        patch.object(shutil, 'rmtree').start()
        patch.object(subprocess, 'check_call').start()
        patch.object(subprocess, 'call').start()
        patch.object(subprocess, 'Popen').start()
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
        unbox.create_virtualenv(env, 'virtualenv', None, None)
        subprocess.check_call.assert_called_with(['virtualenv', env['path']])

    def test_create_virtualenv_dependency(self):
        """ Creating dependency virtualenv should symlink to parent """
        env = {
            'path': 'venv',
            'args': [],
        }
        virtualenv = '../parent/venv'
        unbox.create_virtualenv(env, 'virtualenv', virtualenv, None)
        os.symlink.assert_called_with(virtualenv, env['path'])

    def test_create_virtualenv_child(self):
        """ Creating a non-dependency env with a parent should symlink """
        env = {
            'path': 'childenv',
            'args': [],
        }
        parent_conf = {'env': {'path': 'venv'}}
        self._add_path('../parentrepo')
        self._add_path('../parentrepo/venv')
        patch.object(unbox, 'load_conf', lambda _: parent_conf).start()
        unbox.create_virtualenv(env, 'virtualenv', None, 'parentrepo')
        os.symlink.assert_called_with('../parentrepo/venv', env['path'])

    def test_create_virtualenv_child_no_env(self):
        """ Child virtualenv should make env if parent env is missing """
        env = {
            'path': 'venv',
            'args': [],
        }
        unbox.create_virtualenv(env, 'virtualenv', None, 'nonexistent_parent')

        subprocess.check_call.assert_called_with(['virtualenv', env['path']])


class UnboxTest(FakeFSTest):

    """ Test the unbox command """

    def setUp(self):
        super(UnboxTest, self).setUp()
        patch.object(unbox, 'load_conf').start()
        self.configs = {}
        unbox.load_conf.side_effect = lambda: self.configs.get(
            self.curdir, {})

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


class HookTest(FakeFSTest):

    """ Tests for the pre-commit hook runner """

    def test_pushd(self):
        """ Pushd should temporarily chdir """
        startdir = os.getcwd()
        pushdir = 'the_next_dir'
        with hook.pushd(pushdir) as prevdir:
            self.assertEqual(prevdir, startdir)
            self.assertEqual(os.getcwd(), os.path.join(startdir, pushdir))
        self.assertEqual(os.getcwd(), startdir)

    def test_run_hooks_all(self):
        """ Hook runs all hooks_all commands """
        cmd = ['do', 'something', 'here']
        path = 'path'
        subprocess.call.return_value = 0
        retcode = hook.run_checks([cmd], [], [], path)
        self.assertEqual(retcode, 0)
        subprocess.call.assert_called_with(cmd, env={'PATH': path})

    def test_fail_when_hook_fails(self):
        """ If a hook fails, the returncode should be nonzero """
        cmd = ['do', 'something', 'here']
        subprocess.call.return_value = 1
        retcode = hook.run_checks([cmd], [], [], None)
        self.assertNotEqual(retcode, 0)

    def test_run_hooks_modified(self):
        """ Run the hooks_modified commands on matching files """
        cmd = ['do', 'something', 'here']
        filename = 'myfile'
        hook.run_checks([], [('*', cmd)], [filename], None)
        subprocess.Popen.assert_called_with(cmd + [filename], env=ANY,
                                            stdout=ANY, stderr=ANY)

    def test_no_run_hooks_modified(self):
        """ Don't run the hooks_modified commands on nonmatching files """
        cmd = ['do', 'something', 'here']
        filename = 'myfile'
        hook.run_checks([], [('*.py', cmd)], [filename], None)
        self.assertFalse(subprocess.Popen.called)

    def test_run_hooks_string_cmd(self):
        """ String commands should be split into arrays """
        cmd = "do something here"
        cmdlist = ['do', 'something', 'here']
        filename = 'myfile'
        subprocess.call.return_value = 0
        subprocess.Popen.return_value.returncode = 0
        retcode = hook.run_checks([cmd], [('*', cmd)], [filename], None)
        self.assertEqual(retcode, 0)
        subprocess.call.assert_called_with(cmdlist, env=ANY)
        subprocess.Popen.assert_called_with(cmdlist + [filename], env=ANY,
                                            stdout=ANY, stderr=ANY)


class CreateTest(TestCase):

    """ Tests for box creation """

    def setUp(self):
        super(CreateTest, self).setUp()
        self.tmp = tempfile.mktemp()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        super(CreateTest, self).tearDown()
        patch.stopall()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_list_templates(self):
        """ When listing templates, create should not be called """
        create_meth = patch.object(create, 'create').start()
        create.main(['-l'])
        self.assertFalse(create_meth.called)

    def test_default_create(self):
        """ Ensure proper default arguments from command line """
        create_meth = patch.object(create, 'create').start()
        create.main(['repo', '-s'])
        create_meth.assert_called_with('repo', True, None)

    def test_append_new(self):
        """ Appending lines to a new file adds those lines to the file """
        lines = ['first line', 'another line']
        create.append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), '\n'.join(lines) + '\n')

    def test_append_blank(self):
        """ Appending lines to a file adds those lines to the file """
        with open(self.tmp, 'w') as outfile:
            outfile.write('')
        lines = ['first line', 'another line']
        create.append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), '\n'.join(lines) + '\n')

    def test_append_no_duplicates(self):
        """ Appending lines to a file does not result in duplicate lines """
        with open(self.tmp, 'w') as outfile:
            outfile.write('first line\n')
        lines = ['first line', 'another line']
        create.append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), '\n'.join(lines) + '\n')

    def test_append_no_disturb(self):
        """ Appending lines to a file ignores existing text """
        text = 'pre-existing text\nThat will need to be ignored\n'
        with open(self.tmp, 'w') as outfile:
            outfile.write(text)
        lines = ['first line', 'another line']
        create.append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), text + '\n'.join(lines) + '\n')

    def test_append_prepend_newline(self):
        """ Appending lines to a file adds a leading newline if needed """
        text = 'pre-existing text\nThat will need to be ignored'
        with open(self.tmp, 'w') as outfile:
            outfile.write(text)
        lines = ['first line', 'another line']
        create.append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), text + '\n' + '\n'.join(lines) +
                              '\n')

    def test_base_create_works(self):
        """ Base create method should throw no exceptions """
        create.main([self.tmpdir])
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir,
                                                    create.CONF_FILE)))

    def test_python_create_works(self):
        """ Base create method should throw no exceptions """
        create.main([self.tmpdir, '-t', 'python'])
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir,
                                                    create.CONF_FILE)))
