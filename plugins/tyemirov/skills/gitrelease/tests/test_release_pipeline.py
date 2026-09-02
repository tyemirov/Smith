from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tarfile
import tempfile
import unittest


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = SKILL_ROOT / "scripts" / "release_helper.py"
PREPARE = SKILL_ROOT / "scripts" / "prepare_release.sh"
PREPARE_GO_MODULE = SKILL_ROOT / "scripts" / "prepare_go_module_artifact.sh"
DEPLOY_GO_MODULE = SKILL_ROOT / "scripts" / "deploy_go_module_artifact.sh"
PREPARE_PAGES = SKILL_ROOT / "scripts" / "prepare_pages_artifact.sh"
DEPLOY_PAGES = SKILL_ROOT / "scripts" / "deploy_pages_artifact.sh"


class ReleasePipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary_directory.name)
        self.remote = self.root / "origin.git"
        self.repo = self.root / "repo"
        self.command("git", "init", "--bare", str(self.remote), cwd=self.root)
        self.command("git", "clone", str(self.remote), str(self.repo), cwd=self.root)
        self.command("git", "config", "user.name", "Release Test", cwd=self.repo)
        self.command("git", "config", "user.email", "release-test@example.invalid", cwd=self.repo)
        (self.repo / "README.md").write_text("# Fixture\n", encoding="utf-8")
        (self.repo / "Makefile").write_text(
            "ci:\n\t@true\n\n"
            "go-module-artifact:\n"
            f"\t@{PREPARE_GO_MODULE}\n\n"
            "pages-artifact:\n"
            f"\t@{PREPARE_PAGES} --source site\n",
            encoding="utf-8",
        )
        (self.repo / "go.mod").write_text("module example.invalid/releasefixture\n\ngo 1.23\n", encoding="utf-8")
        (self.repo / "fixture.go").write_text("package releasefixture\n", encoding="utf-8")
        self.command("git", "add", "README.md", "Makefile", "go.mod", "fixture.go", cwd=self.repo)
        self.command("git", "commit", "-m", "Initial", cwd=self.repo)
        self.command("git", "branch", "-M", "master", cwd=self.repo)
        self.command("git", "push", "-u", "origin", "master", cwd=self.repo)
        self.command("git", "symbolic-ref", "HEAD", "refs/heads/master", cwd=self.remote, git_dir=True)
        self.command("git", "remote", "set-head", "origin", "-a", cwd=self.repo)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def command(
        self,
        *command: str,
        cwd: pathlib.Path,
        check: bool = True,
        git_dir: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        actual_command = list(command)
        if git_dir:
            actual_command = [actual_command[0], f"--git-dir={cwd}", *actual_command[1:]]
            cwd = self.root
        return subprocess.run(
            actual_command,
            cwd=cwd,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def test_prepare_is_local_and_finalizes_hashed_payload_inventory(self) -> None:
        env = os.environ.copy()
        env["RELEASE_HELPER"] = str(HELPER)
        self.command(str(PREPARE), "--version", "v1.0.0", cwd=self.repo, env=env)

        remote_head = self.command("git", "rev-parse", "refs/heads/master", cwd=self.remote, git_dir=True).stdout.strip()
        local_parent = self.command("git", "rev-parse", "HEAD^", cwd=self.repo).stdout.strip()
        self.assertEqual(remote_head, local_parent)
        self.assertEqual(
            self.command("git", "rev-parse", "v1.0.0^{}", cwd=self.repo).stdout.strip(),
            self.command("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip(),
        )

        artifact_dir = pathlib.Path(
            self.command("git", "rev-parse", "--git-path", "mprlab-release", cwd=self.repo).stdout.strip()
        )
        if not artifact_dir.is_absolute():
            artifact_dir = self.repo / artifact_dir
        manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["payloads"], [])
        self.command(str(HELPER), "verify-release-artifact", cwd=self.repo)

    def test_pages_release_preserves_distinct_commit_roles_and_nojekyll(self) -> None:
        site = self.repo / "site"
        site.mkdir()
        (site / "index.html").write_text("<!doctype html><title>Fixture</title>\n", encoding="utf-8")
        self.command("git", "add", "site", cwd=self.repo)
        self.command("git", "commit", "-m", "Add Pages fixture", cwd=self.repo)
        self.command("git", "push", "origin", "master", cwd=self.repo)

        env = os.environ.copy()
        env["RELEASE_HELPER"] = str(HELPER)
        env["RELEASE_ARTIFACT_TARGETS"] = "pages-artifact"
        self.command(str(PREPARE), "--version", "v1.2.0", cwd=self.repo, env=env)

        source_commit = self.command("git", "rev-parse", "HEAD^", cwd=self.repo).stdout.strip()
        release_commit = self.command("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        self.assertNotEqual(source_commit, release_commit)
        artifact_dir = pathlib.Path(
            self.command("git", "rev-parse", "--git-path", "mprlab-release", cwd=self.repo).stdout.strip()
        )
        if not artifact_dir.is_absolute():
            artifact_dir = self.repo / artifact_dir
        manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_commit"], source_commit)
        self.assertEqual(manifest["release_commit"], release_commit)

        archive = artifact_dir / "payloads" / "release-assets" / "pages.tar.gz"
        with tarfile.open(archive, "r:gz") as pages_archive:
            members = {member.name.removeprefix("./"): member for member in pages_archive.getmembers()}
            self.assertIn(".nojekyll", members)
            self.assertEqual(members[".nojekyll"].size, 0)
            marker_file = pages_archive.extractfile(members[".mprlab-release.json"])
            self.assertIsNotNone(marker_file)
            marker = json.load(marker_file)
        self.assertEqual(marker["schema_version"], 1)
        self.assertEqual(marker["release_version"], "v1.2.0")
        self.assertEqual(marker["source_commit"], source_commit)

        self.command("git", "push", "origin", "HEAD:refs/heads/master", cwd=self.repo)
        self.command("git", "push", "origin", "refs/tags/v1.2.0:refs/tags/v1.2.0", cwd=self.repo)
        fake_bin = self.root / "pages-fake-bin"
        fake_bin.mkdir()
        fake_gh = fake_bin / "gh"
        fake_gh.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "destination=''\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = '--dir' ]; then destination=\"$2\"; shift 2; else shift; fi\n"
            "done\n"
            "cp \"$FAKE_RELEASE_DIR/manifest.json\" \"$destination/manifest.json\"\n"
            "cp \"$FAKE_RELEASE_DIR/payloads/release-assets/pages.tar.gz\" \"$destination/pages.tar.gz\"\n",
            encoding="utf-8",
        )
        fake_curl = fake_bin / "curl"
        fake_curl.write_text("#!/bin/sh\nset -eu\ncat \"$FAKE_PAGES_MARKER\"\n", encoding="utf-8")
        fake_gh.chmod(0o755)
        fake_curl.chmod(0o755)
        public_marker = self.root / "public-pages-marker.json"
        public_marker.write_text(json.dumps(marker), encoding="utf-8")

        deploy_env = os.environ.copy()
        deploy_env["PATH"] = f"{fake_bin}{os.pathsep}{deploy_env['PATH']}"
        deploy_env["FAKE_RELEASE_DIR"] = str(artifact_dir)
        deploy_env["FAKE_PAGES_MARKER"] = str(public_marker)
        deploy_env["PAGES_VERIFY_ATTEMPTS"] = "1"
        deploy_env["PAGES_VERIFY_DELAY_SECONDS"] = "0"
        deployed = self.command(
            str(DEPLOY_PAGES),
            "--version",
            "v1.2.0",
            "--url",
            "https://pages.example.invalid",
            "--skip-configure",
            cwd=self.repo,
            env=deploy_env,
        )
        self.assertIn(f"Verified https://pages.example.invalid at source {source_commit}.", deployed.stdout)
        self.assertNotIn(f"at source {release_commit}.", deployed.stdout)
        deployed_marker = json.loads(
            self.command(
                "git", "show", "refs/heads/gh-pages:.mprlab-release.json", cwd=self.remote, git_dir=True
            ).stdout
        )
        self.assertEqual(deployed_marker["source_commit"], source_commit)
        self.command("git", "cat-file", "-e", "refs/heads/gh-pages:.nojekyll", cwd=self.remote, git_dir=True)

        invalid_markers = (
            {**marker, "schema_version": 2},
            {**marker, "release_version": "v9.9.9"},
            {**marker, "source_commit": release_commit},
        )
        for invalid_marker in invalid_markers:
            with self.subTest(marker=invalid_marker):
                public_marker.write_text(json.dumps(invalid_marker), encoding="utf-8")
                rejected = self.command(
                    str(DEPLOY_PAGES),
                    "--version",
                    "v1.2.0",
                    "--url",
                    "https://pages.example.invalid",
                    "--skip-configure",
                    cwd=self.repo,
                    env=deploy_env,
                    check=False,
                )
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn(f"source {source_commit}", rejected.stderr)

    def test_payload_tampering_is_rejected(self) -> None:
        source_commit = self.command("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        self.command(
            str(HELPER),
            "initialize-release-artifact",
            "--version",
            "v1.0.0",
            "--source-commit",
            source_commit,
            "--release-timestamp",
            "2026-07-09T12:00:00-07:00",
            cwd=self.repo,
        )
        artifact_dir = pathlib.Path(
            self.command("git", "rev-parse", "--git-path", "mprlab-release", cwd=self.repo).stdout.strip()
        )
        if not artifact_dir.is_absolute():
            artifact_dir = self.repo / artifact_dir
        payload = artifact_dir / "payloads" / "release-assets" / "fixture.txt"
        payload.parent.mkdir(parents=True)
        payload.write_text("prepared\n", encoding="utf-8")
        notes = self.root / "notes.md"
        notes.write_text("## [v1.0.0] - 2026-07-09\n\n- Initial\n", encoding="utf-8")
        (self.repo / "CHANGELOG.md").write_text(notes.read_text(encoding="utf-8"), encoding="utf-8")
        self.command("git", "add", "CHANGELOG.md", cwd=self.repo)
        self.command("git", "commit", "-m", "Release v1.0.0", cwd=self.repo)
        release_commit = self.command("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        self.command("git", "tag", "-a", "v1.0.0", "-m", "Release v1.0.0", cwd=self.repo)
        self.command(
            str(HELPER),
            "write-release-artifact",
            "--version",
            "v1.0.0",
            "--source-commit",
            source_commit,
            "--release-commit",
            release_commit,
            "--notes-file",
            str(notes),
            "--default-branch",
            "master",
            "--release-timestamp",
            "2026-07-09T12:00:00-07:00",
            cwd=self.repo,
        )
        payload.write_text("tampered\n", encoding="utf-8")
        result = self.command(str(HELPER), "verify-release-artifact", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload does not match", result.stdout)

    def test_go_module_release_artifact_and_proxy_deploy(self) -> None:
        env = os.environ.copy()
        env["RELEASE_HELPER"] = str(HELPER)
        env["RELEASE_ARTIFACT_TARGETS"] = "go-module-artifact"
        self.command(str(PREPARE), "--version", "v1.1.0", cwd=self.repo, env=env)

        artifact_dir = pathlib.Path(
            self.command("git", "rev-parse", "--git-path", "mprlab-release", cwd=self.repo).stdout.strip()
        )
        if not artifact_dir.is_absolute():
            artifact_dir = self.repo / artifact_dir
        descriptor = json.loads(
            (artifact_dir / "payloads" / "release-assets" / "go-module.json").read_text(encoding="utf-8")
        )
        archive = artifact_dir / "payloads" / "release-assets" / "go-module-source.tar.gz"
        self.assertEqual(descriptor["artifact_kind"], "mprlab.go-module")
        self.assertEqual(descriptor["module_path"], "example.invalid/releasefixture")
        self.assertEqual(descriptor["version"], "v1.1.0")
        self.assertEqual(descriptor["source_commit"], self.command("git", "rev-parse", "HEAD^", cwd=self.repo).stdout.strip())
        self.assertEqual(descriptor["packages"], ["example.invalid/releasefixture"])
        with tarfile.open(archive, "r:gz") as source_archive:
            self.assertIn("go-module-v1.1.0/go.mod", source_archive.getnames())
            self.assertIn("go-module-v1.1.0/fixture.go", source_archive.getnames())
        self.command(str(HELPER), "verify-release-artifact", cwd=self.repo)

        self.command("git", "push", "origin", "HEAD:refs/heads/master", cwd=self.repo)
        self.command("git", "push", "origin", "refs/tags/v1.1.0:refs/tags/v1.1.0", cwd=self.repo)
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_gh = fake_bin / "fixture-gh"
        fake_gh.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "destination=''\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = '--dir' ]; then destination=\"$2\"; shift 2; else shift; fi\n"
            "done\n"
            "cp \"$FAKE_RELEASE_DIR/manifest.json\" \"$destination/manifest.json\"\n"
            "cp \"$FAKE_RELEASE_DIR/payloads/release-assets/go-module.json\" \"$destination/go-module.json\"\n",
            encoding="utf-8",
        )
        fake_go = fake_bin / "fixture-go"
        fake_go.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import os\n"
            "import pathlib\n"
            "import sys\n"
            "pathlib.Path(os.environ['FAKE_GO_MOD_OUTPUT']).write_bytes(pathlib.Path(os.environ['FAKE_GO_MOD_SOURCE']).read_bytes())\n"
            "pathlib.Path(os.environ['FAKE_GO_LOG']).write_text(json.dumps({'args': sys.argv[1:], 'proxy': os.environ['GOPROXY']}), encoding='utf-8')\n"
            "print(json.dumps({'Path': 'example.invalid/releasefixture', 'Version': 'v1.1.0', 'GoMod': os.environ['FAKE_GO_MOD_OUTPUT'], 'Sum': 'h1:module', 'GoModSum': 'h1:gomod', 'Origin': {'VCS': 'git', 'Hash': os.environ['FAKE_RELEASE_COMMIT']}}))\n",
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)
        fake_go.chmod(0o755)

        deploy_env = os.environ.copy()
        deploy_env["PATH"] = f"{fake_bin}{os.pathsep}{deploy_env['PATH']}"
        deploy_env["GH_COMMAND"] = fake_gh.name
        deploy_env["GO_COMMAND"] = fake_go.name
        deploy_env["FAKE_RELEASE_DIR"] = str(artifact_dir)
        deploy_env["FAKE_GO_MOD_SOURCE"] = str(self.repo / "go.mod")
        deploy_env["FAKE_GO_MOD_OUTPUT"] = str(self.root / "downloaded.mod")
        deploy_env["FAKE_GO_LOG"] = str(self.root / "go-command.json")
        deploy_env["FAKE_RELEASE_COMMIT"] = self.command("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()

        dry_run = self.command(
            str(DEPLOY_GO_MODULE),
            "--version",
            "v1.1.0",
            "--proxy",
            "https://proxy.example.invalid",
            "--dry-run",
            cwd=self.repo,
            env=deploy_env,
        )
        self.assertIn("deploy_dry_run=true", dry_run.stdout)
        self.assertFalse((self.root / "go-command.json").exists())

        deployed = self.command(
            str(DEPLOY_GO_MODULE),
            "--version",
            "v1.1.0",
            "--proxy",
            "https://proxy.example.invalid",
            cwd=self.repo,
            env=deploy_env,
        )
        self.assertIn("Deployed example.invalid/releasefixture@v1.1.0", deployed.stdout)
        go_invocation = json.loads((self.root / "go-command.json").read_text(encoding="utf-8"))
        self.assertEqual(go_invocation["args"], ["mod", "download", "-json", "example.invalid/releasefixture@v1.1.0"])
        self.assertEqual(go_invocation["proxy"], "https://proxy.example.invalid")


if __name__ == "__main__":
    unittest.main()
