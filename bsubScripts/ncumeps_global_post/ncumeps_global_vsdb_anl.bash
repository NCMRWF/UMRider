#!/bin/bash
#
#BSUB -a poe                  # set parallel operating environment
####### BSUB -J  umeps2vsdb job name 
####### Jobname and hours will be submitted in the model executing script itself.
#BSUB -W 06:00                # wall-clock time (hrs:mins)
#BSUB -n 16                  # number of tasks in job
#BSUB -x
#BSUB -R span[ptile=16]
#BSUB -q ensemble             	  # queue
#BSUB -e /gpfs3/home/umeps/UMRiderLogs/vsdb/bsub/umeps2grb2.vsdb.err.%J.%I.hybrid     # error file name in which %J is replaced by the job ID
#BSUB -o /gpfs3/home/umeps/UMRiderLogs/vsdb/bsub/umeps2grb2.vsdb.out.%J.%I.hybrid     # output file name in which %J is replaced by the job ID


# find out the directory of this bash script after submitted to bsub
DIR="$( cd "$( dirname "${BASH_SOURCE[1]}" )" && pwd )"

# get the absolute path of the local table 
localTable_relative_dir="$DIR/../../tables/local/ncmr/v1/"
localTable_absolute_dir="$( cd "$localTable_relative_dir" && pwd )"
localTable=$localTable_absolute_dir/ncmr_grib2_local_table

export UMRIDER_STARTDATE=20160920
export GRIB2TABLE=$localTable
echo "export GRIB2TABLE="$GRIB2TABLE

epsMeanScript=$DIR/ncumeps_create_memavg_vsdb_input.py

export SHELL=/bin/bash
#export UMRIDER_STARTDATE=20170406

# set the hour to pass command line argument to create anl vsdb
hour=0
echo "hour="${hour}

# sourcing umtid_bashrc to load module python-uvcdat-iris!
source "$DIR/../umtid_bashrc"

python $epsMeanScript --start_long_fcst_hour=${hour} --end_long_fcst_hour=${hour}
