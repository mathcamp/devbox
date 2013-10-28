Devbox
======
This is a tool for quickly setting up repositories for development. It was
created specifically for python projects, but has some features that should be
universally useful.

Create a Box
============
First install devbox using pip. Then run ``devbox-create path/to/repository``.
It will prompt you for some configuration options, then write out the data to
several files. Commit the files and push.

Unboxing
========
If devbox is installed, you can run ``devbox-unbox
git@github.com:user/repo.git``. If devbox is not installed, run::

    wget https://raw.github.com/mathcamp/devbox/master/devbox/unbox.py && \
    python unbox.py git@github.com:user/repo.git

The unbox command is idempotent, so you can run it multiple times with no
problems. If you have already cloned the repository you want to unbox, just
pass in the path to the repository like so::

    wget https://raw.github.com/mathcamp/devbox/master/devbox/unbox.py && \
    python unbox.py path/to/repo

Features
========
Devbox makes it easy to manage **pre-commit hooks**. It creates a directory
called ``git_hooks`` and links that to your ``.git/hooks`` directory during
setup. Additionally, it provides an easy way to run pre-commit commands on your
project or certain modified files in your project. See the ``modified`` and
``all`` fields for more detail.

Devbox allows you to run arbitrary **setup commands** when setting up a
repository for development. Useful for installing dependencies, creating
symlinks, etc.

Devbox allows you to specify **project dependencies**, which makes it easy to
bundle multiple projects together. If your project depends on several libraries
that you also frequently edit, you can set the libraries as dependencies and
easily set those up for development at the same time as the main project.

Python-specific Features
------------------------
Devbox provides a simple interface for creating and installing into a
**virtualenv** automatically during setup.

Devbox optionally includes ``version_helper.py``, a simple utility for
automatically generating package versions based on git tags.

For linking to other projects, investigate the ``parent`` and ``dependencies``
options in the conf file. Those will be respected in the virtualenv.

Format of Devbox conf
=====================
.devbox.conf is a json-encoded dictionary with several fields::

    pre_setup : list
        List of commands to run at the start of unboxing.
    dependencies : list
        List of git urls to also clone and set up when unboxing this repo (run
        after setup_commands)
    post_setup : list
        List of commands to run after any dependencies have been handled.
    hooks_modified : list
        A list of (pattern, command) pairs. The pattern is a glob that will
        match modified files. During the pre-commit hooks, each modified file
        that matches the pattern will be passed as an argument to the command.
        (ex. [["*.py", "pylint --rcfile=.pylintrc"], ["*.js", "jsl"]])
    hooks_all : list
        List of commands to run during the pre-commit hook. The advantage of
        using this instead of putting the command directly in 'pre-commit' is
        that these commands will only be run on the git index, not on unstaged
        changes.

Python-specific fields::

    env : dict
        path : str
            The path to a virtualenv. Usually relative to repository root, but
            can be absolute.
        args : list
            List of flags to pass to the virtualenv command (e.g.
            ["--system-site-packages"])
    parent : str or None
        When unboxing this repo, will look for a directory of this name at
        the same level in your directory structure. If it exists, devbox
        will make a symbolic link to that virtualenv instead of constructing
        one for this repo.
