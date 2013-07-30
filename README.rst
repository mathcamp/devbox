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

The unbox command is idempotent, so you can run it multiple times with not
problems. If you have already cloned the repository you want to unbox, just
pass in the path to the repository like so::

    wget https://raw.github.com/mathcamp/gitbox/master/gitbox/unbox.py && \
    python unbox.py path/to/repo

Customizing
===========
You can add additional pre-commit checks by simply putting them in the
``git_hooks/pre-commit`` file. If you want to run additional checks on a
per-modified-file basis, add the command to the gitbox.conf file. If you want
to install additional packages during the unboxing, put them into the
``requirements_dev.txt`` file.
