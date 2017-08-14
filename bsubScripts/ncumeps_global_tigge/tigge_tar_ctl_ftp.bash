#!/bin/bash
#
#BSUB -a poe                  # set parallel operating environment
#BSUB -J eps2tiggeoth # job name
#BSUB -J tiggectl
#BSUB -W 06:00                # wall-clock time (hrs:mins)
#BSUB -n 16                   # number of tasks in job (max task in one node)
#BSUB -x                      # exclusive mode
#BSUB -R span[ptile=16]       # task per node 
#BSUB -q ensemble             	  # queue
#BSUB -e /gpfs3/home/umeps/UMRiderLogs/tigge/bsub/um2grb2.fcst.00hr.err.%J.hybrid     # error file name in which %J is replaced by the job ID
#BSUB -o /gpfs3/home/umeps/UMRiderLogs/tigge/bsub/um2grb2.fcst.00hr.out.%J.hybrid     # output file name in which %J is replaced by the job ID

# find out the directory of this bash script after submitted to bsub
DIR="$( cd "$( dirname "${BASH_SOURCE[1]}" )" && pwd )"


# get the absolute path of the script for forecast 00utc
g2scripts_relative_dir="$DIR/"
g2scripts_absolute_dir="$( cd "$g2scripts_relative_dir" && pwd )"
#g2script=$g2scripts_absolute_dir/tigge_create_tarball_g2files_put_into_ftp-arulalan.py
g2script=$g2scripts_absolute_dir/tigge_create_tarball_g2files.py

#export UMRIDER_STARTDATE=20170406

# sourcing umtid_bashrc to load module python-uvcdat-iris!
#source "$DIR/../umtid_bashrc"
# get the hour to pass command line argument (from based on JOB index)
#echo "hour="${hour}
# execute the script
/gpfs2/home/arulalan/miniconda2/envs/iris-1.10.dev1/bin/python $g2script --date $UMRIDER_STARTDATE --member 0
