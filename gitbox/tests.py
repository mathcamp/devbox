""" Test the unboxing process """
import os

import subprocess
from mock import patch
from unittest import TestCase

from . import unbox


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
        conf = {'env': {
            'path': 'venv',
            'args': [],
        }}
        unbox.create_virtualenv(conf, 'testrepo', 'virtualenv', None, False)
        subprocess.check_call.assert_called_with(['virtualenv',
                                                  conf['env']['path']])

    def test_create_virtualenv_dependency(self):
        """ Creating dependency virtualenv should symlink to parent """
        conf = {'env': {
            'path': 'venv',
            'args': [],
        }}
        virtualenv = '../parent/venv'
        unbox.create_virtualenv(conf, 'testrepo', 'virtualenv', virtualenv,
                                True)
        os.symlink.assert_called_with(virtualenv, conf['env']['path'])

    def test_create_virtualenv_dependency_no_env(self):
        """ Dependency virtualenv should make env if parent is missing """
        # If creating virtualenv for dependency, but parent has no env, create
        # an env for the dep
        conf = {'env': {
            'path': 'venv',
            'args': [],
        }}
        unbox.create_virtualenv(conf, 'testrepo', 'virtualenv', None, True)

        subprocess.check_call.assert_called_with(['virtualenv',
                                                  conf['env']['path']])

    def test_create_virtualenv_child(self):
        """ Creating a non-dependency env with a parent should symlink """
        conf = {'parent': 'parentrepo',
                'env': {
                    'path': 'childenv',
                    'args': [],
                }}
        parent_conf = {'env': {'path': 'venv'}}
        self.existing.add('../parentrepo')
        self.existing.add('../parentrepo/venv')
        patch.object(unbox, 'load_conf', lambda _: parent_conf).start()
        unbox.create_virtualenv(conf, 'testrepo', 'virtualenv', None, False)
        os.symlink.assert_called_with(
            '../parentrepo/venv', conf['env']['path'])
