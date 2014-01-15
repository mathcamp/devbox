""" Setup file """
import os
import sys

from setuptools import setup, find_packages
from version_helper import git_version, UpdateVersion


HERE = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(HERE, 'README.rst')).read()
CHANGES = open(os.path.join(HERE, 'CHANGES.rst')).read()

REQUIREMENTS = []

if sys.version_info[:2] < (2, 7):
    REQUIREMENTS.append('argparse')

TEST_REQUIREMENTS = ['mock']

if __name__ == "__main__":
    setup(
        name='devbox',
        version=git_version('devbox'),
        description='Quickly set up python repos for development',
        long_description=README + '\n\n' + CHANGES,
        classifiers=[
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.2',
            'Programming Language :: Python :: 3.3',
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
        ],
        license='MIT',
        author='Steven Arcangeli',
        author_email='steven@highlig.ht',
        url='http://github.com/mathcamp/devbox',
        zip_safe=False,
        include_package_data=True,
        packages=find_packages(exclude=('tests',)),
        entry_points={
            'console_scripts': [
                'devbox-pre-commit = devbox.hook:precommit',
                'devbox-create = devbox.create:main',
                'devbox-unbox = devbox.unbox:main',
            ],
        },
        install_requires=REQUIREMENTS,
        tests_require=REQUIREMENTS + TEST_REQUIREMENTS,
        cmdclass={'update_version': UpdateVersion},
        test_suite='tests',
    )
