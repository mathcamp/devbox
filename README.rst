Gitbox
======
This is a tool for quickly adding useful pre-commit hooks to a repository and
quickly setting up repositories for development.

Create a Box
============
First install gitbox using pip. Then run ``gitbox-create path/to/repository``.
It will prompt you for some configuration options, then write out the data to
several files. Commit the files and push.

Unboxing
========
If gitbox is installed, you can run ``gitbox-unbox
git@github.com:user/repo.git``. If gitbox is not installed, run::

    wget https://raw.github.com/mathcamp/gitbox/master/gitbox/unbox.py && \
    python unbox.py git@github.com:user/repo.git

This will clone the repository and set up any pre-commit hooks. If a virtualenv
is specified, it will create the virtualenv and install the package into that
env.

The unbox command is idempotent, so you can run it multiple times with no
problems. If you have already cloned the repository you want to unbox, just
pass in the path to the repository like so::

    wget https://raw.github.com/mathcamp/gitbox/master/gitbox/unbox.py && \
    python unbox.py path/to/repo

Customizing
===========
You can add additional pre-commit checks by putting them in the
``git_hooks/pre-commit`` file. If you want to run additional checks on a
per-modified-file basis, add the command to the gitbox.conf file. If you want
to install additional packages during the unboxing, put them into the
``requirements_dev.txt`` file.

Format of gitbox.conf
=====================
gitbox.conf is a json-encoded dictionary with several fields::

    env : dict
        path : str
            The path to a virtualenv. Usually relative to repository root, but
            can be absolute.
        args : list
            List of flags to pass to the virtualenv command (e.g.
            ['--system-site-packages'])
    modified : dict
        Keys are glob patterns. Values are commands (list of strings to pass to
        subprocess.Popen). During the pre-commit hook, for each modified file
        that matches the glob, all commands for that glob are run with the file
        name passed in as the last argument.
    all : list
        List of commands to run during the pre-commit hook. The advantage of
        using this instead of putting the command directly in 'pre-commit' is
        that these commands will only be run on the git index, not on unstaged
        changes.
    pre_setup : list
        List of commands to run at the start of unboxing.
    post_setup : list
        List of commands to run after all other unboxing is done.
    dependencies : list
        List of git urls to also clone and install into the virtualenv when
        unboxing this repo
    parent : str or None
        When unboxing this repo, will look for a folder of this name at the
        same level in your directory structure. If it exists, gitbox will
        install this package into that folder's virtualenv.
