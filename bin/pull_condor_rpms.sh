#!/bin/bash
RSYNC_ROOT="rsync://rsync.cs.wisc.edu/htcondor"

TAG=$1
NEW_REPO_DIR=$2
CURRENT_REPO_DIR=$3
SOURCE_SET=$4

usage () {
  echo "Usage: $(basename "$0") TAG NEW_REPO_DIR CURRENT_REPO_DIR SOURCE_SET"
  echo "Where:"
  echo "  TAG is osg-SERIES-BRANCH-DVER-REPO"
  echo "  SERIES is: 23, 24, etc."
  echo "  DVER is: el8, el9, etc."
  echo "  BRANCH is: main or upcoming"
  echo "  REPO is: development, testing, or release"
  echo "  NEW_REPO_DIR is the directory to output condor RPMs into"
  echo "  CURRENT_REPO_DIR is the directory that may contain condor RPMs from the most recent successful run"
  echo "  SOURCE_SET is '' for rpms and 'SRPMS/' for srpms"
  exit 1
}

tag_not_supported() {
    echo "Tag $TAG does not have a corresponding condor version. Nothing to do."
    exit 2
}

branch_not_supported() {
    echo "Branch $1 does not have a corresponding condor branch. Nothing to do."
    exit 2
}

repo_not_supported() {
    echo "Repo $1 does not have a corresponding condor repo. Nothing to do."
    exit 2
}

[[ $# -eq 4 ]] || usage

# read series, branch, dver, and repo from the osg tag
case $TAG in
  osg-2*-*-*-* ) IFS='-' read osg SERIES BRANCH DVER REPO <<< "$TAG" ;;
  osg-*-*-* ) tag_not_supported ;;
  devops-*-*) tag_not_supported ;;
  * ) usage ;;
esac

# branch "upcoming" corresponds to SERIES.x in htcondor, "main" corresponds to SERIES.0
# others do not have a corresponding series
case $BRANCH in
    main ) 
        CONDOR_SERIES=$SERIES.0 
        TESTING_CONDOR_REPOS=(release rc);;
    upcoming ) CONDOR_SERIES=$SERIES.x
        TESTING_CONDOR_REPOS=(release rc update) ;;
    * ) branch_not_supported $BRANCH ;;
esac

# OSG repos correspond to the condor repos in the following way:
# release -> release
# testing -> release and rc (23.0 and 23.x), update (23.x only)
# development -> daily
case $REPO in
    release ) CONDOR_REPOS=(release) ;;
    testing ) CONDOR_REPOS=(${TESTING_CONDOR_REPOS[@]}) ;;
    development ) CONDOR_REPOS=(daily) ;;
    * ) repo_not_supported $REPO ;;
esac

# get every build available for that package from every applicable condor repo

mkdir -p $CURRENT_REPO_DIR

for CONDOR_REPO in ${CONDOR_REPOS[@]}; do
  RSYNC_URL="$RSYNC_ROOT/$CONDOR_SERIES/$DVER/x86_64/$CONDOR_REPO/$SOURCE_SET*.rpm"
  echo "rsyncing $RSYNC_URL to $NEW_REPO_DIR"

  rsync_tmpfile=$(mktemp rsync.XXXXXX)
  rsync --list-only "$RSYNC_URL" > "$rsync_tmpfile"
  ret=$?
  file_count=$(wc -l < "$rsync_tmpfile")
  rm $rsync_tmpfile

  if [[ $ret != 0 ]]; then
    echo "Unable to get directory listing for $RSYNC_URL: rsync failed with exit code $ret"
    exit 1
  elif [[ $file_count == 0 ]]; then
    echo "Directory listing for $RSYNC_URL returned no files"
    exit 1
  fi

  rsync --times $RSYNC_URL $NEW_REPO_DIR --link-dest $CURRENT_REPO_DIR
  ret=$?
  if [[ $ret != 0 ]]; then
    echo "Unable to retrieve htcondor packages for $RSYNC_URL: rsync failed with exit code $ret"
    exit 1
  fi
done
