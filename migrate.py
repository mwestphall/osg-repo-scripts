#!/usr/bin/env python3
"""
migrate

Migration script from mosh-based repo layout to distrepos-based repo layout.
"""

import logging
import os
import pathlib
import re
import shutil
import sys
import typing as t
from argparse import ArgumentParser
from pathlib import Path

BINARY_ARCHES = ["aarch64", "x86_64"]
CONDOR_RPM_GLOBS = [
    "condor-*.rpm",
    "htcondor-ce-*.rpm",
    "htcondor-release-*.rpm",
    "minicondor-*.rpm",
    "pelican-*.rpm",
    "python3-condor-*.rpm",
]


_log = logging.getLogger(__name__)


def move_and_link(frompath: os.PathLike, topath: os.PathLike):
    """
    Move a file and create a symlink at its original location pointing
    to its new location.
    """
    os.rename(frompath, topath)
    os.symlink(os.path.relpath(topath, os.path.dirname(frompath)), frompath)


def hardlink_or_copy_file(frompath: os.PathLike, topath: os.PathLike):
    """
    Try to hardlink a file from one path to another; if that fails,
    make a copy instead.
    """
    try:
        os.link(frompath, topath)
    except OSError:
        shutil.copy2(frompath, topath)


def get_condor_package_subdirs(repo: Path):
    """
    Get the names of the Packages/condor-* subdirectories for the given
    repo based on if it's development, release, or testing.
    If we don't know, return all three possibilities.
    """
    if repo.name == "debug" or repo.name == "SRPMS":
        parent_name = repo.resolve().parent.parent.name
    else:
        parent_name = repo.resolve().parent.name
    if parent_name in ["testing", "release"]:
        return [
            "condor-release",
            "condor-update",
        ]
    elif parent_name == "development":
        return ["condor-daily"]
    else:
        return [
            "condor-release",
            "condor-update",
            "condor-daily",
        ]


def migrate_one_repo(repo: Path, packages_dir: Path, dry_run: bool = False) -> bool:
    condor_package_subdirs = get_condor_package_subdirs(repo, packages_dir)
    all_rpms = sorted(repo.glob("*.rpm"))
    for rpm in all_rpms:
        if re.search(r"[.]osg(3[456]|devops)", rpm.name):
            _log.warning(f"Pre-OSG-23 RPM found: {rpm}.  Not migrating {repo}")
            return False
    for rpm in all_rpms:
        if rpm.is_symlink:
            _log.debug(f"Skipping symlink {rpm}")
            continue
        is_condor_rpm = any(rpm.match(gl) for gl in CONDOR_RPM_GLOBS)
        if is_condor_rpm:
            destdir = packages_dir / condor_package_subdirs[0]
        elif rpm.name[0] in "0123456789":
            destdir = packages_dir / "0"
        else:
            destdir = packages_dir / rpm.name[0].lower()
        destfile = destdir / rpm.name
        _log.info(f"Move {rpm} to {destfile}")
        if not dry_run:
            destdir.mkdir(exist_ok=True, parents=True)
            move_and_link(rpm, destfile)
        if is_condor_rpm:
            for other_subdir in condor_package_subdirs[1:]:
                other_destdir = packages_dir / other_subdir
                other_destfile = other_destdir / rpm.name
                _log.info(f"Copy {rpm} to {other_destfile}")
                if not dry_run:
                    other_destdir.mkdir(exist_ok=True, parents=True)
                    hardlink_or_copy_file(rpm, other_destfile)
    return True


def migrate_one_source(repo: Path, dry_run: bool = False):
    if repo.is_symlink():
        _log.info(f"{repo} is already a symlink; skipping")
        return
    dest = repo.resolve().parent.parent / "src"
    if dest.exists():
        _log.info(f"{dest} already exists; skipping")
        return

    if migrate_one_repo(repo, repo / "Packages", dry_run=dry_run):
        _log.info(f"Rename {repo} to {dest} and create symlink")
        if not dry_run:
            move_and_link(repo, dest)


def migrate_source(args):
    """
    Migrate SRPMs
    """
    for repo in repos(args.dirs):
        if repo.parts[-2:] == ("source", "SRPMS"):
            _log.info(f"Migrating {repo}")
            migrate_one_source(repo, args.dry_run)


def migrate_binary(args):
    """
    Migrate RPMs in arch-specific repos
    """
    for repo in repos(args.dirs):
        if repo.name not in BINARY_ARCHES:
            continue
        _log.info(f"Migrating {repo}")
        migrate_one_repo(repo, repo / "Packages", dry_run=args.dry_run)


def migrate_debug(args):
    """
    Migrate the debuginfo and debugsource RPMs.
    """
    for repo in repos(args.dirs):
        if repo.name != "debug" and repo.parent.name not in BINARY_ARCHES:
            continue
        _log.info(f"Migrating {repo}")
        migrate_one_repo(repo, repo.parent / "Packages", dry_run=args.dry_run)


def repos(dirs: t.Sequence[os.PathLike]) -> t.Iterator[Path]:
    """
    Iterate over the repos in the directory trees of `dirs`.
    """
    for dir_ in dirs:
        repodatas = Path(dir_).glob("**/repodata")
        for repodata in repodatas:
            repo = repodata.parent
            yield repo


def get_args(argv):
    """
    Parse and validate arguments
    """
    all_actions = ["source", "binary", "debug"]
    parser = ArgumentParser()
    parser.add_argument("dirs", nargs="*", help="Directories to migrate")
    parser.add_argument(
        "--source",
        action="append_const",
        dest="actions",
        const="source",
        help="Migrate source RPMs",
    )
    parser.add_argument(
        "--binary",
        action="append_const",
        dest="actions",
        const="binary",
        help="Migrate binary RPMs",
    )
    parser.add_argument(
        "--debug",
        action="append_const",
        dest="actions",
        const="debug",
        help="Migrate debuginfo and debugsource RPMs",
    )
    parser.add_argument(
        "--all",
        action="store_const",
        dest="actions",
        const=all_actions,
        help="Run all migrations (default)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Only show what would be done, do not migrate",
    )
    parser.set_defaults(actions=[], dirs=[])

    args = parser.parse_args(argv[1:])
    if not args.actions:
        args.action = all_actions
    return args


def main(argv=None):
    """
    Main function. Get arguments and run the desired actions.
    """
    args = get_args(argv or sys.argv)
    if "source" in args.actions:
        migrate_source(args)
    if "binary" in args.actions:
        migrate_binary(args)
    if "debug" in args.actions:
        migrate_debug(args)

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    sys.exit(main())
