#!/bin/bash
#
#BSUB -a poe                  # set parallel operating environment
#BSUB -J ur2g2wnd             # job name
#BSUB -W 06:00                # wall-clock time (hrs:mins)
#BSUB -n 16                   # number of tasks in job (max task in one node)
#BSUB -x                      # exclusive mode
#BSUB -R span[ptile=16]       # task per node 
#BSUB -q small                # queue
#BSUB -e umreg2grb2.fcst.00hr.err.%J.hybrid     # error file name in which %J is replaced by the job ID
#BSUB -o umreg2grb2.fcst.00hr.out.%J.hybrid     # output file name in which %J is replaced by the job ID

# find out the directory of this bash script after submitted to bsub
DIR="$( cd "$( dirname "${BASH_SOURCE[1]}" )" && pwd )"

# get the absolute path of the local table 

# get the absolute path of the script for forecast 00utc
g2scripts_absolute_dir="/gpfs2/home/umfcst/ShortJobs/UMRider/UMRider-2.0.1/g2scripts/"

g2scripts_absolute_dir="/gpfs2/home/umdas/UMRider/g2scripts/"

g2script=$g2scripts_absolute_dir/um2grb2_anl_06Z.py

# export the configure paths to needed variables
export UMRIDER_SETUP=$DIR/ncum_imdaa_regional_post_prl_setup.cfg
export UMRIDER_VARS=$DIR/ncum_imdaa_regional_post_prl_vars.cfg
export GRIB2TABLE=$localTable

export GRIB2TABLE=/gpfs2/home/umtid/UMRider/tables/local/ncmr/v1/ncmr_grib2_local_table


echo "export UMRIDER_SETUP="$UMRIDER_SETUP
echo "export UMRIDER_VARS="$UMRIDER_VARS
echo "export GRIB2TABLE="$GRIB2TABLE

# sourcing umtid_bashrc to load module python-uvcdat-iris!
source "$DIR/umtid_bashrc"
# execute the script
python $g2script

