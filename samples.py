#!/usr/bin/env python3

if __name__ == "__main__":
    import importlib
    import os
    import sys
    direpa_script_parent=os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    module_name=os.path.basename(os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, direpa_script_parent)
    pkg = importlib.import_module(module_name)
    del sys.path[0]

    git=pkg.GitLib(
        direpa="/data/wrk/r/release/1/src"
    )
    print(git.get_active_branch_name())
    print(git.get_all_branches())
    print(git.get_direpa_root())
    print(git.get_first_commit())
