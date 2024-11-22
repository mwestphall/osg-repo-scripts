import typing as t
from pathlib import Path
from distrepos.params import Options


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
        
