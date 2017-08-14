#!/bin/bash

export UMRIDER_STARTDATE=20170404


NEPSJOBID=`bsub < tigge_tar_1to44mem_ftp.bash |tail -1| cut -d" " -f2 | tr -d "<" | tr -d ">"`

bsub -w "done($NEPSJOBID)" < tigge_tar_ctl_ftp.bash

