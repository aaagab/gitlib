#!/usr/bin/env python3
import inspect
import os
import re
import sys

from ..gpkgs import message as msg
from ..gpkgs.getpath import getpath
from ..gpkgs import shell_helpers as shell
from ..gpkgs.prompt import prompt

class Remote():
    def __init__(self, name, location):
        self.name=name
        self.location=location

class GitLib():
    def __init__(self,
        direpa=None,
        prompt_success=True,
        quiet=False,
    ):
        if direpa is None:
            self.direpa_root=os.getcwd()
        else:
            self.direpa_root=getpath(direpa, "directory")

        self.quiet=quiet
        self.prompt_success=prompt_success
        self.switch_root=None
        self.remotes=[]
        self.first_commit=None

        if os.path.exists(self.direpa_root) and self.is_direpa_git() is True:
            self.exists=True
            self.is_bare_repository=self.get_is_bare_repository()
            self.direpa_root=self.get_direpa_root()

            with SwitchDir(self):
                remotes=shell.cmd_get_value("git remote")
                if remotes:
                    for name in remotes.splitlines():
                        remote_name=name.strip()
                        self.remotes.append(Remote(remote_name, self.get_remote(remote_name)))

            if self.is_empty_repository() is False:
                self.first_commit=self.get_first_commit()
        else:
            self.exists=False
            self.is_bare_repository=False

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

    def checkout(self, branch_name, quiet=None):
        with SwitchDir(self):
            if self.get_active_branch_name() != branch_name:
                shell.cmd_prompt('git checkout{} {}'.format(self.get_quiet_arg(quiet),branch_name), success=self.prompt_success)

    def checkoutb(self, branch_name, quiet=None):
        with SwitchDir(self):
            if self.get_active_branch_name() != branch_name:
                shell.cmd_prompt('git checkout{} -b {}'.format(self.get_quiet_arg(quiet),branch_name), success=self.prompt_success)

    def clone(self, direpa_src, direpa_dst=None, remote_name=None, quiet=None, bare=False, shared=None, default_branch=None):
        # direpa_dst must be of form /path/project.git and must not exist
        if direpa_dst is not None:
            tmp_direpa_dst=' "{}"'.format(direpa_dst)
        else:
            tmp_direpa_dst=""

        if remote_name is not None:
            remote_name=" --origin {}".format(remote_name)
        else:
            remote_name=""

        bare_arg=""
        if bare is True:
            bare_arg=" --bare"

        cmd='git clone{}{}{} "{}"{}'.format(self.get_quiet_arg(quiet), bare_arg, remote_name, direpa_src, tmp_direpa_dst)
        with SwitchDir(self):
            shell.cmd_prompt(cmd, success=self.prompt_success)

        if shared is not None:
            filenpa_config=os.path.join(direpa_dst, "config")
            self.set_shared_repo(filenpa_config=filenpa_config, shared=shared)

        if default_branch is not None:
            self.set_bare_repo_default_branch(branch=default_branch, direpa_repo=direpa_dst)

    def cmd(self, cmd):
        with SwitchDir(self):
            shell.cmd_prompt("git {}".format(cmd))

    def commit(self, message:str|None=None, quiet:str|None=None):
        with SwitchDir(self):
            files_to_commit=shell.cmd_get_value("git status --porcelain")
            if files_to_commit is not None:
                print("__untracked files present__")
                for f in files_to_commit.splitlines():
                    print("  {}".format(f))
                shell.cmd_prompt("git add \"{}\"".format(self.direpa_root), success=self.prompt_success)
                files_to_commit=shell.cmd_get_value("git status --porcelain")
                if files_to_commit is None:
                    msg.info("No commit needed, 'git add' was enough.")
                else:
                    if message is None:
                        message=prompt("Type Commit Message")
                    shell.cmd_prompt('git commit{} -a -m "{}"'.format(self.get_quiet_arg(quiet), message), success=self.prompt_success)
            else:
                msg.info("No Files To Commit")

    def commit_empty(self, txt, quiet=None):
        with SwitchDir(self):
            shell.cmd_prompt('git commit{} --allow-empty -m "{}"'.format(self.get_quiet_arg(quiet),txt), success=self.prompt_success)

    def delete_branch_local(self, branch_name):
        with SwitchDir(self):
            shell.cmd_prompt('git branch --delete {}'.format(branch_name), success=self.prompt_success)

    def delete_branch_remote(self, remote_name, branch_name):
        with SwitchDir(self):
            if self.is_branch_on_remote(remote_name, branch_name):
                shell.cmd_prompt('git push {} --delete {}'.format(remote_name, branch_name), success=self.prompt_success)
            else:
                msg.warning("'{}' can't be deleted because it does not exist on remote.".format(branch_name))

    def delete_remote(self, name):
        with SwitchDir(self):
            if self.has_remote(name):
                shell.cmd(f'git remote remove {name}')

    def fetch_tags(self):
        with SwitchDir(self):
            shell.cmd_prompt('git fetch --tags', success=self.prompt_success)

    def fetch(self, remote="", quiet=None):
        with SwitchDir(self):
            if remote:
                remote=" {}".format(remote)
            shell.cmd_prompt('git fetch{}{}'.format(self.get_quiet_arg(quiet),remote), success=self.prompt_success)

    def get_active_branch_name(self):
        with SwitchDir(self):
            branch_name=shell.cmd_get_value("git rev-parse --abbrev-ref HEAD")
            if not branch_name:
                msg.error("No branch name from command git rev-parse --abbrev-ref HEAD at path '{}'".format(self.direpa_root), exit=1)
            else:
                return branch_name
            
    def get_all_branches(self):
        branches={}
        with SwitchDir(self):
            if self.is_direpa_git():
                branches["local"]=self.get_local_branches()
                branches["local_remote"]=self.get_local_remote_branches()
                branches["remote"]=self.get_remotes()
        return branches

    def get_branch_compare_status(self, active_branch, compare_branch):
        with SwitchDir(self):
            active_branch_last_commit=shell.cmd_get_value('git rev-parse {}'.format(active_branch))
            compare_branch_last_commit=shell.cmd_get_value('git rev-parse {}'.format(compare_branch))
            common_ancestor=shell.cmd_get_value('git merge-base {} {}'.format(active_branch, compare_branch))

            if active_branch_last_commit == compare_branch_last_commit:
                return "up_to_date"
            elif active_branch_last_commit == common_ancestor:
                return "pull"
            elif compare_branch_last_commit == common_ancestor:
                return "push"
            else:
                if common_ancestor:
                    return "divergent_with_common_ancestor"
                else:
                    return "divergent_without_common_ancestor"

    def get_diren_root(self):
        return os.path.basename(self.get_direpa_root())

    def get_direpa_root(self):
        with SwitchDir(self):
            direpa_root=shell.cmd_get_value("git rev-parse --git-dir")
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

    def get_first_commit(self):
        with SwitchDir(self):
            # this does not work on repo without head.
            # has commit
            # git rev-parse HEAD show HEAD when no HEAD
            # git rev-list -n 1 --all  looks more reliable but not sure. actually this one give the latest commit
            commit=shell.cmd_get_value("git rev-list --all --reverse", none_on_error=True)
            if commit is not None:
                commit=commit.splitlines()[0]
            return commit

    def get_remote_branches(self, remote_name):
        with SwitchDir(self):
            # string format
            # d06a492857eea71f64c51257ec81645e50f40957        refs/heads/develop
            raw_branches=shell.cmd_get_value('git ls-remote {}'.format(remote_name)).splitlines()
            branches=[]
            # remove all unneeded string

            for branch in raw_branches:
                if re.match("^.*?refs/heads/.*$", branch):
                    branches.append(re.sub("^.*?refs/heads/","",branch).strip())

            return branches

    def get_local_branches(self):
        with SwitchDir(self):
            raw_branches=shell.cmd_get_value("git branch").splitlines()
            branches=[]
            # remove the asterisk and strip all
            for branch in raw_branches:
                branches.append(re.sub(r"^\* ","",branch).strip())
            return branches

    def get_local_remote_branches(self):
        with SwitchDir(self):
            # string format
            # remote_name/develop
            raw_branches=shell.cmd_get_value("git branch -r")
            branches=[]
            # remove all unneeded string
            if raw_branches is not None:
                for branch in raw_branches.splitlines():
                    if not "HEAD ->" in branch:
                        # branches.append(re.sub("^.*?"+remote_name+"/","",branch).strip())
                        branches.append(branch.strip())

            return branches
        
    def get_principal_branch_name(self) -> str | None:
        with SwitchDir(self):
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

    def get_remote(self, name, filenpa_config=None):
        location=shell.cmd_get_value('git config --file "{}" --get remote.{}.url'.format(self.get_filenpa_config(filenpa_config), name))
        return location

    def get_user_email(self, filenpa_config=None):
        useremail=shell.cmd_get_value('git config --file "{}" user.email'.format(self.get_filenpa_config(filenpa_config)))
        if not useremail:
            return None
        else:
            return useremail

    def get_user_name(self, filenpa_config=None):
        username=shell.cmd_get_value('git config --file "{}" user.name'.format(self.get_filenpa_config(filenpa_config)))
        if not username:
            return None
        else:
            return username

    def has_head(self):
        with SwitchDir(self):
            output=shell.cmd_get_value("git rev-parse HEAD")
            if output == "HEAD":
                return False
            else:
                return True

    def get_remotes(self):
        with SwitchDir(self):
            raw_remotes=shell.cmd_get_value("git remote")
            remotes=[]
            if raw_remotes is not None:
                for remote in raw_remotes.splitlines():
                    remotes.append(remote.strip())
            return remotes

    def has_remote(self, name):
        if name in self.get_remotes():
            return True
        else:
            return False

    def init(self, quiet=None):
        shell.cmd_prompt("git init{} \"{}\"".format(
            self.get_quiet_arg(quiet),
            self.direpa_root,
        ), success=self.prompt_success)

    def get_is_bare_repository(self):
        with SwitchDir(self):
            is_bare=shell.cmd_get_value("git rev-parse --is-bare-repository", none_on_error=True)
            if is_bare is None:
                return False
            elif is_bare == "true":
                return True
            elif is_bare == "false":
                return False

    def is_branch_on_local(self, branch_name=None):
        with SwitchDir(self):
            if branch_name is None:
                branch_name=self.get_active_branch_name()

            has_branch_name=shell.cmd_devnull('git rev-parse --verify {}'.format(branch_name)) == 0
            return has_branch_name

    def is_branch_on_local_remote(self, remote_name, branch_name=None):
        with SwitchDir(self):
            if branch_name is None:
                branch_name=self.get_active_branch_name()

            has_branch_name=shell.cmd_devnull('git rev-parse --verify "{}/{}"'.format(remote_name, branch_name)) == 0
            return has_branch_name

    def is_branch_on_remote(self, remote_name, branch_name=None):
        with SwitchDir(self):
            if branch_name is None:
                branch_name=self.get_active_branch_name()
            result=shell.cmd_get_value('git ls-remote --heads {} {}'.format(remote_name, branch_name))
            if result is None:
                return False
            else:
                return True

    def is_branch_uptodate(self):
        with SwitchDir(self):
            is_uptodate=(shell.cmd_get_value("git fetch --dry-run") is None)
            return is_uptodate

    def is_direpa_git(self, fail_exit=False):
        git_directory_found=False
        with SwitchDir(self):
            git_directory_found=shell.cmd_devnull("git rev-parse --git-dir") == 0
            if fail_exit is True:
                if git_directory_found is False:
                    msg.error("This is not a git directory '{}'".format(self.direpa_root), exit=1)

            return git_directory_found

    def is_empty_repository(self):
        with SwitchDir(self):
            num_objects=int(shell.cmd_get_value("git count-objects").split()[0])
            if num_objects == 0:
                return True
            else:
                return False

    def merge(self, branch_name):
        with SwitchDir(self):
            shell.cmd_prompt('git merge --no-edit {}'.format(branch_name), success=self.prompt_success)

    def merge_noff(self, branch_name):
        with SwitchDir(self):
            shell.cmd_prompt('git merge --no-edit --no-ff {}'.format(branch_name), success=self.prompt_success)

    def need_commit(self):
        with SwitchDir(self):
            files_to_commit=shell.cmd_get_value("git status --porcelain")
            if files_to_commit:
                return True
            else:
                return False

    def pull(self, remote="", quiet=None):
        with SwitchDir(self):
            if remote:
                remote=" {}".format(remote)
            shell.cmd_prompt('git pull{}{}'.format(self.get_quiet_arg(quiet),remote), success=self.prompt_success)
        
    def push(self, remote_name=None, branch_name=None, set_upstream=False, quiet=None):
        with SwitchDir(self):
            upstream=""
            if set_upstream is True:
                upstream=" -u"

            if remote_name is None:
                remote_name="origin"
            else:
                remote_name=" {}".format(remote_name)

            if branch_name is None:
                branch_name=""
            else:
                branch_name=" {}".format(branch_name)
            
            shell.cmd_prompt('git push{}{}{}{}'.format(self.get_quiet_arg(quiet), upstream, remote_name, branch_name), success=self.prompt_success)
        
    def set_annotated_tags(self, tag, txt, remote_names=[]):
        with SwitchDir(self):
            shell.cmd_prompt('git tag -a {} -m "{}"'.format(tag, txt), success=self.prompt_success)
            if remote_names:
                for remote_name in remote_names:
                    shell.cmd_prompt('git push {} {}'.format(remote_name, tag), success=self.prompt_success)
    
    def set_remote(self, name, repository_path):
        with SwitchDir(self):
            if self.has_remote(name):
                shell.cmd_prompt('git remote set-url {} {}'.format(name, repository_path), success=self.prompt_success)
            else:
                shell.cmd_prompt('git remote add {} {}'.format(name, repository_path), success=self.prompt_success)

    def set_user(self, username=None, email=None):
        filenpa_config=self.get_filenpa_config()
        if self.get_user_name(filenpa_config=filenpa_config) is None:
            if username is None:
                username=prompt("git user.name")
            self.set_user_name(username, filenpa_config=filenpa_config)

        if self.get_user_email(filenpa_config=filenpa_config) is None:
            if email is None:
                email=prompt("git user.email")
            self.set_user_email(email, filenpa_config=filenpa_config)

    def get_filenpa_config(self, filenpa_config=None):
        if filenpa_config is None:
            if self.is_bare_repository is True:
                filenpa_config=os.path.join(self.direpa_root, "config")
            else:
                filenpa_config=os.path.join(self.direpa_root, ".git", "config")
        return filenpa_config

    def set_user_email(self, email, filenpa_config=None):
        shell.cmd_prompt('git config --file "{}" user.email "{}"'.format(self.get_filenpa_config(filenpa_config), email), success=self.prompt_success)
        
    def set_user_name(self, name, filenpa_config=None):
        shell.cmd_prompt('git config --file "{}" user.name "{}"'.format(self.get_filenpa_config(filenpa_config), name), success=self.prompt_success)

    def set_shared_repo(self, filenpa_config=None, shared="group"):
        shell.cmd_prompt('git config --file "{}" core.sharedRepository "{}"'.format(self.get_filenpa_config(filenpa_config), shared), success=self.prompt_success)

    def set_bare_repo_default_branch(self, branch, direpa_repo=None):
        # to get default branch from local repository do "git remote show origin" and look at line that starts with HEAD
        direpa_current=None
        if direpa_repo is None:
            with SwitchDir(self):
                shell.cmd_prompt("git symbolic-ref HEAD refs/heads/{}".format(branch))
        else:
            direpa_current=os.getcwd()
            os.chdir(direpa_repo)
            shell.cmd_prompt("git symbolic-ref HEAD refs/heads/{}".format(branch))
            os.chdir(direpa_current)

    def set_upstream(self, remote_name, branch_name, filenpa_config=None):
        shell.cmd_prompt('git config --file "{}" branch.{}.remote {}'.format(self.get_filenpa_config(filenpa_config), branch_name, remote_name), success=self.prompt_success)
        shell.cmd_prompt('git config --file "{}" branch.{}.merge refs/heads/{}'.format(self.get_filenpa_config(filenpa_config), branch_name, branch_name), success=self.prompt_success)

class SwitchDir():
    def __init__(self, gitlib: GitLib):
        self.gitlib=gitlib
        self.direpa_previous=None

    def __enter__(self):
        if self.gitlib.switch_root is None:
            self.gitlib.switch_root=self
            direpa_current=os.getcwd()
            if direpa_current != self.gitlib.direpa_root:
                self.direpa_previous=direpa_current
                os.chdir(self.gitlib.direpa_root)
            
    def __exit__(self, exc_type, exc_value, traceback):
        if self.gitlib.switch_root == self:
            self.gitlib.switch_root=None
            if self.direpa_previous is not None:
                os.chdir(self.direpa_previous)
