#!/bin/bash -e
find gitbox -name '*.py' | xargs autopep8 -i --ignore=E501,E24