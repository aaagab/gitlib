#!/usr/bin/env python3
import inspect
import os
import re
import sys

from ...gpkgs import shell_helpers as shell

class Remote():
    def __init__(self, name, location):
        self.name=name
        self.location=location

