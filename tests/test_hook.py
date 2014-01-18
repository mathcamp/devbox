""" Tests for hook file """
import os
import subprocess

from mock import patch, ANY

from . import FakeFSTest
from devbox import hook


# pylint: disable=E1101

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


class TestHookMain(FakeFSTest):

    """ Tests for the hook main method """

    def test_help(self):
        """ Passing in -h prints help and exits """
        with self.assertRaises(SystemExit):
            hook.main(['-h'])

    def test_no_args(self):
        """ Passing in no arguments prints help and exits """
        with self.assertRaises(SystemExit):
            hook.main([])

    @patch.object(hook, 'precommit')
    def test_precommit(self, precommit):
        """ Passing in 'all' calls precommit() """
        hook.main(['all'])
        self.assertTrue(precommit.called)
