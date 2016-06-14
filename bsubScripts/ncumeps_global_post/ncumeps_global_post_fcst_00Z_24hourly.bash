#!/bin/bash
#
#BSUB -a poe                  # set parallel operating environment
#BSUB -J umeps2g2[24-240:24]  # job name [loop through 24 to 240 hours with intervals of 24]
#BSUB -W 06:00                # wall-clock time (hrs:mins)
#BSUB -n 16                   # number of tasks in job
#BSUB -x
#BSUB -R span[ptile=16]
#BSUB -R rusage[mem=61440]
#BSUB -q ultra             	  # queue
#BSUB -e /gpfs3/home/umfcst/UMRiderLogs/eps/bsub/um2grb2.fcst.00hr.err.%J.%I.hybrid     # error file name in which %J is replaced by the job ID
#BSUB -o /gpfs3/home/umfcst/UMRiderLogs/eps/bsub/um2grb2.fcst.00hr.out.%J.%I.hybrid     # output file name in which %J is replaced by the job ID


# find out the directory of this bash script after submitted to bsub
DIR="$( cd "$( dirname "${BASH_SOURCE[1]}" )" && pwd )"

# get the absolute path of the local table 
localTable_relative_dir="$DIR/../../tables/local/ncmr/v1/"
localTable_absolute_dir="$( cd "$localTable_relative_dir" && pwd )"
localTable=$localTable_absolute_dir/ncmr_grib2_local_table

# get the absolute path of the script for forecast 00utc
g2scripts_relative_dir="$DIR/../../g2scripts/"
g2scripts_absolute_dir="$( cd "$g2scripts_relative_dir" && pwd )"
g2script=$g2scripts_absolute_dir/umeps2grb2_fcst_00Z.py

# export the configure paths to needed variables
export UMRIDER_SETUP=$DIR/ncumeps_global_post_um2grb2_24hourly_setup.cfg
export UMRIDER_VARS=$DIR/ncumeps_global_post_um2grb2_24hourly_vars.cfg
export GRIB2TABLE=$localTable

echo "export UMRIDER_SETUP="$UMRIDER_SETUP
echo "export UMRIDER_VARS="$UMRIDER_VARS
echo "export GRIB2TABLE="$GRIB2TABLE

# sourcing umtid_bashrc to load module python-uvcdat-iris!
source "$DIR/../umtid_bashrc"
# execute the script

export SHELL=/bin/bash
# get the hour to pass command line argument (from based on JOB index)
hour=$(printf "%02d" ${LSB_JOBINDEX})     # 2-digit number starting with 0
echo "hour="${hour}
# execute the script
python $g2script --start_long_fcst_hour=${hour} --end_long_fcst_hour=${hour}

