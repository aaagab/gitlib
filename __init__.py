#!/usr/bin/env python3
# authors: Gabriel Auger
# name: gitlib
# licenses: MIT 

__version__= "4.0.1"

# from .dev.bump_version import bump_version
# from .gpkgs import message as msg
from .gpkgs import shell_helpers as _shell
from .dev.gitlib import GitLib, SwitchDir, BranchStatus, Remote

