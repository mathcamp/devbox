#!/bin/bash -e

main() {
    local _autopep="autopep8 -i --ignore=E501,E24"
    if [ "$1" == "all" ]; then
        local _package=$(basename $(readlink -f .))
        find $_package -name '*.py' | xargs $_autopep
    else
        local _diff=$(git diff --name-only --diff-filter=ACMRT | grep '.py$')
        if [ "$_diff" ]; then
            echo "$_diff" | xargs $_autopep
        fi
        local _diff_cached=$(git diff --cached --name-only --diff-filter=ACMRT | grep '.py$')
        if [ "$_diff_cached" ]; then
            echo "$_diff_cached" | xargs $_autopep
        fi
    fi
}

main "$@"
