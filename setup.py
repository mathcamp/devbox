""" Setup file """
import os

from setuptools import setup, find_packages
from version_helper import get_version


HERE = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(HERE, 'README.rst')).read()
CHANGES = open(os.path.join(HERE, 'CHANGES.txt')).read()

REQUIREMENTS = [
    'mock',
]

if __name__ == "__main__":
    setup(
        name='gitbox',
        version=get_version('gitbox'),
        description='Quickly set up python repos for development',
        long_description=README + '\n\n' + CHANGES,
        classifiers=[
            'Programming Language :: Python',
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',

        ],
        license='MIT',
        author='Steven Arcangeli',
        author_email='steven@highlig.ht',
        url='http://github.com/mathcamp/gitbox',
        zip_safe=False,
        include_package_data=True,
        packages=find_packages(),
        entry_points={
            'console_scripts': [
                'gitbox-pre-commit = gitbox.hook:precommit',
                'gitbox-create = gitbox:create',
                'gitbox-unbox = gitbox.unbox:main',
            ],
        },
        setup_requires=[
            'nose>=1.0',
        ],
        install_requires=REQUIREMENTS,
        tests_require=REQUIREMENTS,
    )
