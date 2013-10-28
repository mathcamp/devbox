""" Test the unboxing process """
import os

import subprocess
import tempfile
from mock import patch
from unittest import TestCase

from . import unbox, append


# pylint: disable=E1101

class UnboxTest(TestCase):

    """ Test the unboxing process """

    def setUp(self):
        super(UnboxTest, self).setUp()
        self.curdir = '/home'
        self.existing = set()
        patch.object(os.path, 'exists', self._exists).start()
        patch.object(os, 'chdir', self._chdir).start()
        patch.object(os, 'symlink').start()
        patch.object(subprocess, 'check_call').start()

    def tearDown(self):
        super(UnboxTest, self).tearDown()
        patch.stopall()

    def _chdir(self, newdir):
        """ patch method for faking changing directory """
        if os.path.isabs(newdir):
            self.curdir = os.path.abspath(newdir)
        else:
            self.curdir = os.path.abspath(os.path.join(self.curdir, newdir))

    def _exists(self, path):
        """ patch method for checking if a file exists """
        return path in self.existing

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
        self.existing.add('../parentrepo')
        self.existing.add('../parentrepo/venv')
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


class UtilTest(TestCase):

    """ Test utility functions """

    def setUp(self):
        super(UtilTest, self).setUp()
        self.tmp = tempfile.mktemp()

    def tearDown(self):
        super(UtilTest, self).tearDown()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_append_new(self):
        """ Appending lines to a new file adds those lines to the file """
        lines = ['first line', 'another line']
        append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), '\n'.join(lines) + '\n')

    def test_append_blank(self):
        """ Appending lines to a file adds those lines to the file """
        with open(self.tmp, 'w') as outfile:
            outfile.write('')
        lines = ['first line', 'another line']
        append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), '\n'.join(lines) + '\n')

    def test_append_no_duplicates(self):
        """ Appending lines to a file does not result in duplicate lines """
        with open(self.tmp, 'w') as outfile:
            outfile.write('first line\n')
        lines = ['first line', 'another line']
        append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), '\n'.join(lines) + '\n')

    def test_append_no_disturb(self):
        """ Appending lines to a file ignores existing text """
        text = 'pre-existing text\nThat will need to be ignored\n'
        with open(self.tmp, 'w') as outfile:
            outfile.write(text)
        lines = ['first line', 'another line']
        append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), text + '\n'.join(lines) + '\n')

    def test_append_prepend_newline(self):
        """ Appending lines to a file adds a leading newline if needed """
        text = 'pre-existing text\nThat will need to be ignored'
        with open(self.tmp, 'w') as outfile:
            outfile.write(text)
        lines = ['first line', 'another line']
        append(lines, self.tmp)
        with open(self.tmp, 'r') as infile:
            self.assertEquals(infile.read(), text + '\n' + '\n'.join(lines) +
                              '\n')
