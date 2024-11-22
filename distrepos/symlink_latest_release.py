import typing as t
from pathlib import Path
import re

from distrepos.params import Options, Tag, ReleaseSeries

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

def create_latest_release_symlink(options: Options, release_series: t.List[ReleaseSeries]) -> t.Tuple[bool, str]:
    """
    For the given release series, find the latest-versioned `osg-release`
    rpm within that series, then symlink <series>/osg-<series>-<dver>-release-latest.rpm to it
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