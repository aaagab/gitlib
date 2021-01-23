#!/usr/bin/env python3
import inspect
import os
import re
import sys

from .git_dev.helpers import get_quiet_arg, switch_dir
from .git_dev.remote import Remote
from .git_dev.update import set_exists, set_remotes, set_first_commit

from ..gpkgs import message as msg
from ..gpkgs.getpath import getpath
from ..gpkgs import shell_helpers as shell
from ..gpkgs.prompt import prompt_boolean, prompt

# have to repair set_bump_deploy
# manage_git_repo

class GitLib():
    def __init__(self,
        direpa=None,
        prompt_success=True,
        quiet=False,
    ):
        if direpa is None:
            self.direpa=os.getcwd()
        else:
            self.direpa=getpath(direpa, "directory")

        self.direpa_root=self.direpa
        self.is_bare_repository=False

        self.direpa_git=None
        self.direpa_previous=None
        self.exists=False
        self.first_commit=None
        self.quiet=quiet
        self.prompt_success=prompt_success
        self.remotes=[]
        self.switch_caller=None

        # update git
        self.update()


    def update(self):
        set_exists(self)
        set_remotes(self)
        set_first_commit(self)

    def checkout(self, branch_name, quiet=None):
        switch_dir(self)
        if self.get_active_branch_name() != branch_name:
            shell.cmd_prompt('git checkout{} {}'.format(get_quiet_arg(self, quiet),branch_name), success=self.prompt_success)
        switch_dir(self)

    def checkoutb(self, branch_name, quiet=None):
        switch_dir(self)
        if self.get_active_branch_name() != branch_name:

            shell.cmd_prompt('git checkout{} -b {}'.format(get_quiet_arg(self, quiet),branch_name), success=self.prompt_success)
        switch_dir(self)

    def clone(self, direpa_src, direpa_dst=None, remote_name=None, quiet=None, bare=False, shared=None):
        # direpa_dst must be of form /path/project.git and must not exist
        if direpa_dst is not None:
            direpa_dst=' "{}"'.format(direpa_dst)
        else:
            direpa_dst=""

        if remote_name is not None:
            remote_name=" --origin {}".format(remote_name)
        else:
            remote_name=""

        bare_arg=""
        if bare is True:
            bare_arg=" --bare"

        cmd='git clone{}{}{} "{}"{}'.format(get_quiet_arg(self, quiet), bare_arg, remote_name, direpa_src, direpa_dst)
        switch_dir(self)
        shell.cmd_prompt(cmd, success=self.prompt_success)
        switch_dir(self)

        if shared is not None:
            filenpa_config=os.path.join(direpa_dst, "config")
            self.set_shared_repo(filenpa_config=filenpa_config, shared=shared)

    def commit(self, message, quiet=None):
        switch_dir(self)
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
                shell.cmd_prompt('git commit{} -a -m "{}"'.format(get_quiet_arg(self, quiet), message), success=self.prompt_success)
        else:
            msg.info("No Files To Commit")
        switch_dir(self)

    def commit_empty(self, txt, quiet=None):
        switch_dir(self)
        shell.cmd_prompt('git commit{} --allow-empty -m "{}"'.format(get_quiet_arg(self, quiet),txt), success=self.prompt_success)
        switch_dir(self)

    def delete_branch_local(self, branch_name):
        switch_dir(self)
        shell.cmd_prompt('git branch --delete {}'.format(branch_name), success=self.prompt_success)
        switch_dir(self)

    def delete_branch_remote(self, remote_name, branch_name):
        switch_dir(self)
        if self.is_branch_on_remote(remote_name, branch_name):
            shell.cmd_prompt('git push {} --delete {}'.format(remote_name, branch_name), success=self.prompt_success)
        else:
            msg.warning("'{}' can't be deleted because it does not exist on remote.".format(branch_name))
        switch_dir(self)

    def delete_remote(self, name):
        switch_dir(self)
        if self.has_remote(name):
            shell.cmd('git remote remove local'.format(name))
        switch_dir(self)

    def fetch_tags(self):
        switch_dir(self)
        shell.cmd_prompt('git fetch --tags', success=self.prompt_success)
        switch_dir(self)

    def fetch(self, remote="", quiet=None):
        switch_dir(self)
        if remote:
            remote=" {}".format(remote)
        shell.cmd_prompt('git fetch{}{}'.format(get_quiet_arg(self, quiet),remote), success=self.prompt_success)
        switch_dir(self)

    def get_active_branch_name(self):
        switch_dir(self)
        branch_name=shell.cmd_get_value("git rev-parse --abbrev-ref HEAD")
        switch_dir(self)
        if not branch_name:
            msg.error("No branch name from command git rev-parse --abbrev-ref HEAD at path '{}'".format(self.direpa), exit=1)
        else:
            return branch_name

    def get_all_branches(self):
        branches={}
        switch_dir(self)
        if self.is_direpa_git():
            branches["local"]=self.get_local_branches()
            branches["local_remote"]=self.get_local_remote_branches()
            branches["remote"]=self.get_remotes()
        switch_dir(self)
        return branches

    def get_branch_compare_status(self, active_branch, compare_branch):
        switch_dir(self)
        active_branch_last_commit=shell.cmd_get_value('git rev-parse {}'.format(active_branch))
        compare_branch_last_commit=shell.cmd_get_value('git rev-parse {}'.format(compare_branch))
        common_ancestor=shell.cmd_get_value('git merge-base {} {}'.format(active_branch, compare_branch))
        switch_dir(self)

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
        switch_dir(self)
        # direpa_root=shell.cmd_get_value("git rev-parse --show-toplevel")
        direpa_root=shell.cmd_get_value("git rev-parse --git-dir")
        if direpa_root == ".":
            if self.is_bare_repository is True:
                direpa_root=os.getcwd()
            else:
                direpa_root=os.path.dirname(os.getcwd())

        elif direpa_root == ".git":
            direpa_root=os.getcwd()
        switch_dir(self)
        return direpa_root

    def get_first_commit(self):
        switch_dir(self)
        # this does not work on repo without head.
        # has commit
        # git rev-parse HEAD show HEAD when no HEAD
        # git rev-list -n 1 --all  looks more reliable but not sure. actually this one give the latest commit
        commit=shell.cmd_get_value("git rev-list --all --reverse", none_on_error=True)
        if commit is not None:
            commit=commit.splitlines()[0]
        switch_dir(self)
        return commit

    def get_remote_branches(self, remote_name):
        switch_dir(self)
        # string format
        # d06a492857eea71f64c51257ec81645e50f40957        refs/heads/develop
        raw_branches=shell.cmd_get_value('git ls-remote {}'.format(remote_name)).splitlines()
        branches=[]
        # remove all unneeded string
        switch_dir(self)

        for branch in raw_branches:
            if re.match("^.*?refs/heads/.*$", branch):
                branches.append(re.sub("^.*?refs/heads/","",branch).strip())

        return branches

    def get_local_branches(self):
        switch_dir(self)
        raw_branches=shell.cmd_get_value("git branch").splitlines()
        switch_dir(self)
        branches=[]
        # remove the asterisk and strip all
        for branch in raw_branches:
            branches.append(re.sub("^\* ","",branch).strip())
        return branches

    def get_local_remote_branches(self):
        switch_dir(self)
        # string format
        # remote_name/develop
        raw_branches=shell.cmd_get_value("git branch -r")
        switch_dir(self)
        branches=[]
        # remove all unneeded string
        if raw_branches is not None:
            for branch in raw_branches.splitlines():
                if not "HEAD ->" in branch:
                    # branches.append(re.sub("^.*?"+remote_name+"/","",branch).strip())
                    branches.append(branch.strip())

        return branches

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
        switch_dir(self)
        output=shell.cmd_get_value("git rev-parse HEAD")
        switch_dir(self)
        if output == "HEAD":
            return False
        else:
            return True

    def get_remotes(self):
        switch_dir(self)
        raw_remotes=shell.cmd_get_value("git remote")
        switch_dir(self)
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
            get_quiet_arg(self, quiet),
            self.direpa_root,
        ), success=self.prompt_success)

    def get_is_bare_repository(self):
        switch_dir(self)
        is_bare=shell.cmd_get_value("git rev-parse --is-bare-repository", none_on_error=True)
        switch_dir(self)
        if is_bare is None:
            return False
        elif is_bare == "true":
            return True
        elif is_bare == "false":
            return False

    def is_branch_on_local(self, branch_name=None):
        switch_dir(self)
        if branch_name is None:
            branch_name=self.get_active_branch_name()

        has_branch_name=shell.cmd_devnull('git rev-parse --verify {}'.format(branch_name)) == 0
        switch_dir(self)
        return has_branch_name

    def is_branch_on_local_remote(self, remote_name, branch_name=None):
        switch_dir(self)
        if branch_name is None:
            branch_name=self.get_active_branch_name()

        has_branch_name=shell.cmd_devnull('git rev-parse --verify "{}/{}"'.format(remote_name, branch_name)) == 0
        switch_dir(self)
        return has_branch_name

    def is_branch_on_remote(self, remote_name, branch_name=None):
        switch_dir(self)
        if branch_name is None:
            branch_name=self.get_active_branch_name()
        result=shell.cmd_get_value('git ls-remote --heads {} {}'.format(remote_name, branch_name))
        switch_dir(self)

        if result is None:
            return False
        else:
            return True

    def is_direpa_git(self, fail_exit=False):
        git_directory_found=False
        switch_dir(self)
        git_directory_found=shell.cmd_devnull("git rev-parse --git-dir") == 0
        switch_dir(self)

        if fail_exit is True:
            if git_directory_found is False:
                msg.error("This is not a git directory '{}'".format(self.direpa), exit=1)

        return git_directory_found

    def is_empty_repository(self):
        switch_dir(self)
        num_objects=int(shell.cmd_get_value("git count-objects").split()[0])
        switch_dir(self)
        if num_objects == 0:
            return True
        else:
            return False

    def merge(self, branch_name):
        switch_dir(self)
        shell.cmd_prompt('git merge --no-edit {}'.format(branch_name), success=self.prompt_success)
        switch_dir(self)

    def merge_noff(self, branch_name):
        switch_dir(self)
        shell.cmd_prompt('git merge --no-edit --no-ff {}'.format(branch_name), success=self.prompt_success)
        switch_dir(self)

    def need_commit(self):
        switch_dir(self)
        files_to_commit=shell.cmd_get_value("git status --porcelain")
        switch_dir(self)
        if files_to_commit:
            return True
        else:
            return False

    def pull(self, remote="", quiet=None):
        switch_dir(self)
        if remote:
            remote=" {}".format(remote)
        shell.cmd_prompt('git pull{}{}'.format(get_quiet_arg(self, quiet),remote), success=self.prompt_success)
        switch_dir(self)
        
    def push(self, remote_name, branch_name=None, set_upstream=False, quiet=None):
        switch_dir(self)
        upstream=""
        if set_upstream is True:
            upstream=" -u"

        if branch_name is not None:
            branch_name=" {}".format(branch_name)
        
        shell.cmd_prompt('git push{}{} {}{}'.format(get_quiet_arg(self, quiet), upstream, remote_name, branch_name), success=self.prompt_success)
        switch_dir(self)
        
    def set_annotated_tags(self, tag, txt, remote_names=[]):
        switch_dir(self)
        shell.cmd_prompt('git tag -a {} -m "{}"'.format(tag, txt), success=self.prompt_success)
        if remote_names:
            for remote_name in remote_names:
                shell.cmd_prompt('git push {} {}'.format(remote_name, tag), success=self.prompt_success)
        switch_dir(self)
    
    def set_remote(self, name, repository_path):
        switch_dir(self)
        if self.has_remote(name):
            shell.cmd_prompt('git remote set-url {} {}'.format(name, repository_path), success=self.prompt_success)
        else:
            shell.cmd_prompt('git remote add {} {}'.format(name, repository_path), success=self.prompt_success)
        switch_dir(self)

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

    def set_upstream(self, remote_name, branch_name, filenpa_config=None):
        shell.cmd_prompt('git config --file "{}" branch.{}.remote {}'.format(self.get_filenpa_config(filenpa_config), branch_name, remote_name), success=self.prompt_success)
        shell.cmd_prompt('git config --file "{}" branch.{}.merge refs/heads/{}'.format(self.get_filenpa_config(filenpa_config), branch_name, branch_name), success=self.prompt_success)
