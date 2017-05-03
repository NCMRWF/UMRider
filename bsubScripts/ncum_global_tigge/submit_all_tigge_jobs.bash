#!/bin/bash

source /gpfs2/home/arulalan/.bashrc

export UMRIDER_STARTDATE=$(date +'%Y%m%d')

#export UMRIDER_STARTDATE=20170402


# submit cummulative vars grib2 conversion
NEPSCUMJOBID=`bsub < ncumeps_global_cummulative_fcst_00Z.bash |tail -1| cut -d" " -f2 | tr -d "<" | tr -d ">"`

# submit instataneous vars grib2 conversion
NEPSOTHJOBID=`bsub < ncumeps_global_othervars_fcst_00Z.bash |tail -1| cut -d" " -f2 | tr -d "<" | tr -d ">"`

# submit 1-44 member tarball after completed the above 2 jobs
NEPSTARJOBID=`bsub -w "done($NEPSCUMJOBID) && done($NEPSOTHJOBID)"   < tigge_tar_1to44mem_ftp.bash |tail -1| cut -d" " -f2 | tr -d "<" | tr -d ">"`

# sumit 0th control member tarball and push (0 to 44 member tarballs by rsync) into ftp after completed the above job.
bsub -w "done($NEPSTARJOBID)"  < tigge_tar_ctl_ftp.bash

