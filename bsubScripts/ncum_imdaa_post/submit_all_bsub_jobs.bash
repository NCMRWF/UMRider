#!/bin/bash

export UMRIDER_STARTDATE=19830115
#export UMRIDER_ENDDATE=19830131

## model pp filedsfiles path 
export UMRIDER_INPATH=/gpfs5/home/imdaa/cylc-run_archive_1983_1984/*YYYYMMDD*T*ZZ*00Z/ra_um/

## model grib2 files path
export UMRIDER_OUTPATH=/gpfs4/home/arulalan/um2grb2/ArulTest/NCUM_REGIONAL_IMDAA/*YYYYMMDD*/*ZZ*/

## working directory (used to create temporary log files)
export UMRIDER_TMPPATH=/gpfs4/home/arulalan/tmp/um2grb2/logs/

bsub < ncum_imdaa_regional_post_reanl_prl_00Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_prl_06Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_prl_12Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_prl_18Z.bash
sleep 1

# model level 
bsub < ncum_imdaa_regional_post_reanl_mdl_00Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_mdl_06Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_mdl_12Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_mdl_18Z.bash
sleep 1

# 2d fieldds
bsub < ncum_imdaa_regional_post_reanl_2df_00Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_2df_06Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_2df_12Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_2df_18Z.bash
sleep 1

# flux fieldds
bsub < ncum_imdaa_regional_post_reanl_flux_00Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_flux_06Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_flux_12Z.bash
sleep 1

bsub < ncum_imdaa_regional_post_reanl_flux_18Z.bash
sleep 1
