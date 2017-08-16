#!/bin/bash
#
#BSUB -a poe                  # set parallel operating environment
#BSUB -J tig3d[1-45:1]       # job name selecting variable index %5 forces to
                              # run only 5 jobs concurrently
#BSUB -W 06:00                # wall-clock time (hrs:mins)
#BSUB -n 16                   # number of tasks in job (max task in one node)
#BSUB -x                      # exclusive mode
#BSUB -R span[ptile=16]       # task per node
#BSUB -q ensemble             	  # queue
#BSUB -e /gpfs3/home/umeps/UMRiderLogs/tigge/bsub/um2grb2.tig3d.err.%J.%I.hybrid     # error file name in which %J is replaced by the job ID
#BSUB -o /gpfs3/home/umeps/UMRiderLogs/tigge/bsub/um2grb2.tig3d.out.%J.%I.hybrid     # output file name in which %J is replaced by the job ID

# find out the directory of this bash script after submitted to bsub
DIR="$( cd "$( dirname "${BASH_SOURCE[1]}" )" && pwd )"

# get the absolute path of the local table
localTable_relative_dir="$DIR/../../tables/local/ncmr/v1/"
localTable_absolute_dir="$( cd "$localTable_relative_dir" && pwd )"
localTable=$localTable_absolute_dir/ncmr_grib2_local_table

# get the absolute path of the script for forecast 00utc
g2scripts_relative_dir="$DIR/../../g2scripts/"
g2scripts_absolute_dir="$( cd "$g2scripts_relative_dir" && pwd )"
g2script=$g2scripts_absolute_dir/tigge_umeps2grb2_fcst_00Z.py

# export the configure paths to needed variables
export UMRIDER_SETUP=$DIR/ncumeps_global_tigge_fcst_setup.cfg
export UMRIDER_VARS=$DIR/ncumeps_global_tigge_3d_vars.cfg
export GRIB2TABLE=$localTable

echo "export UMRIDER_SETUP="$UMRIDER_SETUP
echo "export UMRIDER_VARS="$UMRIDER_VARS
echo "export GRIB2TABLE="$GRIB2TABLE

# sourcing umtid_bashrc to load module python-uvcdat-iris!
source "$DIR/../umtigge_bashrc"
# get the hour to pass command line argument (from based on JOB index)
ens=$(printf "%02d" ${LSB_JOBINDEX})     # 2-digit number starting with 0
#echo "hour="${hour}
ens0=$(expr $ens - 1)
# execute the script
python $g2script --start_long_fcst_hour=0 --end_long_fcst_hour=240 --ensemble_member=$ens0
