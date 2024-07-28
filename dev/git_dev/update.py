#!/usr/bin/env python3
import inspect
import os
import re
import sys

from .helpers import switch_dir
from .remote import Remote

from ...gpkgs import shell_helpers as shell

# have to repair set_bump_deploy
# manage_git_repo
def set_exists(self):
    if os.path.exists(self.direpa):
        if self.is_direpa_git() is True:
            self.exists=True
            self.is_bare_repository=self.get_is_bare_repository()
            self.direpa_root=self.get_direpa_root()

def set_remotes(self):
    if self.exists is True:
        switch_dir(self)
        remotes=shell.cmd_get_value("git remote")
        switch_dir(self)
        if remotes:
            for name in remotes.splitlines():
                remote_name=name.strip()
                self.remotes.append(Remote(remote_name, self.get_remote(remote_name)))

def set_first_commit(self):
    if self.exists is True:
        if self.is_empty_repository() is False:
            self.first_commit=self.get_first_commit()