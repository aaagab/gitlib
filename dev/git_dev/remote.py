#!/usr/bin/env python3
import inspect
import os
import re
import sys

from ...gpkgs import message as msg

from ...gpkgs import shell_helpers as shell
from ...gpkgs.prompt import prompt_boolean, prompt

class Remote():
    def __init__(self, name, location):
        self.name=name
        self.location=location

