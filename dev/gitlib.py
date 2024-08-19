#!/usr/bin/env python3
from pprint import pprint
import inspect
import os
import re
import sys
import shlex
from typing import cast
from enum import Enum

from ..gpkgs import message as msg
from ..gpkgs.getpath import getpath
from ..gpkgs import shell_helpers as shell
from ..gpkgs.prompt import prompt


class Remote():
    def __init__(self, name, location):
        self.name=name
        self.location=location

class BranchStatus(str, Enum):
    UP_TO_DATE="up_to_date"
    PULL="pull"
    PUSH="push"
    DIVERGENT_WITH_COMMON_ANCESTOR="divergent_with_common_ancestor"
    DIVERGENT_WITHOUT_COMMON_ANCESTOR="divergent_without_common_ancestor"

class GitLib():
    def __init__(self,
        direpa:str|None=None,
        prompt_success:bool=True,
        quiet:bool=False,
    ):
        if direpa is None:
            self.direpa_root=os.getcwd()
        else:
            self.direpa_root=getpath(direpa, "directory")

        self.quiet=quiet
        self.prompt_success=prompt_success
        self.switch_root=None
        self.remotes:list[Remote]=[]
        self.first_commit=None
        self.default_remote="origin"
        self.update()

    def update(self):
        if os.path.exists(self.direpa_root) and self.is_direpa_git() is True:
            self.exists=True
            self.is_bare_repository=self.get_is_bare_repository()
            self.direpa_root=self.get_direpa_root()

            self.remotes=self.get_remotes()
            if self.is_empty_repository() is True:
                self.first_commit=None
            else:
                self.first_commit=self.get_first_commit()
        else:
            self.exists=False
            self.is_bare_repository=False

    def get_quiet_arg(self, quiet:bool|None):
        if quiet is None:
            quiet=self.quiet

        if quiet is True:
            return "--quiet"
        else:
            return None
        
    def execute(self, cmd:list, show_only:bool):
        if show_only is True:
            print(shlex.join(cmd))
        else:
            shell.cmd_prompt(cmd, success=self.prompt_success)
        
    def append_quiet_arg(self, cmd:list, quiet:bool|None=None):
        quiet_arg=self.get_quiet_arg(quiet)
        if quiet_arg is not None:
            cmd.append(quiet_arg)

    def checkout(self, branch_name:str, quiet:bool|None=None, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            if self.get_active_branch_name(show_cmds=show_only) != branch_name:
                cmd=[
                    "git",
                    "checkout",
                ]
                self.append_quiet_arg(cmd, quiet)
                self.execute(cmd, show_only=show_only)

    def checkoutb(self, branch_name:str, quiet:bool|None=None, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            if self.get_active_branch_name(show_cmds=show_only) != branch_name:
                cmd=[
                    "git",
                    "checkout",
                ]
                self.append_quiet_arg(cmd, quiet)
                cmd.extend([
                    "-b",
                    branch_name,
                ])
                self.execute(cmd, show_only=show_only)

    def clone(
        self, 
        direpa_src:str, 
        direpa_dst:str|None=None,
        remote_name:str|None=None,
        quiet:bool|None=None,
        bare:bool=False,
        shared:str|None=None,
        default_branch:str|None=None,
        show_only:bool=False,
    ):
        """
        direpa_dst must be of form /path/project.git and must not exist
        """

        cmd=[
            "git",
            "clone",
        ]
        self.append_quiet_arg(cmd, quiet)
        if bare is True:
            cmd.append("--bare")

        if remote_name is not None:
            cmd.extend([
                "--origin",
                remote_name
            ])

        cmd.append(direpa_src)

        if direpa_dst is not None:
            cmd.append(direpa_dst)

        with SwitchDir(self, show_cmds=show_only):
            self.execute(cmd, show_only=show_only)
            
        if shared is not None:
            filenpa_config=None
            if isinstance(direpa_dst, str):
                filenpa_config=os.path.join(direpa_dst, "config")
            self.set_shared_repo(filenpa_config=filenpa_config, shared=shared)

        if default_branch is not None:
            self.set_bare_repo_default_branch(branch=default_branch, direpa_repo=direpa_dst, show_only=show_only)

    def cmd(self, cmd:str|list, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            tmp_cmd=[]
            if isinstance(cmd, str):
                tmp_cmd=shlex.split(cmd)
            else:
                tmp_cmd=cmd
            self.execute(tmp_cmd, show_only=show_only)

    def commit(self, message:str|None=None, quiet:bool|None=None, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            files_to_commit=shell.cmd_get_value("git status --porcelain")
            if files_to_commit is not None:
                print("__untracked files present__")
                for f in files_to_commit.splitlines():
                    print("  {}".format(f))

                cmd=[
                    "git",
                    "add",
                    self.direpa_root,
                ]
                self.execute(cmd, show_only=show_only)

                files_to_commit=shell.cmd_get_value("git status --porcelain")
                if files_to_commit is None:
                    msg.info("No commit needed, only 'git add' was needed.")
                else:
                    if message is None:
                        message=prompt("Type Commit Message")

                    cmd=[
                        "git",
                        "commit",
                    ]
                    self.append_quiet_arg(cmd, quiet)
                    cmd.extend([
                        "-a",
                        "-m",
                        message,    
                    ])
                    self.execute(cmd, show_only=show_only)
            else:
                msg.info("No Files To Commit")

    def commit_empty(self, message:str, quiet:bool|None=None, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "commit",
            ]
            self.append_quiet_arg(cmd, quiet)
            cmd.extend([
                "--allow-empty",
                "-m",
                message,
            ])
            self.execute(cmd, show_only=show_only)

    def delete_branch_local(self, branch_name:str, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "branch",
                "--delete",
                branch_name,
            ]
            self.execute(cmd, show_only=show_only)

    def get_remote_name(self):
        remote_names=self.get_remote_names()
        if len(remote_names) == 0:
            return self.default_remote
        elif len(remote_names) == 1:
            return remote_names[0]
        else:
            msg.error(f"Please choose a remote name from {remote_names}.", trace=True)
            sys.exit(1)

    def delete_branch_remote(self, branch_name:str, remote_name:str|None=None, show_only:bool=False):
        if remote_name is None:
            remote_name=self.get_remote_name()
        with SwitchDir(self, show_cmds=show_only):
            if self.is_branch_on_remote(remote_name, branch_name):
                cmd=[
                    "git",
                    "push",
                    remote_name,
                    "--delete",
                    branch_name,    
                ]
                self.execute(cmd, show_only=show_only)
            else:
                msg.warning("'{}' can't be deleted because it does not exist on remote.".format(branch_name))

    def delete_remote(self, remote_name:str|None=None, show_only:bool=False):
        if remote_name is None:
            remote_name=self.get_remote_name()
        with SwitchDir(self, show_cmds=show_only):
            if self.has_remote(remote_name, show_cmds=show_only):
                cmd=[
                    "git",
                    "remote",
                    "remove",
                    remote_name,    
                ]
                self.execute(cmd, show_only=show_only)

    def fetch_tags(self, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "fetch",
                "--tags",
            ]
            self.execute(cmd, show_only=show_only)

    def fetch(self, remote:str|None=None, quiet:bool|None=None, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "fetch",
            ]
            self.append_quiet_arg(cmd, quiet)
            if remote is not None:
                cmd.append(remote)
            self.execute(cmd, show_only=show_only)

    def get_active_branch_name(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
            ]
            if show_cmds is True:
                print("branch_name:", shlex.join(cmd))
            branch_name=shell.cmd_get_value(cmd)
            if not branch_name:
                msg.error("No branch name from command git rev-parse --abbrev-ref HEAD at path '{}'".format(self.direpa_root), exit=1)
            else:
                return branch_name
            
    def get_all_branches(self, filenpa_config:str|None=None, show_cmds:bool=False):
        branches=dict()
        with SwitchDir(self, show_cmds=False):
            if self.is_direpa_git(show_cmds=show_cmds):
                remotes=[]
                for remote in sorted(self.get_remote_names(show_cmds=show_cmds)):
                    remotes.append(dict(
                        remote_name=remote,
                        location=self.get_remote_location(name=remote, filenpa_config=filenpa_config, show_cmds=show_cmds),
                        branches=self.get_remote_branches(remote_name=remote, show_cmds=show_cmds)
                        ))
                branches=dict(
                    local=self.get_local_branches(show_cmds=show_cmds),
                    local_remote=self.get_local_remote_branches(show_cmds=show_cmds),
                    remotes=remotes,
                )
        return branches
    
    def get_branch_compare_status(self, active_branch:str, compare_branch:str, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "rev-parse",
                active_branch,
            ]
            if show_cmds is True:
                print("active_branch_last_commit:", shlex.join(cmd))
            active_branch_last_commit=shell.cmd_get_value(cmd)

            cmd=[
                "git",
                "rev-parse",
                compare_branch,
            ]
            if show_cmds is True:
                print("compare_branch_last_commit:", shlex.join(cmd))
            compare_branch_last_commit=shell.cmd_get_value(cmd)

            cmd=[
                "git",
                "merge-base",
                active_branch,
                compare_branch,
            ]
            if show_cmds is True:
                print("common_ancestor:", shlex.join(cmd))
            common_ancestor=shell.cmd_get_value(cmd)

            if active_branch_last_commit == compare_branch_last_commit:
                return BranchStatus.UP_TO_DATE
            elif active_branch_last_commit == common_ancestor:
                return BranchStatus.PULL
            elif compare_branch_last_commit == common_ancestor:
                return BranchStatus.PUSH
            else:
                if common_ancestor:
                    return BranchStatus.DIVERGENT_WITH_COMMON_ANCESTOR
                else:
                    return BranchStatus.DIVERGENT_WITHOUT_COMMON_ANCESTOR

    def get_diren_root(self):
        return os.path.basename(self.get_direpa_root())

    def get_direpa_root(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "rev-parse",
                "--git-dir",
            ]
            if show_cmds is True:
                print(shlex.join(cmd))
            direpa_root=shell.cmd_get_value(cmd)
            if os.path.isabs(direpa_root):
                direpa_root=os.path.dirname(direpa_root)
            else:
                if direpa_root == ".":
                    if self.is_bare_repository is True:
                        direpa_root=os.getcwd()
                    else:
                        direpa_root=os.path.dirname(os.getcwd())
                elif direpa_root == ".git":
                    direpa_root=os.getcwd()
                else:
                    raise NotImplementedError()
            return direpa_root

    def get_first_commit(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            """
            this does not work on repo without head.
            has commit
            git rev-parse HEAD show HEAD when no HEAD
            git rev-list -n 1 --all  looks more reliable but not sure. actually this one give the latest commit
            """
            cmd=[
                "git",
                "rev-list",
                "--all",
                "--reverse",
            ]
            if show_cmds is True:
                print(shlex.join(cmd))
            commit=shell.cmd_get_value(cmd, none_on_error=True)
            if commit is not None:
                commit=commit.splitlines()[0]
            return commit

    def get_remote_branches(self, remote_name:str|None=None, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            """
            string format
            d06a492857eea71f64c51257ec81645e50f40957        refs/heads/develop
            """
            if remote_name is None:
                remote_name=self.get_remote_name()
            cmd=[
                "git",
                "ls-remote",
                remote_name,    
            ]
            if show_cmds is True:
                print("raw_branches:", shlex.join(cmd))
            raw_branches=shell.cmd_get_value(cmd).splitlines()
            branches=[]
            # remove all unneeded string
            for branch in raw_branches:
                if re.match("^.*?refs/heads/.*$", branch):
                    branches.append(re.sub("^.*?refs/heads/","",branch).strip())
            return branches

    def get_local_branches(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "branch",
                ]
            if show_cmds is True:
                print("raw_branches:", shlex.join(cmd))

            raw_branches=shell.cmd_get_value(cmd).splitlines()
            branches=[]
            # remove the asterisk and strip all
            for branch in raw_branches:
                branches.append(re.sub(r"^\* ","",branch).strip())
            return branches

    def get_local_remote_branches(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            # string format
            # remote_name/develop
            cmd=[
                "git",
                "branch",
                "-r",
                ]
            if show_cmds is True:
                print("raw_branches:", shlex.join(cmd))
            raw_branches=shell.cmd_get_value(cmd)
            branches=[]
            # remove all unneeded string
            if raw_branches is not None:
                for branch in raw_branches.splitlines():
                    if not "HEAD ->" in branch:
                        # branches.append(re.sub("^.*?"+remote_name+"/","",branch).strip())
                        branches.append(branch.strip())
            return branches
        
    def get_principal_branch_name(self) -> str | None:
        with SwitchDir(self, show_cmds=False):
            main_name=None
            for name in self.get_local_branches():
                if main_name is None:
                    if name == "main":
                        main_name="main"
                    elif name == "master":
                        main_name="master"
                else:
                    if name in ["main", "master"]:
                        msg.error("There are two principal branches in the repo 'main' and 'master", exit=1)
            return main_name

    def get_remote_location(self, name:str|None=None, filenpa_config:str|None=None, show_cmds:bool=False):
        if name is None:
            name=self.get_remote_name()
        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            "--get",
            f"remote.{name}.url",
            ]
        if show_cmds is True:
            print("raw_branches:", shlex.join(cmd))
        location=shell.cmd_get_value(cmd)
        return location

    def get_user_email(self, filenpa_config:str|None=None, show_cmds:bool=False):
        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            "user.email",
            ]
        if show_cmds is True:
            print("useremail:", shlex.join(cmd))
        useremail=shell.cmd_get_value(cmd)
        if not useremail:
            return None
        else:
            return useremail

    def get_user_name(self, filenpa_config:str|None=None, show_cmds:bool=False):
        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            "user.name",
            ]
        if show_cmds is True:
            print("username:", shlex.join(cmd))
        username=shell.cmd_get_value(cmd)
        if not username:
            return None
        else:
            return username

    def get_untracked_files(self, show_cmds:bool=False) -> list:
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "status",
                "--porcelain",
                ]
            if show_cmds is True:
                print("files_to_commit:", shlex.join(cmd))
            files_to_commit=shell.cmd_get_value(cmd)
            if files_to_commit is None:
                return []
            else:
                return files_to_commit.splitlines()

    def has_head(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "rev-parse",
                "HEAD",
                ]
            if show_cmds is True:
                print("output:", shlex.join(cmd))
            output=shell.cmd_get_value(cmd)
            if output == "HEAD":
                return False
            else:
                return True

    def get_remote_names(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "remote",
                ]
            if show_cmds is True:
                print("raw_remotes:", shlex.join(cmd))
            raw_remotes=shell.cmd_get_value(cmd)
            remotes=[]
            if raw_remotes is not None:
                for remote in raw_remotes.splitlines():
                    remotes.append(remote.strip())
            return remotes
        
    def get_remotes(self, filenpa_config:str|None=None, show_cmds:bool=False):
        remotes:list[Remote]=[]
        for remote_name in self.get_remote_names(show_cmds=show_cmds):
            remotes.append(Remote(
                name=remote_name, 
                location=self.get_remote_location(name=remote_name, filenpa_config=filenpa_config, show_cmds=show_cmds)
            ))
        return remotes

    def has_remote(self, name:str, show_cmds:bool=False):
        if name in self.get_remote_names(show_cmds=show_cmds):
            return True
        else:
            return False

    def init(self, quiet:bool|None=None, show_only:bool=False):
        cmd=[
            "git",
            "init",
            ]
        self.append_quiet_arg(cmd, quiet)
        cmd.append(self.direpa_root)
        self.execute(cmd, show_only=show_only)

    def get_is_bare_repository(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "rev-parse",
                "--is-bare-repository",
                ]
            if show_cmds is True:
                print("is_bare:", shlex.join(cmd))
            is_bare=shell.cmd_get_value(cmd, none_on_error=True)
            if is_bare is None:
                return False
            elif is_bare == "true":
                return True
            elif is_bare == "false":
                return False

    def is_branch_on_local(self, branch_name:str|None=None, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            if branch_name is None:
                branch_name=self.get_active_branch_name(show_cmds=show_cmds)
            cmd=[
                "git",
                "rev-parse",
                "--verify",
                branch_name,
                ]
            if show_cmds is True:
                print("has_branch_name:", shlex.join(cmd))
            has_branch_name=shell.cmd_devnull(cmd) == 0
            return has_branch_name

    def is_branch_on_local_remote(self, remote_name:str|None=None, branch_name:str|None=None, show_cmds:bool=False):
        if remote_name is None:
            remote_name=self.get_remote_name()
        with SwitchDir(self, show_cmds=show_cmds):
            if branch_name is None:
                branch_name=self.get_active_branch_name(show_cmds=show_cmds)
            cmd=[
                "git",
                "rev-parse",
                "--verify",
                f"{remote_name}/{branch_name}",
                ]
            if show_cmds is True:
                print("has_branch_name:", shlex.join(cmd))
            has_branch_name=shell.cmd_devnull(cmd) == 0
            return has_branch_name

    def is_branch_on_remote(self, remote_name:str|None=None, branch_name:str|None=None, show_cmds:bool=False):
        if remote_name is None:
            remote_name=self.default_remote
        with SwitchDir(self, show_cmds=show_cmds):
            if branch_name is None:
                branch_name=self.get_active_branch_name(show_cmds=show_cmds)

            cmd=[
                "git",
                "ls-remote",
                "--heads",
                remote_name,
                branch_name,
                ]

            if show_cmds is True:
                print("result:", shlex.join(cmd))

            result=shell.cmd_get_value(cmd)
            if result is None:
                return False
            else:
                return True

    def is_branch_uptodate(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "fetch",
                "--dry-run",
                ]
            if show_cmds is True:
                print("is_uptodate:", shlex.join(cmd))

            is_uptodate=(shell.cmd_get_value(cmd) is None)
            return is_uptodate

    def is_direpa_git(self, fail_exit:bool=False, show_cmds:bool=False):
        git_directory_found=False
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "rev-parse",
                "--git-dir",
                ]
            if show_cmds is True:
                print("git_directory_found:", shlex.join(cmd))

            git_directory_found=shell.cmd_devnull(cmd) == 0
            if fail_exit is True:
                if git_directory_found is False:
                    msg.error("This is not a git directory '{}'".format(self.direpa_root), exit=1)

            return git_directory_found

    def is_empty_repository(self, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "count-objects"
                ]
            if show_cmds is True:
                print("num_objects:", shlex.join(cmd))

            num_objects=int(shell.cmd_get_value(cmd).split()[0])
            if num_objects == 0:
                return True
            else:
                return False

    def merge(self, branch_name:str, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "merge",
                "--no-edit",
                branch_name,
            ]
            self.execute(cmd, show_only=show_only)

    def merge_noff(self, branch_name:str, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "merge",
                "--no-edit",
                "--no-ff",
                branch_name,
            ]
            self.execute(cmd, show_only=show_only)

    def need_commit(self, show_files:bool=False, show_cmds:bool=False):
        with SwitchDir(self, show_cmds=show_cmds):
            cmd=[
                "git",
                "status",
                "--porcelain",
            ]
            if show_cmds is True:
                print("files_to_commit:", shlex.join(cmd))

            files_to_commit=shell.cmd_get_value(cmd)
            if show_files is True:
                if files_to_commit is not None:
                    print("__untracked files present__")
                    for f in files_to_commit.splitlines():
                        print("  {}".format(f))
            if files_to_commit:
                return True
            else:
                return False
            
    def pull(self, remote:str|None=None, quiet:bool|None=None, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "pull",    
            ]
            self.append_quiet_arg(cmd, quiet)
            if remote is not None:
                cmd.append(remote)
            self.execute(cmd, show_only=show_only)
        
    def push(self, remote_name:str|None=None, branch_name:str|None=None, set_upstream:bool=False, quiet:bool|None=None, show_only:bool=False):
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "push",
            ]
            self.append_quiet_arg(cmd, quiet)
            if set_upstream is True:
                cmd.append("--set-upstream")

            if remote_name is None:
                cmd.append(self.get_remote_name())
            else:
                cmd.append(remote_name)

            if branch_name is None:
                if set_upstream is True:
                    cmd.append(self.get_active_branch_name(show_cmds=show_only))
            else:
                cmd.append(branch_name)

            self.execute(cmd, show_only=show_only)
        
    def set_annotated_tags(self, tag:str, message:str, remote_names:list|None=None, show_only:bool=False):
        if remote_names is None:
            remote_names=[]
        with SwitchDir(self, show_cmds=show_only):
            cmd=[
                "git",
                "tag",
                "-a",
                tag,
                "-m",
                message,
            ]
            self.execute(cmd, show_only=show_only)
            for remote_name in remote_names:
                cmd=[
                    "git",
                    "push",
                    remote_name,
                    tag,    
                ]
                self.execute(cmd, show_only=show_only)
    
    def set_remote(self, repository_path:str, name:str|None=None, show_only:bool=False):
        if name is None:
            name=self.get_remote_name()
        with SwitchDir(self, show_cmds=show_only):
            if self.has_remote(name, show_cmds=show_only):
                cmd=[
                    "git",
                    "remote",
                    "set-url",
                    name,
                    repository_path,
                    ]
                self.execute(cmd, show_only=show_only)
            else:
                cmd=[
                    "git",
                    "remote",
                    "add",
                    name,
                    repository_path,
                    ]
                self.execute(cmd, show_only=show_only)

    def set_user(self, username:str|None=None, email:str|None=None, show_only:bool=False):
        filenpa_config=self.get_filenpa_config()
        if self.get_user_name(filenpa_config=filenpa_config, show_cmds=show_only) is None:
            if username is None:
                username=prompt("git user.name")
            self.set_user_name(username, filenpa_config=filenpa_config, show_only=show_only)

        if self.get_user_email(filenpa_config=filenpa_config, show_cmds=show_only) is None:
            if email is None:
                email=prompt("git user.email")
            self.set_user_email(email, filenpa_config=filenpa_config, show_only=show_only)

    def get_filenpa_config(self, filenpa_config:str|None=None):
        if filenpa_config is None:
            if self.is_bare_repository is True:
                filenpa_config=os.path.join(self.direpa_root, "config")
            else:
                filenpa_config=os.path.join(self.direpa_root, ".git", "config")
        return filenpa_config

    def set_user_email(self, email:str, filenpa_config:str|None=None, show_only:bool=False):
        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            "user.email",
            email,
            ]
        self.execute(cmd, show_only=show_only)
        
    def set_user_name(self, name:str, filenpa_config:str|None=None, show_only:bool=False):
        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            "user.name",
            name,
            ]
        self.execute(cmd, show_only=show_only)

    def set_shared_repo(self, filenpa_config:str|None=None, shared="group", show_only:bool=False):
        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            "core.sharedRepository",
            shared,
            ]
        self.execute(cmd, show_only=show_only)

    def set_bare_repo_default_branch(self, branch, direpa_repo=None, show_only:bool=False):
        # to get default branch from local repository do "git remote show origin" and look at line that starts with HEAD
        direpa_current=None
        if direpa_repo is None:
            with SwitchDir(self, show_cmds=show_only):
                cmd=[
                    "git",
                    "symbolic-ref",
                    "HEAD",
                    f"refs/heads/{branch}",
                ]
                self.execute(cmd, show_only=show_only)
        else:
            direpa_current=os.getcwd()
            if show_only is True:
                print(f"cd {direpa_repo}")
            else:
                os.chdir(direpa_repo)
            cmd=[
                "git",
                "symbolic-ref",
                "HEAD",
                f"refs/heads/{branch}",
            ]
            self.execute(cmd, show_only=show_only)
            if show_only is True:
                print(f"cd {direpa_current}")
            else:
                os.chdir(direpa_current)

    def set_upstream(self, branch_name:str, remote_name:str|None=None, filenpa_config:str|None=None, show_only:bool=False):
        if remote_name is None:
            remote_name=self.get_remote_name()
        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            f"branch.{branch_name}.remote",
            remote_name,
            ]
        self.execute(cmd, show_only=show_only)

        cmd=[
            "git",
            "config",
            "--file",
            self.get_filenpa_config(filenpa_config),
            f"branch.{branch_name}.merge",
            f"refs/heads/{branch_name}"
            ]
        self.execute(cmd, show_only=show_only)

class SwitchDir():
    """with SwitchDir switches to git root directory and returns to previous directory.
    """
    def __init__(self, gitlib: GitLib, show_cmds:bool=False):
        self.gitlib=gitlib
        self.direpa_previous=None
        self.show_cmds=show_cmds

    def __enter__(self):
        if self.gitlib.switch_root is None:
            self.gitlib.switch_root=self
            direpa_current=os.getcwd()
            if direpa_current != self.gitlib.direpa_root:
                self.direpa_previous=direpa_current
                if self.show_cmds is True:
                    print(f"cd {self.gitlib.direpa_root}")
                os.chdir(self.gitlib.direpa_root)
            
    def __exit__(self, exc_type, exc_value, traceback):
        if self.gitlib.switch_root == self:
            self.gitlib.switch_root=None
            if self.direpa_previous is not None:
                if self.show_cmds is True:
                    print(f"cd {self.direpa_previous}")
                os.chdir(self.direpa_previous)
