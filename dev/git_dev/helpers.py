#!/usr/bin/env python3
import inspect
import os
import re
import sys

from ...gpkgs import message as msg

from ...gpkgs import shell_helpers as shell
from ...gpkgs.prompt import prompt_boolean, prompt

def get_quiet_arg(self, quiet):
    tmp_quiet=None
    if quiet is None:
        tmp_quiet=self.quiet
    else:
        tmp_quiet=quiet
    if tmp_quiet is True:
        return " --quiet"
    elif tmp_quiet is False:
        return ""
    else:
        msg.error("quiet value unknown '{}'".format(tmp_quiet), exit=1, trace=True)

def switch_dir(self):
    if self.switch_caller is None:
        self.switch_caller=sys._getframe(1)
        direpa_current=os.getcwd()
        if direpa_current != self.direpa_root:
            self.direpa_previous=direpa_current
            os.chdir(self.direpa_root)
    elif self.switch_caller == sys._getframe(1):
        if self.direpa_previous is not None:
            os.chdir(self.direpa_previous)
        self.direpa_previous=None
        self.switch_caller=None
    else:
        pass
    

