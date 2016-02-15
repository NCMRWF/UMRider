#!/bin/bash
#
#BSUB -L /bin/bash
#BSUB -a poe                  # set parallel operating environment
#BSUB -J um2grb2              # job name
#BSUB -W 06:00                # wall-clock time (hrs:mins)
#BSUB -n 6                    # number of tasks in job
#BSUB -q small                # queue
#BSUB -e um2grb2.anl.00hr.err.%J.hybrid     # error file name in which %J is replaced by the job ID
#BSUB -o um2grb2.anl.00hr.out.%J.hybrid     # output file name in which %J is replaced by the job ID

# find out the directory of this bash script after submitted to bsub
DIR="$( cd "$( dirname "${BASH_SOURCE[1]}" )" && pwd )"

# get the absolute path of the local table 
localTable_relative_dir="$DIR/../../tables/local/ncmr/v1/"
localTable_absolute_dir="$( cd "$localTable_relative_dir" && pwd )"
localTable=$localTable_absolute_dir/ncmr_grib2_local_table

# get the absolute path of the script for analysis 00utc
g2scripts_relative_dir="$DIR/../../g2scripts/"
g2scripts_absolute_dir="$( cd "$g2scripts_relative_dir" && pwd )"
g2script=$g2scripts_absolute_dir/um2grb2_anl_00Z.py

# export the configure paths to needed variables
export UMRIDER_SETUP=$DIR/ncum_global_osf_input_um2grb2_setup.cfg
export UMRIDER_VARS=$DIR/ncum_global_osf_input_um2grb2_vars.cfg
export GRIB2TABLE=$localTable

echo "export UMRIDER_SETUP="$UMRIDER_SETUP
echo "export UMRIDER_VARS="$UMRIDER_VARS
echo "export GRIB2TABLE="$GRIB2TABLE

# execute the script
/gpfs2/home/umtid/Pythons/Python-2.7.9/bin/python $g2script
