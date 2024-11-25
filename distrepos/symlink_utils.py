"""
Set of utilities for setting up symlinks within the repo webserver.
"""

import typing as t
from pathlib import Path
from distrepos.params import Options, ReleaseSeries
import re


def link_static_data(options: Options, repo_name: str = "osg") -> t.Tuple[bool, str]:
    """
    Utility function to create a symlink to each top-level directory under options.static_root
    from options.dest_root
    
    Args:
        options: The global options for the run
        repo_name: The repo to link between dest_root and static_root

    Returns:
        An (ok, error message) tuple.

    TODO: "osg" repo is essentially hardcoded by the default arg here, might want to specify
          somewhere in config instead
    """
    if not options.static_root:
        # no static data specified, no op
        return True, ""

    # This code assumes options.static_root is an absolute path
    if not Path('/') in options.static_root.parents:
        return False, f"Static data path must be absolute, got {options.static_root}"

    static_src = options.static_root / repo_name
    data_dst = options.dest_root / repo_name
    
    if not static_src.exists():
        return False, f"Static data path {static_src} does not exist"

    if not data_dst.exists():
        data_dst.mkdir(parents=False)


    # clear out decayed symlinks to static_src in data_dst
    for pth in data_dst.iterdir():
        if pth.is_symlink() and static_src in pth.readlink().parents and not pth.readlink().exists():
            pth.unlink()

    # create missing symlinks to static_src in data_dist
    for pth in static_src.iterdir():
        dest = data_dst / pth.name
        # Continue if symlink is already correct
        if dest.is_symlink() and dest.readlink() == pth:
            continue

        if dest.is_symlink() and dest.readlink() != pth:
            # Reassign incorrect symlinks
            dest.unlink()
        elif dest.exists():
            # Fail if dest is not a symlink
            return False, f"Expected static data symlink {dest} is not a symlink"

        # Create the symlink
        dest.symlink_to(pth.relative_to(dest.parent))
    
    return True, ""
        

RELEASE_RPM='osg-release'
RELEASE_PATTERN = re.compile(r"-([0-9]+)\.osg")

def _get_release_number(release_rpm: Path) -> int:
    """
    Extract the integer release number from the release rpm name. Assumes all release RPMs 
    for a given series have the same semantic version and are only differentiated by integer 
    release number.
    """
    release_match = RELEASE_PATTERN.search(release_rpm.name)
    if not release_match:
        return 0
    return int(release_match[1])

def link_latest_release(options: Options, release_series: t.List[ReleaseSeries]) -> t.Tuple[bool, str]:
    """
    For the given release series, find the latest-versioned `osg-release`
    rpm within that series, then symlink <series>/osg-<series>-<dver>-release-latest.rpm to it

    Args:
        options: The global options for the run
        release_series: The list of release series (eg. [23-main, 24-main] to create release symlinks for)

    Returns:
        An (ok, error message) tuple.
    """

    for series in release_series:
        series_root = Path(options.dest_root) / series.dest
        base_arch = series.arches[0]

        for dver in series.dvers:
            # Filter release rpms in the repo down to ones in the "primary" arch 
            # with parse-able release numbers
            release_rpms = [
                rpm for rpm in (series_root / dver).rglob(f"release/{base_arch}/**/{RELEASE_RPM}*")
                if _get_release_number(rpm) > 0
            ]
            
            if not release_rpms:
                return False, f"No valid release RPMs found for series {series.name}"

            release_rpms.sort(key = _get_release_number, reverse=True)
            latest_symlink = series_root / f"osg-{series.name}-{dver}-release-latest.rpm"
            latest_symlink.symlink_to(release_rpms[0].relative_to(latest_symlink.parent))
    
    return True, ""