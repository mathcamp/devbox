Devbox
======
.. image:: https://travis-ci.org/mathcamp/devbox.png?branch=master
  :target: https://travis-ci.org/mathcamp/devbox
.. image:: https://coveralls.io/repos/mathcamp/devbox/badge.png
  :target: https://coveralls.io/r/mathcamp/devbox

This is a tool for quickly setting up repositories for development. It was
created specifically for python projects, but has some features that should be
universally useful.

Create a Box
============
First install devbox using pip. Then run ``devbox-create path/to/repository``.
There are different templates which provide different base configurations for
your repo. For more information run ``devbox-create -h``.

After running the create command, your repository will have a bunch of new
files that provide some default behavior. Alter them as you desire, then add
and commit them.

Unboxing
========
If devbox is installed, you can run ``devbox-unbox
git@github.com:user/repo.git``. If devbox is not installed, run::

    wget https://raw.github.com/mathcamp/devbox/master/devbox/unbox.py && \
    python unbox.py git@github.com:user/repo.git

If you have already cloned the repository you want to unbox, just
pass in the path to the repository and devbox will complete the setup::

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

Pre-Commit in-depth
===================
There is a problem with naïve pre-commit hooks. To illustrate this, here is a trivial example.

**Expected**:
* modify files A and B, putting syntax error in B
* git add A
* git commit
* git add B
* git commit BLOCKED by pre-commit hook failure on B
* fix and git add B
* git commit
* smiles all around

**Actual**:
* modify files A and B, putting syntax error in B
* git add A
* git commit BLOCKED by pre-commit hook failure on B
* sadness

This is a simple example, but it's very easy to do this to yourself frequently.
There's a much worse variant where the hooks can pass even though you're
committing a broken build. The ``hook.py`` file is designed to fix this and
other issues.  It performs a git checkout-index into a temporary folder, copies
over any git submodules, and then runs the hooks on those temporary files. This
means that you have some guarantee that the code that's being checked is the
code that will be committed.
