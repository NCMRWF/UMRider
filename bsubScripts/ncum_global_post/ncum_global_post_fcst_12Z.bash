#!/bin/bash
#
#BSUB -a poe                  # set parallel operating environment
#BSUB -J u2g2pos              # job name
###BSUB -J u2g2pos[24-120:24] # job name
#BSUB -W 06:00                # wall-clock time (hrs:mins)
#BSUB -n 16                   # number of tasks in job (max task in one node)
#BSUB -x                      # exclusive mode
#BSUB -R span[ptile=16]       # task per node 
#BSUB -q ultra             	  # queue
#BSUB -e /gpfs3/home/umfcst/UMRiderLogs/post/bsub/um2grb2.fcst.12hr.err.%J.hybrid     # error file name in which %J is replaced by the job ID
#BSUB -o /gpfs3/home/umfcst/UMRiderLogs/post/bsub/um2grb2.fcst.12hr.out.%J.hybrid     # output file name in which %J is replaced by the job ID

# find out the directory of this bash script after submitted to bsub
DIR="$( cd "$( dirname "${BASH_SOURCE[1]}" )" && pwd )"

# get the absolute path of the local table 
localTable_relative_dir="$DIR/../../tables/local/ncmr/v1/"
localTable_absolute_dir="$( cd "$localTable_relative_dir" && pwd )"
localTable=$localTable_absolute_dir/ncmr_grib2_local_table

# get the absolute path of the script for forecast 12utc
g2scripts_relative_dir="$DIR/../../g2scripts/"
g2scripts_absolute_dir="$( cd "$g2scripts_relative_dir" && pwd )"
g2script=$g2scripts_absolute_dir/um2grb2_fcst_12Z.py

# export the configure paths to needed variables
export UMRIDER_SETUP=$DIR/ncum_global_post_um2grb2_setup.cfg
export UMRIDER_VARS=$DIR/ncum_global_post_um2grb2_vars.cfg
export GRIB2TABLE=$localTable

echo "export UMRIDER_SETUP="$UMRIDER_SETUP
echo "export UMRIDER_VARS="$UMRIDER_VARS
echo "export GRIB2TABLE="$GRIB2TABLE

export SHELL=/bin/bash
# get the hour to pass command line argument (from based on JOB index)
hour=$(printf "%02d" ${LSB_JOBINDEX})     # 2-digit number starting with 0
hour0=$(expr $hour - 18)

# sourcing umtid_bashrc to load module python-uvcdat-iris!
source "$DIR/../umtid_bashrc"
# execute the script
#python $g2script --start_long_fcst_hour=${hour0} --end_long_fcst_hour=${hour}
python $g2script
