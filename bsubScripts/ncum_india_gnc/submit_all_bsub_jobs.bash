#!/bin/bash

#export UMRIDER_STARTDATE=20170216

bsub < ncum_winds_anl_00Z.bash
sleep 1

bsub < ncum_sfc_anl_00Z.bash
sleep 1

bsub < ncum_pres_anl_00Z.bash
sleep 1
       

bsub < ncum_winds_fcst_00Z.bash
sleep 1

bsub < ncum_sfc_fcst_00Z.bash
sleep 1

bsub < ncum_pres_fcst_00Z.bash
sleep 1

bsub < ncum_rain_fcst_03Z.bash
sleep 1

bsub < imd_rain_obs_03Z.bash
sleep 1
