#!/usr/bin/env python

__author__ = 'arulalant'
__version__ = 'v2.0.1'
__long_name__ = 'NCUM Parallel Rider by targetting creation of TIGGE Grib2 files'

"""
Inputs: NCUM fieldsfile / pp format files

Outputs: WMO-NCEP Grib2 format files

This script produce output files as multiple 6 hourly forecasts data from
different input files such as pd, pd, pe, etc., So all 6 hourly forecasts data
of different input files will be append to same 6 hourly grib2 outfiles. 
But not limited to 6 hours only, it supports 3 hourly and 24 hourly too. 
(These conventions are according to NCUM only!)

Parallel:
As for now, we are using multiprocessing to make parallel run on different files
like pb, pd, pe and its creating child porcess with respect to no of forecast
hours. To make more parallel threads on variable, fcstHours level we may need to
use OpenMPI-Py.

Testing team in NCMRWF & their roles:
#1. Mr. Kuldeep Sharma - Main tester for visual integrety vis-a-vis GrADS & subset.ctl tool
#2. Dr. Sumit Kumar - Main tester for visual integrety vis-a-vis GrADS & subset.ctl tool  
#3. Dr. C.J. Johny - VSDB Input product tester 
#4. Mr. M.Momin Imran Ali - Hycom Input product tester 
#4. Mr. Abhishek Lodh - Soil Moisture tester 
#2. Dr. Raghavendra Ashrit - Testing for RIMES with WRF-Noah and overall integrity testing
#3. Dr. Jayakumar A. - Comparison with the CAWCR convertor and specifictions needs
#4. Dr. Saji Mohandad, TIFF Lead - Control test (GrADS & subset.tcl) & Future Functional Description
#5. Mr. Gopal Raman Iyengar - Overseer

Acknowledgments: 
#1. Mr. Raghavendra S. Mupparthy - Integrator, TIAV Lead for the
    initial serial version for grib2 conversion of NCUM pp/ff file.
#2. Dr. Rakhi R, Dr. Jayakumar A, Dr. Saji Mohandas and Mr. Bangaru (Ex-IBM) 
    for N768 and STASH corrections.
#3. Mr. Raghavendra S. Mupparthy, Dr. Rakhi R and Dr. S.Indira Rani for Rose-cycle um setup and intergration.
#4. IBM Team @ NCMRWF for installation support on Bhaskara - Ms. Shivali (IBM) & Mr. Bangaru (Ex-IBM)

References:
1. Iris. v1.8.1 03-Jun-2015. Met Office. UK. https://github.com/SciTools/iris/archive/v1.8.1.tar.gz

2. Saji M. (2014), "Utility to convert UM fieldsfile output to NCEP GRIB1 format:
                    A User Guide", NMRF/TR/01/2014, April 2014, pp. 51, available at
                    http://www.ncmrwf.gov.in/umfld2grib.pdf

Disclaimers (if any!)
This is just test code as of now and is meant for a specific purpose only!

Copyright: ESSO-NCMRWF, MoES, 2015-2016, 2016-2017.

Author : Arulalan.T
latest Update : 27-Sep-2016
"""

# -- Start importing necessary modules
import os, sys, time, subprocess, errno
import numpy, cdtime 
import iris
import gribapi
from cf_units import Unit
import multiprocessing as mp
import multiprocessing.pool as mppool       
# We must import this multiprocessing.pool explicitly, it is not imported
# by the top-level multiprocessing module.
import datetime
from iris.time import PartialDateTime
from cubeutils import cubeAverager, cubeAddSubtractor, cubeCummulator
from ncum_load_rules import update_cf_standard_name
import um2grb2 as umfcs
import umeps2grb2 as umeps
from um2grb2 import (createDirWhileParallelRacing, getCubeData, myLog, 
             __getAnlFcstFileNameIndecies__, __genAnlFcstOutFileName__, 
            getCubeAttr, _NoDaemonProcess, _MyPool)
# End of importing business

# We have to make sure that strict_grib_load as False, since we have to 
# read the cubes from grib2 to re-order the variables. True throws an error
# while reading for tweaked_messages (say pf varibles)
iris.FUTURE.strict_grib_load = False
iris.FUTURE.netcdf_promote = True
iris.FUTURE.netcdf_no_unlimited = True
iris.FUTURE.cell_datetime_objects = True
# -- Start coding
# create global _lock_ object
_lock_ = mp.Lock()

# global path variables
g2ctl = "/gpfs2/home/umtid/Softwares/grib2ctl/g2ctl.pl"
grib2ctl = "/gpfs2/home/umtid/Softwares/grib2ctl/grib2ctl.pl"
gribmap = "/gpfs1/home/Libs/GNU/GRADS/grads-2.0.2.oga.1/Contents/gribmap"
cnvgrib = "/gpfs1/home/Libs/INTEL/CNVGRIB/CNVGRIB-1.4.1/cnvgrib-1.4.1/cnvgrib"
wgrib2 = "/gpfs1/home/Libs/GNU/WGRIB2/v2.0.5/wgrib2/wgrib2"

# other global variables
__LPRINT__ = False
__utc__ = '00'
__outFileType__ = 'ana'
# start and step hour in short forecast files
__anl_step_hour__ = 6
# start hour in long forecast files
__start_long_fcst_hour__ = 6
# step hour in long forecast files
__fcst_step_hour__ = 6
# maximum long forecast hours produced by model
__end_long_fcst_hour__ = 240
# analysis reference time applicable only to average/accumulation vars.
__anl_aavars_reference_time__ = 'shortforecast'
# analysis time bounds option applicable only to average/accumulation vars.
__anl_aavars_time_bounds__ = True
# grib1 file suffix
__grib1FilesNameSuffix__ = '.grib1'
# flag for removing grib2 files after grib1 has been converted 
__removeGrib2FilesAfterGrib1FilesCreated__ = False
# fill fully masked vars with this value.
__fillFullyMaskedVars__ = None
_ensemble_count_ = 44

# Defining default out grib2 file name structure for analysis 
__anlFileNameStructure__ = ('um_ana', '_', '*HHH*', 'hr', '_', 
                            '*YYYYMMDD*', '_', '*ZZ*', 'Z', '.grib2')

# Defining default out grib2 file name structure for forecast                             
__fcstFileNameStructure__ = ('um_prg', '_', '*HHH*', 'hr', '_', 
                            '*YYYYMMDD*', '_', '*ZZ*', 'Z', '.grib2')
                            
# the _convertVars_ is global list which should has final variables list of 
# tuples (varName, varSTASH) will be converted, otherwise default variables 
# of this module will be converted!
_convertVars_ = []
_removeVars_ = []   # used to store temporary vars 
_current_date_ = None
_startT_ = None
_tmpDir_ = None
_inDataPath_ = None
_opPath_ = None
_doRegrid_ = False
_targetGrid_ = None
_targetGridFile_ = ''
_targetGridRes_ = None
_reverseLatitude_ = False
_requiredLat_ = None
_requiredLon_ = None
_requiredPressureLevels_ = None
_preExtension_ = '_unOrdered'
_createGrib2CtlIdxFiles_ = True
_createGrib1CtlIdxFiles_ = False
_convertGrib2FilestoGrib1Files_ = False
__setGrib2TableParameters__ = None
__wgrib2Arguments__ = None
_extraPolateMethod_ = 'auto'
__UMtype__ = 'global'
_ncfilesVars_ = []
__outg2files__ = []
# By default __soilFirstSecondFixedSurfaceUnit__ takes as 'cm', suggested for
# WRF-Noah model. 
__soilFirstSecondFixedSurfaceUnit__ = 'cm'
# global ordered variables (the order we want to write into grib2)
_orderedVars_ = {'PressureLevel': [
## Pressure Level Variable names & STASH codes
('geopotential_height', 'm01s16i202'),        
('x_wind', 'm01s15i201'), 
('y_wind', 'm01s15i202'),   
('upward_air_velocity', 'm01s15i242'),
('air_temperature', 'm01s16i203'),
('relative_humidity', 'm01s16i256'),
('specific_humidity', 'm01s30i205')],

## Non Pressure Level Variable names & STASH codes
'nonPressureLevel': [
('tropopause_altitude', 'm01s30i453'),
('tropopause_air_temperature', 'm01s30i452'),
('tropopause_air_pressure', 'm01s30i451'),
('surface_air_pressure', 'm01s00i409'),
('air_pressure_at_sea_level', 'm01s16i222'),
('surface_temperature', 'm01s00i024'),
('relative_humidity', 'm01s03i245'), 
('specific_humidity', 'm01s03i237'),
('air_temperature', 'm01s03i236'),
('dew_point_temperature', 'm01s03i250'),
('atmosphere_convective_available_potential_energy_wrt_surface', 'm01s05i233'), # CAPE
('atmosphere_convective_inhibition_wrt_surface', 'm01s05i234'), #CIN
('high_type_cloud_area_fraction', 'm01s09i205'),
('medium_type_cloud_area_fraction', 'm01s09i204'),
('low_type_cloud_area_fraction', 'm01s09i203'), 
('cloud_area_fraction_assuming_random_overlap', 'm01s09i216'),
('cloud_area_fraction_assuming_maximum_random_overlap', 'm01s09i217'),
('x_wind', 'm01s03i225'), 
('y_wind', 'm01s03i226'), 
('x_wind', 'm01s15i212'),  # 50meter B-Grid U component wind 
('y_wind', 'm01s15i213'),  # 50meter B-Grid V component wind     
('visibility_in_air', 'm01s03i247'),
('precipitation_amount', 'm01s05i226'),
('stratiform_snowfall_amount', 'm01s04i202'),
('convective_snowfall_amount', 'm01s05i202'),
('stratiform_rainfall_amount', 'm01s04i201'),
('convective_rainfall_amount', 'm01s05i201'),
('rainfall_flux', 'm01s05i214'),
('snowfall_flux', 'm01s05i215'),
('precipitation_flux', 'm01s05i216'),
('atmosphere_mass_content_of_water', 'm01s30i404'),
('atmosphere_mass_content_of_dust_dry_aerosol_particles', 'm01s30i403'),
('atmosphere_cloud_liquid_water_content', 'm01s30i405'),
('atmosphere_cloud_ice_content', 'm01s30i406'),
('fog_area_fraction', 'm01s03i248'),
('toa_incoming_shortwave_flux', 'm01s01i207'), 
('toa_outgoing_shortwave_flux', 'm01s01i205'),
('toa_outgoing_shortwave_flux_assuming_clear_sky', 'm01s01i209'),  
('toa_outgoing_longwave_flux', 'm01s02i205'),
('toa_outgoing_longwave_flux_assuming_clear_sky', 'm01s02i206'),   
('surface_upward_latent_heat_flux', 'm01s03i234'),
('surface_upward_sensible_heat_flux', 'm01s03i217'),
('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'),
('surface_downwelling_longwave_flux', 'm01s02i207'),
('surface_net_downward_longwave_flux', 'm01s02i201'), 
('surface_net_downward_shortwave_flux', 'm01s01i202'),
('atmosphere_boundary_layer_thickness', 'm01s00i025'),
('atmosphere_optical_thickness_due_to_dust_ambient_aerosol', 'm01s02i422'),
('moisture_content_of_soil_layer', 'm01s08i223'),  # 4 layers 
# single layer, this must be after 4 layers as in order 
('soil_moisture_content', 'm01s08i208'),       # single layer  
## though moisture_content_of_soil_layer and volumetric_moisture_of_soil_layer
## has same STASH code, but we must include seperate entry here.
('volumetric_moisture_of_soil_layer', 'm01s08i223'), # 4 layers
# single layer, this must be after 4 layers as in order 
('volumetric_moisture_of_soil_layer', 'm01s08i208'), # single layer
('soil_temperature', 'm01s03i238'),  
('land_binary_mask', 'm01s00i030'),
('sea_ice_area_fraction', 'm01s00i031'),
('sea_ice_thickness', 'm01s00i032'),
# the snowfall_amount might be changed as 
# liquid_water_content_of_surface_snow by convert it into
# water equivalent of snow amount, before re-ordering itself.
('liquid_water_content_of_surface_snow', 'm01s00i023'),
# the below one is for orography which presents only in analysis 00 file.
# so we must keep this as the last one in the ordered variables!
('surface_altitude', 'm01s00i033')],
}
  

#Define _precipVars_
# The following vars should contains only precipitation, rainfall, snow 
# variables, those whose regrid extrapolate should be only in 'linear' mode
# and not in 'mask' mode, and should not have -ve values.
_precipVars_ = [('precipitation_amount', 'm01s05i226'),
              ('stratiform_snowfall_amount', 'm01s04i202'),
              ('convective_snowfall_amount', 'm01s05i202'),
              ('stratiform_rainfall_amount', 'm01s04i201'),
              ('convective_rainfall_amount', 'm01s05i201'),
              ('rainfall_flux', 'm01s05i214'),
              ('snowfall_flux', 'm01s05i215'),
              ('precipitation_flux', 'm01s05i216')]

# Define _accumulationVars_
# The following variables should be 6-hourly accumulated, but model
# produced as 1-hourly accumulation. So we need to sum of 6-hours data to 
# get 6-hourly accumulation.
# rainfall_flux, snowfall_flux, precipitation_flux are not accumulated 
# vars, since those are averaged rain rate (kg m-2 s-1). 
# But the following vars unit is (kg m-2), accumulated vars.  
_accumulationVars_ = [('precipitation_amount', 'm01s05i226'),
                      ('surface_net_downward_shortwave_flux', 'm01s01i202'),
                      ('surface_net_downward_longwave_flux', 'm01s02i201'), 
                      ('surface_upward_latent_heat_flux', 'm01s03i234'),   
                      ('surface_upward_sensible_heat_flux', 'm01s03i217'),   
                      ('toa_outgoing_longwave_flux', 'm01s02i205')]                    

# TIGGE's totoal time cummulated variables
_total_cummulativeVars_ = ['precipitation_amount', 
                           'surface_net_downward_shortwave_flux', 
                           'surface_net_downward_longwave_flux', 
                           'surface_upward_latent_heat_flux', 
                           'surface_upward_sensible_heat_flux', 
                           'toa_outgoing_longwave_flux',
                           'time_cummulated_precipitation',
                           'time_integrated_surface_net_downward_shortwave_flux', 
                           'time_integrated_surface_net_downward_longwave_flux', 
                           'time_integrated_surface_upward_latent_heat_flux', 
                           'time_integrated_surface_upward_sensible_heat_flux', 
                           'time_integrated_toa_outgoing_longwave_flux',] 

                 
## Define _ncmrGrib2LocalTableVars_
## the following variables need to be set localTableVersion no as 1 and
## master table version no as 255 (undefined), since WRF grib2 table doesnt
## support for the following variables. So we created our own local table.
_ncmrGrib2LocalTableVars_ = ['fog_area_fraction',
                            'toa_outgoing_longwave_flux_assuming_clear_sky',   
                            'toa_outgoing_shortwave_flux_assuming_clear_sky',
                  'atmosphere_optical_thickness_due_to_dust_ambient_aerosol',
                     'atmosphere_mass_content_of_dust_dry_aerosol_particles',
                               'cloud_area_fraction_assuming_random_overlap',
                       'cloud_area_fraction_assuming_maximum_random_overlap',]

## Define _maskOverOceanVars_
## the following variables need to be set mask over ocean because the original
## model itself producing mask over ocean. but when we are doing regrid it 
## couldnt retain the mask ! dont know why ! So using land_binary_mask 
## variable, we are resetting mask over ocean for the following vars.
_maskOverOceanVars_ = ['moisture_content_of_soil_layer', 
        'soil_moisture_content', 'volumetric_moisture_of_soil_layer', 
        # 'moisture_content_of_soil_layer' and 'soil_moisture_content' are 
        # renamed as  'volumetric_moisture_of_soil_layer', 
        # but same STASH m01s08i223 and m01s08i208 code.
                 'soil_temperature']
 
## Define dust aerosol optical thickness of model pseudo level with its 
## corresponding micron / micro wavelength. We need to tweak with following 
## information before writing into final grib2 file.
_aod_pseudo_level_var_ = {
'atmosphere_optical_thickness_due_to_dust_ambient_aerosol': [
(1, '0.38'), (2, '0.44'), (3, '0.55'), (4, '0.67'), (5, '0.87'), (6, '1.02')]}

## Define _depedendantVars_ where A is key, B is value. A is depedendant on B,
## B is not. B not necessarily to be written in out file. User may just specify
## only A in var.cfg configure file.
_depedendantVars_ = {
# land_binary_mask is needed to set ocean mask 
('volumetric_moisture_of_soil_layer', 'm01s08i208'): [('land_binary_mask', 'm01s00i030')],
('moisture_content_of_soil_layer', 'm01s08i208'): [('land_binary_mask', 'm01s00i030')],
('soil_temperature', 'm01s03i238'): [('land_binary_mask', 'm01s00i030')],
# need to calculate surface up sw/lw using surface down & net sw/lw fluxes
('surface_upwelling_shortwave_flux_in_air', 'None'): [
                 ('surface_net_downward_shortwave_flux', 'm01s01i202'),
                 ('surface_downwelling_shortwave_flux_in_air', 'm01s01i235')],
                 
('surface_upwelling_longwave_flux_in_air', 'None'): [
                        ('surface_net_downward_longwave_flux', 'm01s02i201'), 
                        ('surface_downwelling_longwave_flux', 'm01s02i207')],

('atmosphere_precipitable_water_content', 'None'): [
    ('atmosphere_mass_content_of_water', 'm01s30i404'),
    ('atmosphere_mass_content_of_dust_dry_aerosol_particles', 'm01s30i403'),
    ('atmosphere_cloud_liquid_water_content', 'm01s30i405'),
    ('atmosphere_cloud_ice_content', 'm01s30i406'),    
    ]
}


ncumSTASH_tiggeVars = {
######################## BEGIN OF TIGGE-VALID-VARS-IN-BOTH-NCUM-DETERMINISTIC-ENSEMBLES ################
# PressureLevel Variables
('geopotential_height', 'm01s16i202'): ('geopotential_height', 'gh', None), # 'gpm'
('specific_humidity', 'm01s30i205'): ('specific_humidity', 'q', 'kg kg-1'),
('air_temperature', 'm01s16i203'): ('temperature', 't', 'K'),
('x_wind', 'm01s15i243'): ('u_velocity', 'u', 'm s-1'),
('y_wind', 'm01s15i244'): ('v_velocity', 'v', 'm s-1'),
('x_wind', 'm01s15i201'): ('u_velocity', 'u', 'm s-1'), #deterministic
('y_wind', 'm01s15i202'): ('v_velocity', 'v', 'm s-1'), #deterministic

# SingleLevel Variables
('x_wind', 'm01s03i209'): ('10_meter_u_velocity', '10u', 'm s-1'),
('y_wind', 'm01s03i210'): ('10_meter_v_velocity', '10v', 'm s-1'),
('x_wind', 'm01s03i225'): ('10_meter_u_velocity', '10u', 'm s-1'), #deterministic
('y_wind', 'm01s03i226'): ('10_meter_v_velocity', '10v', 'm s-1'), #deterministic
('land_binary_mask', 'm01s00i030'): ('land_sea_mask', 'lsm', None), # Proportion
('air_pressure_at_sea_level', 'm01s16i222'): ('mean_sea_level_pressure', 'msl', 'Pa'), 
('surface_altitude', 'm01s00i033'): ('orography', 'orog', None), # 'gpm' 
('air_temperature', 'm01s03i236'): ('surface_air_temperature', '2t', 'K'),
('air_temperature_maximum', 'm01s03i236'): ('surface_air_maximum_temperature', 'mx2t6', 'K'),   
('air_temperature_minimum', 'm01s03i236'): ('surface_air_minimum_temperature', 'mn2t6', 'K'),
('dew_point_temperature', 'm01s03i250'): ('surface_air_dew_point_temperature', '2d', 'K'),
('surface_temperature', 'm01s00i024'): ('skin_temperature', 'skt', 'K'),
('moisture_content_of_soil_layer', 'm01s08i223'): ('soil_moisture', 'sm', 'K'),
('soil_temperature', 'm01s03i238'): ('soil_temperature', 'st', 'K'),                        
('surface_air_pressure', 'm01s00i409'): ('surface_pressure', 'sp', 'Pa'),
('precipitation_amount', 'm01s05i226'): ('total_precipitation', 'tp', 'kg m-2'), # intermediate file 
('time_cummulated_precipitation', 'None'): ('total_precipitation', 'tp', 'kg m-2'), 

('surface_upward_latent_heat_flux', 'm01s03i234'): ('time_integrated_surface_latent_heat_flux', 'slhf', None), # intermediate file  
('time_integrated_surface_upward_latent_heat_flux', 'm01s03i234'): ('time_integrated_surface_latent_heat_flux', 'slhf', 'W m-2 s'),

('surface_upward_sensible_heat_flux', 'm01s03i217'): ('time_integrated_surface_sensible_heat_flux', 'sshf', None), # intermediate file 
('time_integrated_surface_upward_sensible_heat_flux', 'm01s03i217'): ('time_integrated_surface_sensible_heat_flux', 'sshf', 'W m-2 s'),

('surface_net_downward_longwave_flux', 'm01s02i201'): ('time_integrated_surface_net_thermal_radiation', 'str', None), # intermediate file 
('time_integrated_surface_net_downward_longwave_flux', 'm01s02i201'): ('time_integrated_surface_net_thermal_radiation', 'str', 'W m-2 s'),

('surface_net_downward_shortwave_flux', 'm01s01i202'): ('time_integrated_surface_net_solar_radiation', 'ssr', None), # intermediate file 
('time_integrated_surface_net_downward_shortwave_flux', 'm01s01i202'): ('time_integrated_surface_net_solar_radiation', 'ssr', 'W m-2 s'),

('toa_outgoing_longwave_flux', 'm01s02i205'): ('time_integrated_outgoing_long_wave_radiation', 'ttr', None), # intermediate file 
('time_integrated_toa_outgoing_longwave_flux', 'm01s02i205'): ('time_integrated_outgoing_long_wave_radiation', 'ttr', 'W m-2 s'),

######################## END OF TIGGE-VALID-VARS-IN-BOTH-NCUM-DETERMINISTIC-ENSEMBLES ################

######################## BEGIN OF TIGGE-VALID-VARS-ONLY-AVAILABLE-IN-DETERMINISTIC ###################
('cloud_area_fraction_assuming_maximum_random_overlap', 'm01s09i217'): ('total_cloud_cover', 'tcc', '%'),
### Doubts fluxes input needs to be divided by no of sec in the 3-hour or 1-hour 
## upward, dowward , + / - ???
######################## END OF TIGGE-VALID-VARS-ONLY-AVAILABLE-IN-DETERMINISTIC ###################
}

     

def getTiggeFileName(cube):
    # follows as per standard of tigge
    # https://software.ecmwf.int/wiki/display/TIGGE/TIGGE+Data+Exchange+Protocol
    # z_tigge_c_cccc_yyyymmddhhmmss_mmmm_vvvv_tt_ll_ssss_nnn_llll_param

    prefix = 'z_tigge_c'
    cccc = 'dems' # DEMS Delhi Meteorological Station centre code (WMO Standard)
    mmmm = 'glob'
    vvvv = 'test' # TIGGE TEST 
    cstash = None
    
    # get the cube time and make it as yyyymmddhhmmss
    tpoint = cube.coords('forecast_reference_time')[0].points[0]
    tunit = cube.coords('forecast_reference_time')[0].units.name 
    ct = cdtime.reltime(tpoint, tunit).tocomp()
    yyyymmddhhmmss = str(ct.year) + str(ct.month).zfill(2) + str(ct.day).zfill(2)
    yyyymmddhhmmss+= str(ct.hour).zfill(2) + str(ct.minute).zfill(2) + str(int(ct.second)).zfill(2)

    # get the type of forecast        
    if cube.coords('realization'):
        if cube.coords('realization')[0].points[0] == 0:
            tt = 'cf' # control forecast
        else:
            tt = 'pf' # perturbed forecast
    else:
        tt = 'fc' # deterministic forecast
        
    # pressure level or single level 
    ll = 'pl' 
    if cube.coords('pressure'):
        ll = 'pl'
        llll = str(int(cube.coords('pressure')[0].points[0])).zfill(4)
    else:
        ll = 'sl'
        llll = '0000'

    # assign forecast hour 
    if cube.coords('forecast_period')[0].bounds is None:
        # instantaneous time point  
        ssss = cube.coords('forecast_period')[0].points[0]
    else:
        # end time of bound time or
        ssss = cube.coords('forecast_period')[0].bounds[0][-1]    
    ssss = str(int(ssss)).zfill(4)

    # ensemble no 
    if cube.coords('realization'):
        nnn = str(int(cube.coords('realization')[0].points[0])).zfill(3)
    else:
        nnn = '000'

    # get the tigge standard short name
    cname = cube.standard_name if cube.standard_name else cube.long_name
    cstash = str(cube.attributes.get('STASH', 'None'))
    tiggeName, tiggeParam, tiggeUnit = ncumSTASH_tiggeVars.get((cname, cstash), (None, None, None))
    
    # set tigge unit
    if tiggeUnit: cube.units = Unit(tiggeUnit)    
    # return the tigge standard file name of this cube.
    outfilename = '_'.join([prefix, cccc, yyyymmddhhmmss, mmmm, vvvv, 
                                        tt, ll, ssss, nnn, llll, tiggeParam])
    return outfilename, tiggeParam
# end of def getTiggeFileName(cube, datatype):

# start definition #5
def regridAnlFcstFiles(arg):
    """
    New Module by AAT:
    This module has been rewritten entirely by AAT for optimization as an embarassingly-
    parallel problem! It also checks the std names from Iris cube format with the
    CF-convention and it regrids the data to 0.25x0.25 regular grid using linear
    interpolation methods.
    :param arg: tuple(fname, hr)
            fname: common filename
            hr: forecast hour
    :return: regridded cube saved as GRIB2 file! TANGIBLE!
    ACK:
    This module has been entirely revamped & improved by AAT based on an older and
    serial version by MNRS on 11/16/2015.
    """
    global _lock_, _targetGrid_, _targetGridRes_, _current_date_, _startT_, \
           _inDataPath_, _opPath_, _preExtension_, _accumulationVars_, _ncfilesVars_, \
           _convertVars_, _requiredLat_, _requiredLon_, _doRegrid_, __utc__, \
           __anlFileNameStructure__, __fcstFileNameStructure__, __LPRINT__, \
           __fcst_step_hour__, __anl_step_hour__, _targetGridFile_, __UMtype__, \
           _precipVars_, _requiredPressureLevels_, __anl_aavars_reference_time__, \
           __anl_aavars_time_bounds__, _extraPolateMethod_, _maskOverOceanVars_, \
           __fillFullyMaskedVars__,  _reverseLatitude_ 
   
    fpname, hr = arg 
    
    if  __UMtype__ == 'global':
        ### if fileName has some extension, then do not add hr to it.
        fileName = fpname + hr if not '.' in fpname else fpname
    elif  __UMtype__ == 'regional':
        if '.' in fpname:
            fileName = fpname 
        else:
           fileName = fpname if '.' in fpname else fpname + hr.zfill(3) 
        # end of if '.' in pfname:
    # end of if  __UMtype__ == 'global':
    
    fname = os.path.join(_inDataPath_, fileName)        
    inDataPathHour = _inDataPath_.split('/')[-1]  
    # call definition to get variable indices
    varNamesSTASH, fcstHours, doMultiHourlyMean, infile, simulated_hr = umfcs.getVarInOutFilesDetails(_inDataPath_, fileName, hr)
    if not os.path.isfile(fname): 
        print "The file doesn't exists: %s.. \n" %fname
        return  
    # end of if not os.path.isfile(fname): 
    
    if _convertVars_:
        # load only needed variables from this file !
        varNamesSTASH = [vns for vns in varNamesSTASH if vns in _convertVars_]
    
    if not varNamesSTASH:
        print "No varibale selected to load from the file '%s' " % fname
        if __LPRINT__: 
            print "Because global variable _convertVars_ doesn't contain any one of the following variables"
            print "\n".join([str(i+1)+' : ' + str(tu) for i, tu in enumerate(varNamesSTASH)])
        return None
    else:
        print "The following variables are going to be converted from file ", fname
        print "\n".join([str(i+1)+' : ' + str(tu) for i, tu in enumerate(varNamesSTASH)])
    # end of if not varNamesSTASH:
    
    print "Started Processing the file: %s.. \n" %infile
    
    # call definition to get cube data
    cubes = getCubeData(infile)
    nVars = len(cubes)
    simulated_hr = int(infile.split('/')[-2])
    if __LPRINT__: print "simulated_hr = ", simulated_hr
    print "simulated_hr = ", simulated_hr
    
    if fpname.startswith(('umglaa', 'umnsaa')):
        dtype = 'fcst'         
        outFileNameStructure = __fcstFileNameStructure__
        start_step_fcst_hour = __fcst_step_hour__
    elif fpname.startswith(('umglca', 'qwqg00')):
        dtype = 'ana'
        outFileNameStructure = __anlFileNameStructure__
        start_step_fcst_hour = __anl_step_hour__
    # end of if fpname.startswith('umglaa'):
    
    # get the out fileName Structure based on pre / user defined indecies                       
    outFnIndecies = __getAnlFcstFileNameIndecies__(outFileNameStructure)
    # get the file name extension
    fileExtension = outFileNameStructure[-1]
    #####
    ### setting timepoint, fcstpoint as 'centre' bounds, will not affect
    ### in g2ctl.pl because it uses flag -verf by default which will set 
    ### access time point as end time point of fcst bounds.
    timepoint = 'cbound'            # TESTED, OK, on 05-01-2016
    fcstpoint = 'cbound'            # TESTED, OK, on 05-01-2016
    timebound = True                # TESTED, OK, on 28-03-2016
    fcstbound = True                # TESTED, OK, on 28-03-2016
    
    # Note : if we are not correcting ana, fcst fcstpoint as above, in g2ctl
    # ctl file will has 2 time points. To avoid that we have to tell to g2ctl
    # to use start time bound for analysis and last time bound for fcst, 
    # which brings to  1 time point.
    
    # Define default lat, lon, pressure contraint (None just bring model global data)
    latConstraint, lonConstraint, pressureConstraint = None, None, None
    if _requiredLat_: 
        # make constraint of required latitude
        latConstraint = iris.Constraint(latitude=lambda cell: 
                                _requiredLat_[0] <= cell <= _requiredLat_[-1])
    if _requiredLon_:
        # make constraint of required longitude
        lonConstraint = iris.Constraint(longitude=lambda cell: 
                                _requiredLon_[0] <= cell <= _requiredLon_[-1])
    
    if _requiredPressureLevels_:
        # make constraint of required pressure 
        # To slice out particular pressure levels (like 850, 200, 1000 alone)
        # then the following way is essential.       
        pressureConstraint = iris.Constraint(pressure=lambda cell: 
                                int(cell.point) in _requiredPressureLevels_)
                            
    # open for-loop-1 -- for all the variables in the cube
    for varName, varSTASH in varNamesSTASH:
        # define variable name constraint
        varConstraint = iris.Constraint(name=varName)
        # define varibale stash code constraint
        STASHConstraint = iris.AttributeConstraint(STASH=varSTASH)
        
        if not cubes.extract(varConstraint & STASHConstraint): 
            raise ValueError("unable to extract variable %s %s" % (varName, varSTASH))
        
        # get the standard_name of variable 
        stdNm = cubes.extract(varConstraint & STASHConstraint)[0].standard_name
        longNm = cubes.extract(varConstraint & STASHConstraint)[0].long_name
        print "stdNm", stdNm, infile
        if stdNm is None and longNm is None:
            print "Unknown variable standard_name for '%s' of %s. So skipping it" % (varName, infile)
            continue
        # end of if stdNm is None and longNm is None:
        print "  Working on variable: %s \n" %stdNm
        
        if (varName, varSTASH) in [('soil_temperature', 'm01s03i238'), 
                        ('moisture_content_of_soil_layer', 'm01s08i223')]:                        
            # Within pi file, these variable has instantaneous time point,
            # rest of other variables in pi file are 3-hr averaged.
            # get an instantaneous forecast time for soil_temperature, and 
            # moisture_content_of_soil_layer. 
            if dtype == 'ana':
                ana_soil_infile = os.path.join(_inDataPath_, fileName)
                cubes = getCubeData(ana_soil_infile)   
                simulated_hr = int(ana_soil_infile.split('/')[-2])                
                # get instantaneous forecast hours to be extracted.
                fcstHours = numpy.array([0,])
                print varName, "loaded from file, ", ana_soil_infile
                print "simulated_hr = ", simulated_hr
            elif dtype == 'fcst':                         
                # get instantaneous forecast hours to be extracted.
                if isinstance(fcstHours[0], numpy.ndarray):
                    fcstHours += 1  # adjust fcst hour by add 1
                    idx = 1         # get second time in tuple        
                    # do this process only one time though we have 2 variables
                    # here (both soil_temperature & moisture_content_of_soil_layer)
                    # becase here we are overwriting fcstHours which we 
                    # previously defined in umfcs.getVarInOutFilesDetails function.
                    fcstHours = numpy.array([fhr[idx] for fhr in fcstHours])
                print varName,"fcstHours", fcstHours
        # end of if (varName, varSTASH) in [...]:
        
        if (varName, varSTASH) in _accumulationVars_:
            # From pe files, we need to extract precipitation_amount fileds
            # as 6 hourly accumulation, but other variables from pe files
            # are instantaneous fileds (no need to 6 hourly mean/sum).
            # both analysis & forecast need to be accumulation.
            doMultiHourlyMean = True
            if dtype == 'fcst':
                # for forecast pe file, and this varibale we need to set the 
                # extract time as follows. 
                # the cube contains data of every 1-hourly accumutated.
                # but we need to make only every 6th hourly accumutated.
                # fileName[-3:] is equivalent to hr. but hr had updated in 
                # filename extension for some case. So it better extract 
                # forecast hour from the fileName itself.                
                fcstHours = numpy.arange(24).reshape(4, 6) + int(fileName[-3:]) + 0.5 
                # required since NCUM 10.2 onwards
                print varName, "fcstHours ", fcstHours, int(fileName[-3:])
            elif dtype == 'ana':
                # for analysis pe file, and this varibale we need to set the 
                # extract time as follows. 
                # the cube contains data of every 1-hourly accumutated.
                # but we need to make only every 6th hourly accumutated.
                fcstHours = numpy.array([(0, 1, 2, 3, 4, 5)]) + 0.5 # required since NCUM 10.2 onwards
                ana_precip_infile, simulated_hr = umfcs.__getTodayOrYesterdayInfile__(_inDataPath_, fileName)    
                if ana_precip_infile != infile: 
                    cubes = getCubeData(ana_precip_infile)   
                    print varName, "loaded from file, ", ana_precip_infile
                    print "simulated_hr = ", simulated_hr
                # end of if ana_infile != infile:               
        # end of if (varName, varSTASH) in _accumulationVars_:
        
        # define (simulated_hr) forecast_reference_time constraint
        fcstRefTimeConstraint = iris.Constraint(forecast_reference_time=PartialDateTime(hour=int(simulated_hr)))
        if __LPRINT__: print fcstRefTimeConstraint
        for fhr in fcstHours:
            # loop-2 -- runs through the selected time slices - synop hours                        
            if __LPRINT__: print "   Working on forecast time: ", fhr            
            # grab the variable which is f(t,z,y,x)
            # tmpCube corresponds to each variable for the SYNOP hours
            if __LPRINT__: print "extract start", infile, fhr, varName
            # get the varibale iris cube by applying variable name constraint, 
            # variable name, stash code, forecast_reference_time constraints
            # and forecast hour constraint
            if __LPRINT__: print varConstraint, STASHConstraint, fhr,
            if __LPRINT__: print fcstRefTimeConstraint, latConstraint, lonConstraint
            if fhr is not None:
                # make forecast_period constraint
                fpConstraint = iris.Constraint(forecast_period=fhr)
            if __anl_step_hour__ == 3 and inDataPathHour == '00' and fhr == 0 \
                                            and fpname.startswith('umglca_pe'):
                if (varName, varSTASH) in [('air_pressure_at_sea_level', 'm01s16i222'), 
                            ('surface_air_pressure', 'm01s00i409'),]:
                    # these vars taken already from qwqg00.pp0 file. 
                    continue                    
            # end of if __anl_step_hour__ == 3 and fhr == 0:
                
            if __anl_step_hour__ == 3 and fhr == 1.5:
                # Load from current date instead of yesterday date 
                ana_today_infile = os.path.join(_inDataPath_, fileName)                 
                if ana_today_infile != infile: 
                    a3_1p5_cube = getCubeData(ana_today_infile)   
                    a3_simulated_hr = int(ana_today_infile.split('/')[-2])
                    a3_fcstRefTime = iris.Constraint(forecast_reference_time=PartialDateTime(hour=a3_simulated_hr))
                    # extract based on new constraints which are all applicable only to ana 1.5 hours.
                    tmpCube = a3_1p5_cube.extract(varConstraint & 
                                    STASHConstraint & a3_fcstRefTime &
                                    fpConstraint &
                                    latConstraint & lonConstraint)
                    print "special load of ana_hour 1.5"
                    print varName, "loaded from today infile, ", ana_today_infile
                    print "simulated_hr = ", simulated_hr            
            else:
                # extract cube with possible and required constraints
                tmpCube = cubes.extract(varConstraint & STASHConstraint & 
                                    fcstRefTimeConstraint &
                                    fpConstraint &
                                    latConstraint & lonConstraint)
            # end of if __anl_step_hour__ == 3 and fhr == 1.5:
            print "tmpCube=", tmpCube
            if not tmpCube: raise ValueError("unable to extract variable %s %s %d" % varName, varSTASH, fhr)
            # Got variable successfully!    
            tmpCube = tmpCube[0]
            
            # extract pressure levels
            if pressureConstraint and tmpCube.coords('pressure'): 
                tmpCube = tmpCube.extract(pressureConstraint)
            # ene of if pressureConstraint and tmpCube.coords('pressure'): 
            
            if __LPRINT__: print "extract end", infile, fhr, varName
            if __LPRINT__: print "tmpCube =>", tmpCube
            if tmpCube.has_lazy_data():
                print "Loaded", tmpCube.standard_name, "into memory",
                ## By accessing tmpCube.data (even for printing), the full 
                ## data has been loaded into memory instead of being lazy 
                ## data. Especially for dust aod, we must make it as fully 
                ## loaded otherwise full data will be treated as zeros only 
                ## instead of 6 pseudo_level data.
                print "- min", tmpCube.data.min(), "max", tmpCube.data.max(),
                print "has_lazy_data =", tmpCube.has_lazy_data()
            # end of if tmpCube.has_lazy_data():
            
            if (varName, varSTASH) == ('snowfall_amount', 'm01s00i023'):
                # the snowfall_amount need to be changed as 
                # liquid_water_content_of_surface_snow by convert it into
                # water equivalent of snow amount.                    
                umfcs._convert2WEASD(tmpCube)
            # end of if (varName, varSTASH) == ('snowfall_amount', 'm01s00i023'):
            
            if doMultiHourlyMean and (tmpCube.coords('forecast_period')[0].shape[0] > 1):              
                # grab the variable which is f(t,z,y,x)
                # tmpCube corresponds to each variable for the SYNOP hours from
                # start to end of short time period mean (say 3-hourly)                                
                cubeName = tmpCube.standard_name    
                cubeName = cubeName if cubeName else ''
                # get action as either do we have to accumulation or mean.
                action = 'sum' if (cubeName, varSTASH) in _accumulationVars_ else 'mean'
                # convert 3-hourly mean data into 6-hourly mean or accumulation
                # actionIntervals is 6 hourly mean or accumulation
                # here dt intervals meant to be forecast intervals, as per 
                # model, it forecast every one hour. so we must pass as 
                # '1 hour' to dt intervals argument. 
                if __LPRINT__: print "action = ", action
                print "tmpCube", tmpCube
                tmpCube = cubeAverager(tmpCube, action, dt='1 hour', 
                            actionIntervals=str(start_step_fcst_hour)+' hour', 
                                           tpoint=timepoint, fpoint=fcstpoint, 
                                         tbounds=timebound, fbounds=fcstbound)
            # end of if doMultiHourlyMean and tmpCube.coords('forecast_period')[0].shape[0] > 1:     
            print "before regrid", varName, tmpCube.data.min(), tmpCube.data.max()             
            exmode = None # required, when user didnt do any regrid
            # interpolate it as per targetGridResolution deg resolution by 
            # setting up sample points based on coord            
            if _doRegrid_:
                if __LPRINT__: print "From shape", tmpCube.shape                    
                if (varName, varSTASH) in _precipVars_:
                    # DO NOT APPLY iris.analysis.Linear(extrapolation_mode='mask'), 
                    # which writes nan every where for the snowfall_flux,  
                    # rainfall_flux, precipitation_flux. So donot apply that.         
                    exmode = 'linear'
                else:
                    # In general all the other variables should not be 
                    # extrapolated over masked grid points.
                    exmode = 'mask'
                # end of if (...):
                # However, if user specified custom method do that!                
                exmode = _extraPolateMethod_ if _extraPolateMethod_ != 'auto' else exmode
                # but make sure that soil variables (or whichever variables do not have values over ocean)
                # do not extrapolate over ocean/masked regions. Otherwise, it will write only nan.
                exmode = 'mask' if varName in _maskOverOceanVars_ else exmode
                    
                if os.path.isfile(_targetGridFile_):
                    print "\n Regridding data to %s degree spatial resolution based on file %s\n" % (_targetGrid_.shape, _targetGridFile_) 
                    # Do regrid based on user specfied target grid file.
                    scheme = iris.analysis.Linear(extrapolation_mode=exmode)
                    regdCube = tmpCube.regrid(_targetGrid_, scheme)
                    print "regrid data shape", regdCube.shape 
                else:           
                    # Do regrid based on user specfied target grid resolution number.
                    print "\n Regridding data to %sx%s degree spatial resolution \n" % (_targetGridRes_, _targetGridRes_)                    
                    try:
                        # This lienar interpolate will do extra polate over ocean even 
                        # though original data doesnt have values over ocean and wise versa.
                        # So lets be aware of this.                    
                        regdCube = tmpCube.interpolate(_targetGrid_, iris.analysis.Linear(extrapolation_mode=exmode))
                    except Exception as e:
                        print "ALERT !!! Error while regridding!! %s" % str(e)
                        print " So skipping this without saving data"
                        continue
                    # end of try:      
            else:
                # do not apply regrid. this is temporary fix. 
                regdCube = tmpCube
            # end of if _doRegrid_:

            if _reverseLatitude_:
                # Need to reverse latitude from SN to NS
                rcsh = len(regdCube.data.shape)
                if rcsh == 3:
                    regdCube.data = regdCube.data[:,::-1,:]
                elif rcsh == 2:
                    regdCube.data = regdCube.data[::-1,:]
                lat = regdCube.coords('latitude')[0]
                lat.points = lat.points[::-1]
            # end of if _reverseLatitude_:
            
            unit = regdCube.units
            if varName.endswith('_flux'):
                # applicable only to TIGGE 
                # converting flux unit from time average into time integrated
                # by multiplying 60*60*6 = 21600 seconds in 6-hour 
                regdCube.data *= 21600.0     
                unit = Unit('W m-2 s') # changed unit from (W m-2) into (W m-2 s)           
                print "Multiplied data with 60*60*6 seconds to make flux variable into time-intergrated"
                print regdCube.data.min(), regdCube.data.max()
            # end of if varName.endswith('_flux'):
            
            if (varName, varSTASH) in _precipVars_:
                # Since we are not using 'mask' option for extrapolate while 
                # doing linear regrid, which bring -ve values after regrid in 
                # extrapolated grids. So lets make it as 0 as minimum value.
                regdCube.data[regdCube.data < 0.0] = 0.0
            # end of if (varName, varSTASH) in _precipVars_:
            
            if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
                regdCube.data[regdCube.data > 0] = 1
                # trying to keep values either 0 or 1. Not fraction!
                regdCube.data = numpy.ma.array(regdCube.data, dtype=numpy.int)            
            # end of if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
            
            
            if (varName, varSTASH) in [('surface_altitude', 'm01s00i033')]:
                regdCube.standard_name = None
                regdCube.long_name = 'orography'
            # end of if (varName, varSTASH) in [('surface_altitude', 'm01s00i033')]:
            
            if exmode == 'mask':
                # For the above set of variables we shouldnot convert into 
                # masked array. Otherwise its full data goes as nan.                
                # convert data into masked array
                regdCube.data = numpy.ma.masked_array(regdCube.data, 
                                    dtype=numpy.float64, fill_value=9.999e+20) 
                
                if (varName, varSTASH) in [('moisture_content_of_soil_layer', 'm01s08i223'),
                                           ('sea_ice_area_fraction', 'm01s00i031'),
                                           ('sea_ice_thickness', 'm01s00i032'),]:
                        # We should assign 0 instead 1e-15 only for this var!
                        regdCube.data[regdCube.data <= 1e-15] = 0.0
                elif (varName, varSTASH) == ('soil_temperature', 'm01s03i238'):
                    # We should assign min instead 1e-15 only for this var!
                    # because 0 will not make sense when temperature unit is Kelvin
                    nmin = numpy.ma.masked_less_equal(regdCube.data, 1e-15).min()
                    regdCube.data[regdCube.data <= 1e-15] = nmin
                # http://www.cpc.ncep.noaa.gov/products/wesley/g2grb.html
                # Says that 9.999e+20 value indicates as missingValue in grib2
                # by default g2ctl.pl generate "undefr 9.999e+20", so we must 
                # keep the fill_value / missingValue as 9.999e+20 only.
                numpy.ma.set_fill_value(regdCube.data, 9.999e+20)    
            # end of if exmode == 'mask':
                        
            if __fillFullyMaskedVars__ is not None and isinstance(regdCube.data, numpy.ma.masked_array):
                # yes, it is ma array
                if regdCube.data.mask.all():
                    # Now data is fully masked. So lets fill with user passed value.
                    # And still create ma array
                    regdCube.data = regdCube.data.filled(__fillFullyMaskedVars__)
                    print "filled masked vars", regdCube.data
                    regdCube.data = numpy.ma.masked_array(regdCube.data.filled(__fillFullyMaskedVars__),
                                                         fill_value=9.999e+20) 
                elif regdCube.data.min() == regdCube.data.max():
                    # Both min and max are same value. But its mask is not fully True.
                    # So previous condition not executed, anyhow lets set 
                    # fully the value of fillFullyMaskedVars.
                    print "Both min and max are same. So lets fillFullyMaskedVars as", __fillFullyMaskedVars__ 
                    regdCube.data = numpy.ma.masked_array(regdCube.data.filled(__fillFullyMaskedVars__), 
                                                        fill_value=9.999e+20)
            # end of if __fillFullyMaskedVars__ and ...:
                        
            # get all other dimensions
            # generate list of tuples contain index and coordinate
            dim_coords = [(coord, i) for i,coord in enumerate(list(regdCube.dim_coords))]
            aux_factories = regdCube.aux_factories
            t = regdCube.coords('time')[0]
            fp = regdCube.coords('forecast_period')[0]
            ft = regdCube.coords('forecast_reference_time')[0]
            # create ensemble packed cubes 
            regdData = iris.cube.Cube(regdCube.data, regdCube.standard_name, 
                                     regdCube.long_name, regdCube.var_name,
                                       unit, regdCube.attributes, 
                                           regdCube.cell_methods, dim_coords)
            # add all time coordinates
            regdData.add_aux_coord(fp)
            regdData.add_aux_coord(ft)
            regdData.add_aux_coord(t)
            
#            # add cell_methods to the ensembleData                        
#            if regdCube.cell_methods:
#                if (varName, varSTASH) in _accumulationVars_:
#                    # The following variables cell_methods should show accumulated/sum, but 
#                    # UM pp code doesnt support for accumulation. So lets fix it here ! 
#                    cm = iris.coords.CellMethod('sum', ('time',), 
#                                   intervals=('1 hour',), comments=('6 hour accumulation',))
#                    regdData.cell_methods = (cm)
#                else:             
#                    regdData.cell_methods = (regdCube.cell_methods[0])
            
            print regdData
            # make memory free 
            
            print "regrid done"
            print "after regrid", varName, regdData.data.min(), regdData.data.max() 
            if __LPRINT__: print "To shape", regdData.shape  
                
            regdData.attributes = tmpCube.attributes
            if __LPRINT__: print "set the attributes back to regdData"              
            if __LPRINT__: print "regdData => ", regdData
            # get the regridded lat/lons
            stdNm, stash, fcstTm, refTm, lat1, lon1 = umfcs.getCubeAttr(regdData)
            if __LPRINT__: print "Got attributes from regdData"
            # save the cube in append mode as a grib2 file       
                                    
            if fcstTm.bounds is not None:
                # (need this for pf files)
                if dtype == 'ana':
                    # this is needed for analysis 00th simulated_hr
                    # get the first hour from bounds
                    if __anl_step_hour__ == 3:                        
                        # for 3-hourly ana file, we need to subtract 3 to get
                        # corresponding out hr. 
                        # i.e. 3 means 0. Do not applicable for instantaneous fields.
                        if fhr == 1.5:
                            hr = str(int(fcstTm.bounds[-1][-1]))
                        elif fhr == 4.5:
                            hr = str(int(fcstTm.bounds[-1][0]) - 3)
                    elif __anl_step_hour__ == 6:
                        hr = str(int(fcstTm.bounds[-1][0]))
                elif dtype == 'fcst':
                    # this is needed for forecast 00th simulated_hr
                    # get the last hour from bounds
                    hr = str(int(fcstTm.bounds[-1][-1]))
                if __LPRINT__: print "Bounds comes in ", hr, fcstTm.bounds, fileName                        
            else:
                # get the fcst time point 
                # this is needed for analysis/forecast 00th simulated_hr
                hr = str(int(fcstTm.points))
                if __LPRINT__: print "points comes in ", hr, fileName 
            # end of if fcstTm.bounds:
            
            if dtype == 'ana':
                hr = str(int(hr) + int(_inDataPath_.split('/')[-1]))
              
            # generate the out file name based on actual informations                                 
            outFn = __genAnlFcstOutFileName__(outFileNameStructure, 
                                 outFnIndecies, _current_date_, hr, 
                                           __utc__, _preExtension_) 
            # get the file full name except last extension, for the purpose
            # of writing intermediate nc files
            ofname = outFn.split(fileExtension)[0]                    
            ncfile = False
            if regdData.coords('soil_model_level_number'):
                # NOTE : THIS SECTION WILL WORKS ONLY FOR SOIL MOISTURE AND
                # SOIL TEMPERATUE AT 4 LAYERS, NOT FOR SINGLE LAYER OR 
                # NOT FOR Root zone Soil Moisture Content !!!
                 
                # Get soil_model_level_number coords from the cube.
                # We need to update this variable, which will be replicated
                # in the cube attributes. By default iris-1.9 will not 
                # support to handle soil_model_level_number, so we need to 
                # tweak it by following way.
                depth_below_land_surface = regdData.coords('soil_model_level_number')[0]
                umfcs._updateDepthBelowLandSurfaceCoords4Levs(depth_below_land_surface)
                if __LPRINT__: print "depth_below_land_surface", depth_below_land_surface
                
                if regdData.standard_name == 'moisture_content_of_soil_layer':
                    # pass the vertical layer depth in millimeter
                    umfcs._convert2VolumetricMoisture(regdData, 
                                        levels=[100.0, 250.0, 650.0, 1000.0])
                    print "converted four layer soil moisture to volumetric"
                # end of if regdData.standard_name == 'moisture_content_of_soil_layer':                
                               
            # end of if regdData.coords('soil_model_level_number'):
            
            if (varName, varSTASH) == ('soil_moisture_content', 'm01s08i208'):
                # NOTE : THIS SECTION WILL WORKS ONLY FOR SINGLE LAYERED 
                # Root zone Soil Moisture Content, NOT FOR 4 LAYERS.
                
                # By default this variable doesn't have any vertical coords 
                # inforomation. So we must add explicitly by ourself.
                umfcs._createDepthBelowLandSurfaceCoords1Lev(regdData)
                
                # Convert this into volumetirc soil moisture. This varibale
                # vertical level at 2meter in millimeter.
                umfcs._convert2VolumetricMoisture(regdData, levels=2000.0)
                print "converted single layer soil moisture to volumetric"                
            # end of if (varName, varSTASH) in (...):                       
                        
            try:                
                save_tigge_tweaked_messages([regdData])                
            except Exception as e:
                print "ALERT !!! Error while saving!! %s" % str(e)
                print " So skipping this without saving data"
                continue
            # end of try:
            print "saved"            
            # make memory free 
            del regdCube, tmpCube, regdData
        # end of for fhr in fcstHours:
    # end of for varName, varSTASH in varNamesSTASH:
    # make memory free
    del cubes
    
    print "  Time taken to convert the file: %8.5f seconds \n" %(time.time()-_startT_)
    print " Finished converting file: %s into grib2 format for fcst file: %s \n" %(fileName,hr)
# end of def regridAnlFcstFiles(fname):

def save_tigge_tweaked_messages(cubeList):
    global _ncmrGrib2LocalTableVars_, _aod_pseudo_level_var_,  _opPath_, \
           __setGrib2TableParameters__, __soilFirstSecondFixedSurfaceUnit__, \
           _accumulationVars_, _total_cummulativeVars_
    
    for cube in cubeList:
        for cube, grib_message in iris.fileformats.grib.as_pairs(cube): #save_pairs_from_cube(cube): #
            print "Tweaking begin ", cube.standard_name, cube.long_name
            # post process the GRIB2 message, prior to saving
            gribapi.grib_set_long(grib_message, "centre", 29) # RMC of India
            gribapi.grib_set_long(grib_message, "subCentre", 0) # No subcentre
            print "reset the centre as 29"
            
            # Set the tigge's standard production status of the data 
            # http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_table1-3.shtml   
            # https://software.ecmwf.int/wiki/display/TIGGE/Rules+for+data+encoding+and+exchange
            # 4 for TIGGE-NCMRWF Operational data
            # 5 for TIGGE-NCMRWF Test data
            gribapi.grib_set_long(grib_message, "productionStatusOfProcessedData", 5)
            
            if cube.coords("realization"):
                # ensembles tweak 
                # http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_table4-3.shtml 
                # 4 points ensemble forecast
                gribapi.grib_set_long(grib_message, "typeOfGeneratingProcess", 4)
                if cube.coord("forecast_period").bounds is None:       
                    #http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_table4-0.shtml 
                    # template 01 would be better
                    gribapi.grib_set(grib_message, "productDefinitionTemplateNumber", 1)
                else:
                    # template 11 would be better
                    gribapi.grib_set(grib_message, "productDefinitionTemplateNumber", 11)
                    # if we set bounds[0][0] = 0, wgrib2 gives error for 0 fcst time.
                    # so we need to set proper time intervals 
                    # (typeOfTimeIncrement) as 2 as per below table.
                    # http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_table4-11.shtml
                    # fileformats/grib/_save_rules.py-> set_forecast_time() ->
                    # _non_missing_forecast_period() returns 'fp' as bounds[0][0]. 
                    # but mean while lets fix by setting typeOfTimeIncrement=2.
                    # http://www.cosmo-model.org/content/model/documentation/grib/pdtemplate_4.11.htm 
                    gribapi.grib_set(grib_message, "typeOfTimeIncrement", 2)           
                # end of if cube.coord("forecast_period").bounds is None:          
                # setting ensemble no   
                ensno = int(cube.coord('realization').points[0])                
                gribapi.grib_set(grib_message, "perturbationNumber", ensno)
                # no encoding at present in Iris, set to missing
                gribapi.grib_set(grib_message, "numberOfForecastsInEnsemble", 255)
                if ensno:
                    # http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_table4-6.shtml 
                    # 3 would be better, since we keep on increasing ensmble points 
                    # from 1 to 44
                    gribapi.grib_set(grib_message, "typeOfEnsembleForecast", 3)
                else:
                    # control forecast 
                    # 1 would be better for control run 
                    gribapi.grib_set(grib_message, "typeOfEnsembleForecast", 1)
                # ensembles tweak end
            else:
                # deterministic forecast 
                if cube.coord("forecast_period").bounds is not None:  
                    # if we set bounds[0][0] = 0, wgrib2 gives error for 0 fcst time.
                    # so we need to set proper time intervals 
                    # (typeOfTimeIncrement) as 2 as per below table.
                    # http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_table4-11.shtml
                    # fileformats/grib/_save_rules.py-> set_forecast_time() ->
                    # _non_missing_forecast_period() returns 'fp' as bounds[0][0]. 
                    # but mean while lets fix by setting typeOfTimeIncrement=2.
                    # http://www.cosmo-model.org/content/model/documentation/grib/pdtemplate_4.11.htm 
                    gribapi.grib_set(grib_message, "typeOfTimeIncrement", 2)
            # end of if cube.coord("realization"):
            
            if cube.coords('depth_below_land_surface') or cube.coords('depth'):                
                if __soilFirstSecondFixedSurfaceUnit__ == 'cm':
                    # scaleFactorOfFirstFixedSurface as 2, equivalent to divide
                    # the depth_below_land_surface.points by 100. So that we can 
                    # be sure that grib2 has 0.1m, 0.35m, 1m & 3m. Otherwise, we 
                    # will endup with 0m, 0m, 1m & 3m and finally will loose 
                    # information about decimal values of levels.
                    gribapi.grib_set(grib_message, "scaleFactorOfFirstFixedSurface", 2)
                    gribapi.grib_set(grib_message, "scaleFactorOfSecondFixedSurface", 2)
                    print "reset scaleFactorOfFirstFixedSurface as 2"
                    print "reset scaleFactorOfSecondFixedSurface as 2"
                elif __soilFirstSecondFixedSurfaceUnit__ == 'mm':
                    # scaleFactorOfFirstFixedSurface as 3, equivalent to divide
                    # the depth_below_land_surface.points by 1000. So that we can 
                    # be sure that grib2 has 0.1m, 0.35m, 1m & 3m. Otherwise, we 
                    # will endup with 0m, 0m, 1m & 3m and finally will loose 
                    # information about decimal values of levels.
                    gribapi.grib_set(grib_message, "scaleFactorOfFirstFixedSurface", 3)
                    gribapi.grib_set(grib_message, "scaleFactorOfSecondFixedSurface", 3)
                    print "reset scaleFactorOfFirstFixedSurface as 3"
                    print "reset scaleFactorOfSecondFixedSurface as 3"
                # end of if __soilFirstSecondFixedSurfaceUnit__ == 'cm':
            # end of if cube.coords('depth_below_land_surface'):    
            if cube.standard_name or cube.long_name:
                if cube.standard_name:
                    loc_longname = None
                    if cube.standard_name.startswith('air_pressure_at_sea_level'):
                        # we have to explicitly re-set the type of first fixed
                        # surfcae as Mean sea level (101)
                        gribapi.grib_set(grib_message, "typeOfFirstFixedSurface", 101) 
                    if cube.standard_name.startswith('toa'):
                        # we have to explicitly re-set the type of first surfcae
                        # as Nominal top of the atmosphere i.e. 8 (WMO standard)
                        gribapi.grib_set(grib_message, "typeOfFirstFixedSurface", 8) 
                    # end of if cube.standard_name.startswith('toa'): 
                    if cube.standard_name.startswith('tropopause'):
                        # we have to explicitly re-set the type of first surfcae
                        # as tropopause i.e. 7 (WMO standard)
                        gribapi.grib_set(grib_message, "typeOfFirstFixedSurface", 7) 
                    # end of if cube.standard_name.startswith('tropopause'):                     
                # end of if cube.standard_name:

                if cube.long_name: 
                    aod_name = _aod_pseudo_level_var_.keys()[0]
                    if cube.long_name.startswith(aod_name):
                        # we have to explicitly re-set the type of first surfcae
                        # as surfaced (1) and type of second fixed surface as 
                        # tropopause (7) as per WMO standard, for the aod var.
                        gribapi.grib_set(grib_message, "typeOfFirstFixedSurface", 1)
                        gribapi.grib_set(grib_message, "typeOfSecondFixedSurface", 7) 
                        print "Set typeOfFirstFixedSurface as 1 and typeOfSecondFixedSurface as 7 to aod"
                    # end of if cube.long_name.startswith(aod_name):
                    # check for long name in _ncmrGrib2LocalTableVars_
                    loc_longname = [1 for lname in _ncmrGrib2LocalTableVars_ if cube.long_name.startswith(lname)]                                        
                # end of if cube.long_name: 
                
                if 'cloud' in str(cube.standard_name) or 'cloud' in str(cube.long_name):
                    # we have to explicitly re-set the type of first surfcae
                    # as surfaced (1) and type of second fixed surface as 
                    # as Nominal top of the atmosphere i.e. 8 (WMO standard)
                    gribapi.grib_set(grib_message, "typeOfFirstFixedSurface", 1)
                    gribapi.grib_set(grib_message, "typeOfSecondFixedSurface", 8) 
                # end of if 'cloud' in cube.long_name or 'cloud':
                
                if cube.standard_name in _ncmrGrib2LocalTableVars_ or loc_longname:
                    # We have to enable local table version and disable the 
                    # master table only the special variables.
                    # http://www.cosmo-model.org/content/model/documentation/grib/grib2keys_1.htm 
                    # Above link says that tablesVersion must be set to 255, 
                    # then only local table will be enabled.
                    gribapi.grib_set_long(grib_message, "tablesVersion", 255)
                    # http://apt-browse.org/browse/debian/wheezy/main/i386/libgrib-api-1.9.16/1.9.16-2%2Bb1/file/usr/share/grib_api/definitions/grib2/section.1.def (line no 42)
                    # Above link says versionNumberOfGribLocalTables is alias 
                    # of LocalTablesVersion.        
                    # Set local table version number as 1 as per 
                    # ncmr_grib2_local_table standard.
                    gribapi.grib_set_long(grib_message, "versionNumberOfGribLocalTables", 1)
                # end of if cube.standard_name in _ncmrGrib2LocalTableVars_:
                
                if (cube.standard_name in _total_cummulativeVars_ or \
                    cube.long_name in _total_cummulativeVars_):
                    gribapi.grib_set(grib_message, "typeOfStatisticalProcessing", 1)
            # end of if cube.standard_name or ...:
                        
            if __setGrib2TableParameters__:
                # This user defined parameters must be at last of this function!
                for key, val in __setGrib2TableParameters__:
                    gribapi.grib_set_long(grib_message, key, val)
                    print "set user defined grib2table parameter ('%s', %s)" % (key, val)
            # end of if __setGrib2TableParameters__:
            print "Tweaking end ", cube.standard_name
                        
            # get tigge statndard filename 
            outgname, sname = getTiggeFileName(cube)
            outgdir = os.path.join(_opPath_, sname)
            createDirWhileParallelRacing(outgdir)
            outgpath = os.path.join(outgdir, outgname) # Join the outpath 
            print "lets save into", outgpath
            cstash = str(cube.attributes.get('STASH', 'None'))
            if (cube.standard_name, cstash) in _accumulationVars_:
                iris.fileformats.netcdf.save(cube, outgpath+'.nc')  # save nc file 
            else:
                # finally save the cube/message into many individual grib2 files
                iris.fileformats.grib.save_messages([grib_message], outgpath)

        # end of for cube, grib_message in iris.fileformats.grib.as_pairs(cube):
    # end of for cube in cubeList:
# end of def save_tigge_tweaked_messages(cube):

def makeTotalCummulativeVars(arg):
    
    global _opPath_, _current_date_, __start_long_fcst_hour__, __end_long_fcst_hour__  
    
    svar, sname, umfcstype, ens = arg 

    if svar == 'tp':
        lname = 'time_cummulated_precipitation'
        rstash = True
    else:
        lname = 'time_integrated_' + sname 
        rstash = False
    
    fname = 'z_tigge_c_dems_' +_current_date_+ '000000_glob_test_'  # TIGGE TEST 
    fname += umfcstype+ '_sl_%s_' + ens.zfill(3) + '_0000_' + svar + '.nc' 
    infiles = [os.path.join(*[_opPath_, svar, fname % str(t).zfill(4)]) 
                        for t in range(6, __end_long_fcst_hour__+1, 6)]

    try:
        cubes = iris.load(infiles)[0]
    except Exception as e:
        raise ValueError("Unable to load files from %s - while makeTotalCummulativeVars" % str(infiles))
    
    # get the cummulated cubes generator
    outcubes = cubeCummulator(cubes, standard_name='None', long_name=lname, 
                                addZerosFirstCube=True, removeSTASH=rstash)

    # save cummulated cubes into individual grib2 files
    for cube in outcubes: save_tigge_tweaked_messages([cube])        
    
    cmd = 'rm -rf ' + ' '.join(infiles)
    subprocess.call(cmd, shell=True)
# end of def makeTotalCummulativeVars():
    
# Start definition #6
def doFcstConvert(fname):
    """
    New Module by AAT:
    This module has been rewritten entirely by AAT for optimization as an embarassingly-
    parallel problem! This module acts as the main program to feed the filenames as a
    child process to a multiprocessing thread as a daemon process.
    :param fname: Name of the FF filename in question as a "string"
    :return: Nothing! TANGIBLE!
    """
    global __start_long_fcst_hour__, __end_long_fcst_hour__, __UMtype__
    
    
    if __UMtype__ == 'global':
        # calculate start hour of long fcst in multiples of 24. Why?
        # 00 hr contains from 06 to 24 hours data.
        # 24 hr contains from 24 to 48 hours data, and so on.
        start_fcst_hour = ((__start_long_fcst_hour__ / 24) - 1) * 24
        # Here we are reducing one 24 because, 00 file contains upto 24 hour,
        # and 24 hour files contains upto 48 hour and so on.
            
        # here max fcst hours goes upto 240 only, not 241. why ??
        # because 216 long fcst hours contains upto 240th hour fcst.
        # and 240th long fcst contains upto 264th hour fcst.
        # so here no need to add +1 to __end_long_fcst_hour__.
        fcst_times = [str(hr).zfill(3) for hr in range(start_fcst_hour, __end_long_fcst_hour__, 24)]
        
    elif __UMtype__ == 'regional':
        fcst_times = [str(hr).zfill(2) for hr in range(0, __end_long_fcst_hour__, 6)]
    # end of if __UMtype__ == 'global':
    
    fcst_filenames = [(fname, hr) for hr in fcst_times]
    nchild = len(fcst_times)
    if not nchild: raise ValueError("Got 0 fcst_times, couldn't make parallel !")
    # create the no of child parallel processes
    inner_pool = mp.Pool(processes=nchild)
    print "Creating %i (daemon) workers and jobs in child." % nchild
    
    # pass the forecast hours as argument to take one fcst file per process / core to regrid it.
    results = inner_pool.map(regridAnlFcstFiles, fcst_filenames)
    # closing and joining child pools      
    inner_pool.close() 
    inner_pool.join()
    # parallel end
# end def doFcstConvert(fname):


def doAnlConvert(fname):
    """
    New Module by AAT:
    This module has been rewritten entirely by AAT for optimization as an embarassingly-
    parallel problem! This module acts as the main program to feed the filenames as a
    child process to a multiprocessing thread as a daemon process.
    :param fname: Name of the FF filename in question as a "string"
    :return: Nothing! TANGIBLE!
    """
    
    regridAnlFcstFiles((fname, '000'))  
# end def doAnlConvert(fname):


# Start the convertFilesInParallel function
def convertFilesInParallel(fnames, ftype):
    """
    convertFilesInParallel function calling all the sub-functions
    :param fnames: a simple filename as argument in a string format
    :return: THE SheBang!
    """
    
    global _startT_, _tmpDir_, _opPath_
    
    ## get the no of files and 
    nprocesses = len(fnames)
    if not nprocesses: raise ValueError("Got 0 fnames, couldn't make parallel !")
    # lets create no of parallel process w.r.t no of files.

    # parallel begin - 1 
    pool = _MyPool(nprocesses)
    print "Creating %d (non-daemon) workers and jobs in convertFilesInParallel process." % nprocesses
    
    if ftype in ['anl', 'analysis']:
        results = pool.map(doAnlConvert, fnames)
    elif ftype in ['fcst', 'forecast']:
        results = pool.map(doFcstConvert, fnames)
    else:
        raise ValueError("Unknown file type !")
    # end of if ftype in ['anl', 'analysis']:    

    # closing and joining master pools
    pool.close()     
    pool.join()
    # parallel end - 1 
    
    print "Total time taken to convert %d files was: %8.5f seconds \n" %(len(fnames),(time.time()-_startT_))
    
    return
# end of def convertFilesInParallel(fnames):

def _checkInFilesStatus(path, ftype, pfnames):
    
    global __start_long_fcst_hour__, __end_long_fcst_hour__, __UMtype__
    
    if ftype in ['ana', 'anl']:
        fhrs = ['000'] 
    elif ftype in ['fcst', 'prg']:
        if __UMtype__ == 'global':
            # calculate start hour of long fcst in multiples of 24. Why?
            # 00 hr contains from 06 to 24 hours data.
            # 24 hr contains from 24 to 48 hours data, and so on.
            start_fcst_hour = (__start_long_fcst_hour__ / 24) * 24

            # here max fcst hours goes upto 240 only, not 241. why ??
            # because 216 long fcst hours contains upto 240th hour fcst.
            # and 240th long fcst contains upto 264th hour fcst.
            # so here no need to add +1 to __end_long_fcst_hour__.
            fhrs = [str(hr).zfill(3) for hr in range(start_fcst_hour, __end_long_fcst_hour__, 24)]
        elif __UMtype__ == 'regional':
            fhrs = [str(hr).zfill(2) for hr in range(6, __end_long_fcst_hour__, 6)]
        elif __UMtype__ == 'ensemble':
            fhrs = [str(hr).zfill(3) for hr in range(0, __end_long_fcst_hour__, 6)]
            
        # end of if __UMtype__ == 'global':
    # end of if ftype in ['ana', 'anl']:
    print fhrs
    fileNotExistList = []
    for pfname in pfnames:
        for fhr in fhrs:
            # constrct the correct fileName from partial fileName and hours
            # add hour only if doenst have any extension on partial filename.
            if __UMtype__ == 'global':
                fname = pfname if '.' in pfname else pfname + fhr
            elif __UMtype__ == 'regional':
                # generate filenames like 'umnsaa_pb000', 'umnsaa_pb006', etc
                fname = pfname if '.' in pfname else pfname + fhr.zfill(3)  
            elif __UMtype__ == 'ensemble':
                fname = pfname if '.' in pfname else pfname + fhr              
            # end of if __UMtype__ == 'global':
            fpath = os.path.join(path, fname)
            if not os.path.isfile(fpath): fileNotExistList.append(fpath)
    # end of for pfname in pfnames:
    status = False if fileNotExistList else True
    if status is False:    
        print "The following infiles are not exists!\n"
        print "*" * 80
        print "\n".join(fileNotExistList)
        print "*" * 80
        
    return status
# end of def _checkInFilesStatus(path, ftype, pfnames):

def _checkOutFilesStatus(path, ftype, date, utc, overwrite):
    
    global _preExtension_, __end_long_fcst_hour__, __anlFileNameStructure__,\
           __fcstFileNameStructure__, __fcst_step_hour__, \
           __anl_step_hour__, __utc__, __start_long_fcst_hour__
           
    if ftype in ['ana', 'anl']:
        outFileNameStructure = __anlFileNameStructure__
        fhrs = [utc] # ana_hour (short forecast hour) is same as simulated_hr (i.e. utc)
        simulated_hr = int(__utc__)
        # since ncum producing analysis files 00, 06, 12, 18 utc cycles and 
        # its forecast time starting from 0 and reference time based on utc.
        # so we should calculate correct hour as below.
        fhrs = range(0+simulated_hr, 6+simulated_hr, __anl_step_hour__)     
    elif ftype in ['fcst', 'prg']:
        outFileNameStructure = __fcstFileNameStructure__
        fhrs = range(__start_long_fcst_hour__, __end_long_fcst_hour__+1, 
                                                     __fcst_step_hour__)
    
    # get the out fileName Structure based on pre / user defined indecies
    outFnIndecies = __getAnlFcstFileNameIndecies__(outFileNameStructure)
    status = None
    for fhr in fhrs:
        # generate the out file name based on actual informations.
        # here preExtension is empty string to create final needed out file name                        
        fname = __genAnlFcstOutFileName__(outFileNameStructure, outFnIndecies,  
                                                               date, fhr, utc)
        fpath = os.path.join(path, fname)        
        for ext in ['', '.ctl', '.idx']:
            fpath = os.path.join(path, fname+ext)
            if os.path.isfile(fpath):
                print "Out File already exists", fpath,
                if overwrite: 
                    os.remove(fpath)
                    status = 'FilesRemoved'
                    print ", but overwrite option is True. So removed it!"
                else:
                    status = 'FilesExist' 
            else:
                print "\nOut File does not exists", fpath 
                if status in [None, 'FilesRemoved']:
                    status = 'FilesDoNotExist' 
                    continue
                elif status is 'FilesExist':
                    status = 'PartialFilesExist'
                    break
        # end of for ext in ['', '.ctl', '.idx']:
    # end of for fhr in fhrs:
    
    ifiles = [fname for fname in os.listdir(path) if _preExtension_ in fname]
    if ifiles:        
        print "Intermediate files are exists in the outdirectory.", path
        for ifile in ifiles:        
            if outFileNameStructure[0] in ifile and utc in ifile and _preExtension_ in ifile:
                os.remove(os.path.join(path, ifile))
                status = 'IntermediateFilesExist'
                print "removed intermediate nc file"                
        # end of for ncfile in ncfiles:        
    # end of if ncfiles:
    if status in ['PartialFilesExist', 'IntermediateFilesExist']:
        # partial files exist, so make overwrite option as True and do 
        # recursive call one time to remove all output files.
        print "Partial/Intermediate out files exist, so going to overwrite all files"
        return _checkOutFilesStatus(path, ftype, date, utc, overwrite=True)
    else:
        return status
# end of def _checkOutFilesStatus(path, ftype, date, hr, overwrite):
            
def convertFcstFiles(inPath, outPath, tmpPath, **kwarg):
           
    global _targetGrid_, _targetGridRes_, _current_date_, _startT_, _tmpDir_, \
       _inDataPath_, _opPath_, _doRegrid_, _convertVars_, _requiredLat_, \
       _requiredLon_, _createGrib2CtlIdxFiles_, _createGrib1CtlIdxFiles_, \
       _convertGrib2FilestoGrib1Files_, __fcstFileNameStructure__, \
       __LPRINT__, __utc__, __fcst_step_hour__, _reverseLatitude_, \
       __end_long_fcst_hour__, __outFileType__, __grib1FilesNameSuffix__, \
       __removeGrib2FilesAfterGrib1FilesCreated__, _depedendantVars_, \
       _removeVars_, _requiredPressureLevels_, __setGrib2TableParameters__, \
       __wgrib2Arguments__, __soilFirstSecondFixedSurfaceUnit__,  __UMtype__, \
       __start_long_fcst_hour__, _extraPolateMethod_, _targetGridFile_, \
       __fillFullyMaskedVars__
     
    # load key word arguments
    UMtype = kwarg.get('UMtype', 'global')    
    UMInLongFcstFiles = kwarg.get('UMInLongFcstFiles', None)
    targetGridResolution = kwarg.get('targetGridResolution', 0.25)
    targetGridFile = kwarg.get('targetGridFile', '')
    date = kwarg.get('date', time.strftime('%Y%m%d'))
    utc = kwarg.get('utc', '00')
    overwrite = kwarg.get('overwrite', False)
    lprint = kwarg.get('lprint', False)
    convertVars = kwarg.get('convertVars', None)
    latitude = kwarg.get('latitude', None)
    longitude = kwarg.get('longitude', None)
    pressureLevels = kwarg.get('pressureLevels', None)
    fillFullyMaskedVars = kwarg.get('fillFullyMaskedVars', None)
    extraPolateMethod = kwarg.get('extraPolateMethod', 'auto')
    soilFirstSecondFixedSurfaceUnit = kwarg.get('soilFirstSecondFixedSurfaceUnit', 'cm')
    fcst_step_hour = kwarg.get('fcst_step_hour', 6)
    start_long_fcst_hour = kwarg.get('start_long_fcst_hour', 6)
    end_long_fcst_hour = kwarg.get('end_long_fcst_hour', 240)
    fcstFileNameStructure = kwarg.get('fcstFileNameStructure', None)
    createGrib2CtlIdxFiles = kwarg.get('createGrib2CtlIdxFiles', True)
    createGrib1CtlIdxFiles = kwarg.get('createGrib1CtlIdxFiles', False)
    convertGrib2FilestoGrib1Files = kwarg.get('convertGrib2FilestoGrib1Files', False)
    grib1FilesNameSuffix = kwarg.get('grib1FilesNameSuffix', '1')
    removeGrib2FilesAfterGrib1FilesCreated = kwarg.get('removeGrib2FilesAfterGrib1FilesCreated', False)
    setGrib2TableParameters = kwarg.get('setGrib2TableParameters', None)
    wgrib2Arguments = kwarg.get('wgrib2Arguments', None)
    callBackScript = kwarg.get('callBackScript', None)
    
    
    # assign out file type in global variable
    __outFileType__ = 'fcst'
    # assign the convert vars list of tuples to global variable
    if convertVars: _convertVars_ = convertVars
    # assign the analysis file name structure
    if fcstFileNameStructure: __fcstFileNameStructure__ = fcstFileNameStructure
    # set print variables details options
    __LPRINT__ = lprint    
    # update global variables
    __UMtype__ = UMtype
    __utc__ = utc
    __fcst_step_hour__ = fcst_step_hour
    __start_long_fcst_hour__ = start_long_fcst_hour
    __end_long_fcst_hour__ = end_long_fcst_hour
    __removeGrib2FilesAfterGrib1FilesCreated__ = removeGrib2FilesAfterGrib1FilesCreated
    __grib1FilesNameSuffix__ = grib1FilesNameSuffix
    _targetGridRes_ = str(targetGridResolution)
    _targetGridFile_ = targetGridFile
    _extraPolateMethod_ = extraPolateMethod      
    _requiredPressureLevels_ = pressureLevels    
    __fillFullyMaskedVars__ = fillFullyMaskedVars
    __soilFirstSecondFixedSurfaceUnit__ = soilFirstSecondFixedSurfaceUnit
    _createGrib2CtlIdxFiles_ = createGrib2CtlIdxFiles
    _createGrib1CtlIdxFiles_ = createGrib1CtlIdxFiles
    _convertGrib2FilestoGrib1Files_ = convertGrib2FilestoGrib1Files
    __setGrib2TableParameters__ = setGrib2TableParameters
    __wgrib2Arguments__ = wgrib2Arguments
    # forecast filenames partial name
    if __UMtype__ == 'global':
        # pass user passed long forecast global model infiles otherwise pass proper infiles.
        fcst_fnames = UMInLongFcstFiles if UMInLongFcstFiles else ['umglaa_pb','umglaa_pd', 'umglaa_pe', 'umglaa_pf', 'umglaa_pi']
    elif __UMtype__ == 'regional':
        # pass user passed long forecast regional model infiles otherwise pass proper infiles.
        fcst_fnames = UMInLongFcstFiles if UMInLongFcstFiles else ['umnsaa_pb','umnsaa_pd', 'umnsaa_pe', 'umnsaa_pf', 'umnsaa_pi']
    # end of if __UMtype__ == 'global':
    
    # get the current date in YYYYMMDD format
    _tmpDir_ = tmpPath
    _current_date_ = date
    print "\n _current_date_ is %s" % _current_date_
    logpath = os.path.join(_tmpDir_, _current_date_)
    createDirWhileParallelRacing(logpath)
    logfile = 'um2grb2_fcst_stdout_'+ _current_date_ +'_' + utc +'Z.log'
    sys.stdout = myLog(os.path.join(logpath, logfile))
    
    # start the timer now
    _startT_ = time.time()

    # set-up base folders    
    _inDataPath_ = os.path.join(inPath, _current_date_, utc)
    if not os.path.exists(_inDataPath_):
        raise ValueError("In datapath does not exists %s" % _inDataPath_)
    # end of if not os.path.exists(_inDataPath_):
    
    if convertVars:
        # check either depedendant vars are need to be loaded 
        for var, dvars in _depedendantVars_.iteritems():
            if var in convertVars:
                for dvar in dvars:
                    if dvar not in convertVars:               
                        _convertVars_.append(dvar)  # include depedendant var
                        _removeVars_.append(dvar)   # remove depedendant var at last
        # end of for var, dvar in _depedendantVars_.iteritems():
                
        # load only required file names to avoid unnneccessary computations
        # by cross checking with user defined variables list.
        for fpname in fcst_fnames[:]:   
            # loop through copy of fcst_fnames[:], because fcst_fnames list 
            # will may change within this loop.
            hr = utc.zfill(3)
            ### if fileName has some extension, then do not add hr to it.
            fileName = fpname + hr if not '.' in fpname else fpname
            varNamesSTASH, _, _, _, _ = umfcs.getVarInOutFilesDetails(_inDataPath_, fileName, hr)
            # check either user requires this file or not!
            if not set(varNamesSTASH).intersection(convertVars):
                # remove the fpname from fcst_fnames, because user didn't 
                # require variabels from this fpname file.
                fcst_fnames.remove(fpname)
                print "removed %s from list of files" % fpname             
    # end of if convertVars:    
    print "Final fpname list :", fcst_fnames
    # check either infiles are exist or not!
    status = _checkInFilesStatus(_inDataPath_, 'prg', fcst_fnames)
    print "in status+++++++++++++++++++++++++++", status
    if not status:
        raise ValueError("In datapath does not contain the above valid infiles")
    # end of if not instatus:
    
    _opPath_ = os.path.join(outPath, _current_date_)
    createDirWhileParallelRacing(_opPath_)
    
    # define default global lat start, lon end points
    slat, elat = (-90., 90.)
    # define default global lon start, lon end points 
    slon, elon = (0., 360.)
    # define user defined custom lat & lon start and end points
    if latitude: 
        (slat, elat) = latitude        
        if slat > elat:
            # just make sure while extracting south to north
            slat, elat = elat, slat            
            # and reverse while saving into grib2 file.
            _reverseLatitude_ = True
        # end of if slat > elat:
        _requiredLat_ = (slat, elat)
    # end of if latitude: 
    
    if os.path.isfile(_targetGridFile_):
        # load target grid from user specfied file and make it as target grid.
        _targetGrid_ = iris.load(_targetGridFile_)[0]
        _doRegrid_ = True   
    elif targetGridResolution is None:
        _doRegrid_ = False
        if longitude: (slon, elon) = longitude
        # reduce one step if user passed / default lon is 360. If we write 
        # longitude from 0 upto 360, wgrib2 reads it as 0 to 0. To avoid it, 
        # just reduct one small step in longitude only incase of 360.
        if int(elon) == 360: elon -= 0.0001
        if longitude: _requiredLon_ = (slon, elon)
    else:
        if not isinstance(targetGridResolution, (int, float)):
            raise ValueError("targetGridResolution must be either int or float")        
        if longitude: (slon, elon) = longitude
        # reduce one step if user passed / default lon is 360. If we write 
        # longitude from 0 upto 360, wgrib2 reads it as 0 to 0. To avoid it, 
        # just reduct one step in longitude only incase of 360.
        if int(elon) == 360: elon -= targetGridResolution 
        if longitude: _requiredLon_ = (slon, elon)
        # target grid as 0.25 deg (default) resolution by setting up sample points 
        # based on coord
        # generate lat, lon values
        latpoints = numpy.arange(slat, elat+targetGridResolution, targetGridResolution)
        lonpoints = numpy.arange(slon, elon+targetGridResolution, targetGridResolution)
        # correct lat, lon end points 
        if latpoints[-1] > elat: latpoints = latpoints[:-1]
        if lonpoints[-1] > elon: lonpoints = lonpoints[:-1]
        # set target grid lat, lon values pair                   
        _targetGrid_ = [('latitude', latpoints), ('longitude', lonpoints)]
        _doRegrid_ = True        
    # end of iif os.path.isfile(_targetGridFile_):
    
    # check either files are exists or not. delete the existing files in case
    # of overwrite option is True, else return without re-converting files.
    status = _checkOutFilesStatus(_opPath_, 'prg', _current_date_, utc, overwrite)
    if status is 'FilesExist': 
        print "All files are already exists. So skipping convert Fcst files porcess"
        return # return back without executing conversion process.
    elif status in [None, 'FilesDoNotExist', 'FilesRemoved']:
        print "Going to start convert Fcst files freshly"
    # end of if status is 'FilesExists': 
    
    # do convert for forecast files 
    convertFilesInParallel(fcst_fnames, ftype='fcst')   
    
    time.sleep(30)  
    
    # make total time cummulated variables    
    for (TCV, TCVS, TCSVAR) in [('surface_net_downward_shortwave_flux', 'm01s01i202', 'ssr'),
                        ('surface_net_downward_longwave_flux', 'm01s02i201', 'str'), 
                        ('surface_upward_latent_heat_flux', 'm01s03i234', 'slhf'),   
                        ('surface_upward_sensible_heat_flux', 'm01s03i217', 'sshf'),   
                        ('toa_outgoing_longwave_flux', 'm01s02i205', 'ttr'),
                        ('precipitation_amount', 'm01s05i226', 'tp')]:
        if (TCV, TCVS) in convertVars: makeTotalCummulativeVars((TCSVAR, TCV, 'fc', '000'))
    # end of for (TCV, TCVS, TCSVAR) ...:
    
    if callBackScript:
        time.sleep(30)  # required few seconds sleep before further process starts  
        callBackScript = os.path.abspath(callBackScript)
        if not os.path.exists(callBackScript): 
            print "callBackScript '%s' doenst exist" % callBackScript
            return 
        kwargs = ' --date=%s --outpath=%s --oftype=forecast --utc=%s' % (_current_date_, _opPath_, utc)
        scriptExecuteCmd = callBackScript + ' ' + kwargs
        # execute user defined call back script with keyword arguments
        subprocess.call(scriptExecuteCmd, shell=True)
    # end of if callBackScript:
# end of def convertFcstFiles(...):


def convertAnlFiles(inPath, outPath, tmpPath, **kwarg):
       
    global _targetGrid_, _targetGridRes_, _current_date_, _startT_, _tmpDir_, \
       _inDataPath_, _opPath_, _doRegrid_, _convertVars_, _requiredLat_, \
       _requiredLon_, _createGrib2CtlIdxFiles_, _createGrib1CtlIdxFiles_, \
       _convertGrib2FilestoGrib1Files_, __anlFileNameStructure__,  \
       __LPRINT__, __utc__, __outFileType__, __grib1FilesNameSuffix__, \
       __removeGrib2FilesAfterGrib1FilesCreated__, _depedendantVars_, \
       _removeVars_, __anl_step_hour__, _requiredPressureLevels_, \
       __setGrib2TableParameters__, __anl_aavars_reference_time__, \
       __anl_aavars_time_bounds__, _reverseLatitude_, __wgrib2Arguments__, \
       __soilFirstSecondFixedSurfaceUnit__, _extraPolateMethod_, _targetGridFile_, \
       __UMtype__, __fillFullyMaskedVars__  
           
    # load key word arguments
    UMtype = kwarg.get('UMtype', 'global')
    UMInAnlFiles = kwarg.get('UMInAnlFiles', None)
    UMInShortFcstFiles = kwarg.get('UMInShortFcstFiles', None)
    targetGridResolution = kwarg.get('targetGridResolution', 0.25)
    targetGridFile = kwarg.get('targetGridFile', '')
    date = kwarg.get('date', time.strftime('%Y%m%d'))
    utc = kwarg.get('utc', '00')
    overwrite = kwarg.get('overwrite', False)
    lprint = kwarg.get('lprint', False)
    convertVars = kwarg.get('convertVars', None)
    latitude = kwarg.get('latitude', None)
    longitude = kwarg.get('longitude', None)
    pressureLevels = kwarg.get('pressureLevels', None)
    fillFullyMaskedVars = kwarg.get('fillFullyMaskedVars', None)
    extraPolateMethod = kwarg.get('extraPolateMethod', 'auto')
    soilFirstSecondFixedSurfaceUnit = kwarg.get('soilFirstSecondFixedSurfaceUnit', 'cm')
    anl_step_hour = kwarg.get('anl_step_hour', 6)
    anl_aavars_reference_time = kwarg.get('anl_aavars_reference_time', 'shortforecast')
    anl_aavars_time_bounds = kwarg.get('anl_aavars_time_bounds', True)
    anlFileNameStructure = kwarg.get('anlFileNameStructure', None)    
    createGrib2CtlIdxFiles = kwarg.get('createGrib2CtlIdxFiles', True)
    createGrib1CtlIdxFiles = kwarg.get('createGrib1CtlIdxFiles', False)
    convertGrib2FilestoGrib1Files = kwarg.get('convertGrib2FilestoGrib1Files', False)
    grib1FilesNameSuffix = kwarg.get('grib1FilesNameSuffix', '1')
    removeGrib2FilesAfterGrib1FilesCreated = kwarg.get('removeGrib2FilesAfterGrib1FilesCreated', False)
    setGrib2TableParameters = kwarg.get('setGrib2TableParameters', None)
    wgrib2Arguments = kwarg.get('wgrib2Arguments', None)
    callBackScript = kwarg.get('callBackScript', None)
        
    # assign out file type in global variable
    __outFileType__ = 'ana'
    # assign the convert vars list of tuples to global variable
    if convertVars: _convertVars_ = convertVars
    # assign the analysis file name structure
    if anlFileNameStructure: __anlFileNameStructure__ = anlFileNameStructure
    # set print variables details options
    __LPRINT__ = lprint
    # update global variables
    __UMtype__ = UMtype
    __utc__ = utc
    __anl_step_hour__ = anl_step_hour
    __anl_aavars_reference_time__ = anl_aavars_reference_time
    __anl_aavars_time_bounds__ = anl_aavars_time_bounds
    __removeGrib2FilesAfterGrib1FilesCreated__ = removeGrib2FilesAfterGrib1FilesCreated
    __grib1FilesNameSuffix__ = grib1FilesNameSuffix
    _targetGridRes_ = str(targetGridResolution)
    _targetGridFile_ = targetGridFile
    _extraPolateMethod_ = extraPolateMethod  
    _requiredPressureLevels_ = pressureLevels    
    __fillFullyMaskedVars__ = fillFullyMaskedVars
    __soilFirstSecondFixedSurfaceUnit__ = soilFirstSecondFixedSurfaceUnit
    _createGrib2CtlIdxFiles_ = createGrib2CtlIdxFiles
    _createGrib1CtlIdxFiles_ = createGrib1CtlIdxFiles
    _convertGrib2FilestoGrib1Files_ = convertGrib2FilestoGrib1Files
    __setGrib2TableParameters__ = setGrib2TableParameters
    __wgrib2Arguments__ = wgrib2Arguments
    # analysis filenames partial name
    if __UMtype__ == 'global':
        # pass user passed short forecast in files otherwise pass proper infiles.
        anl_fnames = UMInShortFcstFiles if UMInShortFcstFiles else ['umglca_pb', 'umglca_pd', 'umglca_pe', 'umglca_pf', 'umglca_pi']
        if utc == '00':
            # pass user passed analysis in files valid for 00UTC otherwise pass proper infile.
            anl_fnames = UMInAnlFiles + anl_fnames if UMInAnlFiles else anl_fnames.insert(0, 'qwqg00.pp0')
    # end of if __UMtype__ == 'global':
    
    # get the current date in YYYYMMDD format
    _tmpDir_ = tmpPath
    _current_date_ = date
    print "\n _current_date_ is %s" % _current_date_
    logpath = os.path.join(_tmpDir_, _current_date_)
    createDirWhileParallelRacing(logpath)
    logfile = 'um2grb2_anal_stdout_'+ _current_date_ +'_' + utc +'Z.log'
    sys.stdout = myLog(os.path.join(logpath, logfile))
    
    # start the timer now
    _startT_ = time.time()

    # set-up base folders
    _inDataPath_ = os.path.join(inPath, _current_date_, utc)
    if not os.path.exists(_inDataPath_):
        raise ValueError("In datapath does not exists %s" % _inDataPath_)
    # end of if not os.path.exists(_inDataPath_):
    
    if convertVars:
        # check either depedendant vars are need to be loaded 
        for var, dvars in _depedendantVars_.iteritems():
            if var in convertVars:
                for dvar in dvars:
                    if dvar not in convertVars:                 
                        _convertVars_.append(dvar)  # include depedendant var
                        _removeVars_.append(dvar)   # remove depedendant var at last
        # end of for var, dvar in _depedendantVars_.iteritems():
        
        # load only required file names to avoid unnneccessary computations
        # by cross checking with user defined variables list.
        for fpname in anl_fnames[:]:
            # loop through copy of fcst_fnames[:], because fcst_fnames list 
            # will may change within this loop.
            hr = utc.zfill(3)
            ### if fileName has some extension, then do not add hr to it.
            fileName = fpname + hr if not '.' in fpname else fpname
            varNamesSTASH, _, _, _, _ = umfcs.getVarInOutFilesDetails(_inDataPath_, fileName, hr)
            # check either user requires this file or not!
            if not set(varNamesSTASH).intersection(convertVars):
                # remove the fpname from fcst_fnames, because user didn't 
                # require variabels from this fpname file.
                anl_fnames.remove(fpname)
                print "removed %s from list of files" % fpname            
    # end of if convertVars:    
    print "Final fpname list :", anl_fnames    
    # check either infiles are exist or not!
    status = _checkInFilesStatus(_inDataPath_, 'ana', anl_fnames)
    if not status:
        raise ValueError("In datapath does not contain the above valid infiles")
    # end of if not instatus:
    
    _opPath_ = os.path.join(outPath, _current_date_)
    createDirWhileParallelRacing(_opPath_)
    
    # define default global lat start, lon end points
    slat, elat = (-90., 90.)
    # define default global lon start, lon end points 
    slon, elon = (0., 360.)
    # define user defined custom lat & lon start and end points
    if latitude: 
        (slat, elat) = latitude
        if slat > elat:
            # just make sure while extracting south to north
            slat, elat = elat, slat            
            # and reverse while saving into grib2 file.
            _reverseLatitude_ = True
        # end of if slat > elat:
        _requiredLat_ = (slat, elat)
    # end of if latitude: 
    
    if os.path.isfile(_targetGridFile_):
        # load target grid from user specfied file and make it as target grid.
        _targetGrid_ = iris.load(_targetGridFile_)[0]
        _doRegrid_ = True
    elif targetGridResolution is None:
        _doRegrid_ = False  
        if longitude: (slon, elon) = longitude
        # reduce one step if user passed / default lon is 360. If we write 
        # longitude from 0 upto 360, wgrib2 reads it as 0 to 0. To avoid it, 
        # just reduct one small step in longitude only incase of 360.
        if int(elon) == 360: elon -= 0.0001
        if longitude: _requiredLon_ = (slon, elon)
    else:
        if not isinstance(targetGridResolution, (int, float)):
            raise ValueError("targetGridResolution must be either int or float")        
        if longitude: (slon, elon) = longitude
        # reduce one step if user passed / default lon is 360. If we write 
        # longitude from 0 upto 360, wgrib2 reads it as 0 to 0. To avoid it, 
        # just reduct one step in longitude only incase of 360.
        if int(elon) == 360: elon -= targetGridResolution
        if longitude: _requiredLon_ = (slon, elon)
        # target grid as 0.25 deg (default) resolution by setting up sample points 
        # based on coord    
        # generate lat, lon values
        latpoints = numpy.arange(slat, elat+targetGridResolution, targetGridResolution)
        lonpoints = numpy.arange(slon, elon+targetGridResolution, targetGridResolution)
        # correct lat, lon end points 
        if latpoints[-1] > elat: latpoints = latpoints[:-1]
        if lonpoints[-1] > elon: lonpoints = lonpoints[:-1]
        # set target grid lat, lon values pair                   
        _targetGrid_ = [('latitude', latpoints), ('longitude', lonpoints)]
        _doRegrid_ = True  
    # end of if os.path.isfile(_targetGridFile_):
    print "_reverseLatitude_ =", _reverseLatitude_ 
    # check either files are exists or not. delete the existing files in case
    # of overwrite option is True, else return without re-converting files.
    status = _checkOutFilesStatus(_opPath_, 'ana', _current_date_, utc, overwrite)
    if status is 'FilesExist': 
        print "All files are already exists. So skipping convert Anl files porcess"
        return # return back without executing conversion process.
    elif status in [None, 'FilesDoNotExist', 'FilesRemoved']:
        print "Going to start convert Anl files freshly"
    # end of if status is 'FilesExists': 
                   
    # do convert for analysis files
    convertFilesInParallel(anl_fnames, ftype='anl')   
        
    if callBackScript:
        time.sleep(30)  # required few seconds sleep before further process starts  
        callBackScript = os.path.abspath(callBackScript)
        if not os.path.exists(callBackScript): 
            print "callBackScript '%s' doenst exist" % callBackScript
            return 
        kwargs = ' --date=%s --outpath=%s --oftype=analysis --utc=%s' % (_current_date_, _opPath_, utc)
        scriptExecuteCmd = callBackScript + ' ' + kwargs
        # execute user defined call back script with keyword arguments
        subprocess.call(scriptExecuteCmd, shell=True)
    # end of if callBackScript:
# end of def convertAnlFiles(...):

#################################### EPS STUFF ###############################
def packEnsembles(arg, **kwarg):
    
    global _targetGrid_, _targetGridRes_,  _startT_, _inDataPath_, _opPath_, \
            _preExtension_, _ncfilesVars_, _requiredLat_, _requiredLon_, \
            _doRegrid_, __utc__, _requiredPressureLevels_, __LPRINT__, \
            __outg2files__, _lock_, _accumulationVars_, __fcst_step_hour__, \
            _targetGridFile_, _extraPolateMethod_, _current_date_, \
             _reverseLatitude_, _precipVars_, _maskOverOceanVars_, __end_long_fcst_hour__

   
    
    infiles, varNamesSTASHFcstHour = arg
    varName, varSTASH, fhr = varNamesSTASHFcstHour
    # update function for tweaking grib messages
    
    if (varName, varSTASH) in _accumulationVars_:
        # update the forecast hour, since precipitation_amount is accumulated
        # var, not instantaneous one.        
        fhr = fhr-3 if fhr else fhr+3
    # end of if (varName, varSTASH) in [('precipitation_amount', 'm01s05i226')]:
    
    simulated_hr = __utc__
    # define variable name constraint
    varConstraint = iris.Constraint(name=varName)
    # define varibale stash code constraint
    STASHConstraint = iris.AttributeConstraint(STASH=varSTASH)    
    # 
    forecast_period_constraint = iris.Constraint(forecast_period=fhr)            
     # define (simulated_hr) forecast_reference_time constraint
    fcstRefTimeConstraint = iris.Constraint(forecast_reference_time=PartialDateTime(hour=simulated_hr))
    # Define default lat, lon, pressure contraint (None just bring model global data)
    latConstraint, lonConstraint, pressureConstraint = None, None, None
    if _requiredLat_: 
        # make constraint of required latitude
        latConstraint = iris.Constraint(latitude=lambda cell: 
                                _requiredLat_[0] <= cell <= _requiredLat_[-1])
    if _requiredLon_:
        # make constraint of required longitude
        lonConstraint = iris.Constraint(longitude=lambda cell: 
                                _requiredLon_[0] <= cell <= _requiredLon_[-1])
    
    if _requiredPressureLevels_:
        # make constraint of required pressure 
        # To slice out particular pressure levels (like 850, 200, 1000 alone)
        # then the following way is essential.       
        pressureConstraint = iris.Constraint(pressure=lambda cell: 
                                int(cell.point) in _requiredPressureLevels_)
    
    # make load constraints together
    loadConstraints = varConstraint & STASHConstraint & forecast_period_constraint & latConstraint & lonConstraint
    # initialize 
    ensembleData, ensCube, dshape = None, None, None
    print "packEnsembles Started using", infiles
    for idx, infile in enumerate(infiles):
        print "extracting ensemble data", infile
        # load ensemble cube with all constraints
        ensCube = getCubeData(infile, constraints=loadConstraints)
        if not ensCube: raise ValueError("unable to extract variable %s %s %d from %s" % (varName, varSTASH, fhr, infile))
        # Got variable successfully!    
        ensCube = ensCube[0]        
        # extract pressure levels
        if pressureConstraint and ensCube.coords('pressure'): 
            ensCube = ensCube.extract(pressureConstraint)
        # ene of if pressureConstraint and tmpCube.coords('pressure'): 

        if ensCube.has_lazy_data():
            print "Loaded", ensCube.standard_name, "into memory",
            ## By accessing tmpCube.data (even for printing), the full 
            ## data has been loaded into memory instead of being lazy 
            ## data. Especially for dust aod, we must make it as fully 
            ## loaded otherwise full data will be treated as zeros only 
            ## instead of 6 pseudo_level data.
            print "- min", ensCube.data.min(), "max", ensCube.data.max(),
            print "has_lazy_data =", ensCube.has_lazy_data()
        # end of if ensCube.has_lazy_data():        
        exmode = None # required, when user didnt do any regrid
        # interpolate it as per targetGridResolution deg resolution by 
        # setting up sample points based on coord 
        if _doRegrid_:
            if __LPRINT__: print "From shape", ensCube.shape                    
            if (varName, varSTASH) in _precipVars_:
                # DO NOT APPLY iris.analysis.Linear(extrapolation_mode='mask'), 
                # which writes nan every where for the snowfall_flux,  
                # rainfall_flux, precipitation_flux. So donot apply that.         
                exmode = 'linear'
            else:
                # In general all the other variables should not be 
                # extrapolated over masked grid points.
                exmode = 'mask'
            # end of if (...):
            # However, if user specified custom method do that!                
            exmode = _extraPolateMethod_ if _extraPolateMethod_ != 'auto' else exmode
            # but make sure that soil variables (or whichever variables do not have values over ocean)
            # do not extrapolate over ocean/masked regions. Otherwise, it will write only nan.
            exmode = 'mask' if varName in _maskOverOceanVars_ else exmode
                
            if os.path.isfile(_targetGridFile_):
                print "\n Regridding data to %s degree spatial resolution based on file %s\n" % (_targetGrid_.shape, _targetGridFile_) 
                # Do regrid based on user specfied target grid file.
                scheme = iris.analysis.Linear(extrapolation_mode=exmode)
                regdCube = ensCube.regrid(_targetGrid_, scheme)
                print "regrid data shape", regdCube.shape 
            else:           
                # Do regrid based on user specfied target grid resolution number.
                print "\n Regridding data to %sx%s degree spatial resolution \n" % (_targetGridRes_, _targetGridRes_)                    
                try:
                    # This lienar interpolate will do extra polate over ocean even 
                    # though original data doesnt have values over ocean and wise versa.
                    # So lets be aware of this.                    
                    regdCube = ensCube.interpolate(_targetGrid_, iris.analysis.Linear(extrapolation_mode=exmode))
                except Exception as e:
                    print "ALERT !!! Error while regridding!! %s" % str(e)
                    print " So skipping this without saving data"
                    continue
                # end of try:      
        else:
            # do not apply regrid. this is temporary fix. 
            regdCube = ensCube
        # end of if _doRegrid_:

        if _reverseLatitude_:
            # Need to reverse latitude from SN to NS
            rcsh = len(regdCube.data.shape)
            if rcsh == 3:
                regdCube.data = regdCube.data[:,::-1,:]
            elif rcsh == 2:
                regdCube.data = regdCube.data[::-1,:]
            lat = regdCube.coords('latitude')[0]
            lat.points = lat.points[::-1]
        # end of if _reverseLatitude_:
        
        unit = regdCube.units
        if varName.endswith('_flux'):
            # applicable only to TIGGE 
            # converting flux unit from time average into time integrated
            # by multiplying 60*60*6 = 21600 seconds in 6-hour 
            regdCube.data *= 21600.0            
            unit = Unit('W m-2 s') # changed unit from (W m-2) into (W m-2 s)
            print "Multiplied data with 60*60*6 seconds to make flux variable into time-intergrated"
            print regdCube.data.min(), regdCube.data.max()
        # end of if varName.endswith('_flux'):
        
        if (varName, varSTASH) in _precipVars_:
            # Since we are not using 'mask' option for extrapolate while 
            # doing linear regrid, which bring -ve values after regrid in 
            # extrapolated grids. So lets make it as 0 as minimum value.
            regdCube.data[regdCube.data < 0.0] = 0.0
        # end of if (varName, varSTASH) in _precipVars_:
        
        if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
            regdCube.data[regdCube.data > 0] = 1
            # trying to keep values either 0 or 1. Not fraction!
            regdCube.data = numpy.ma.array(regdCube.data, dtype=numpy.int)            
        # end of if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
        
        if exmode == 'mask':
            # For the above set of variables we shouldnot convert into 
            # masked array. Otherwise its full data goes as nan.                
            # convert data into masked array
            regdCube.data = numpy.ma.masked_array(regdCube.data, 
                                dtype=numpy.float64, fill_value=9.999e+20) 
            
            if (varName, varSTASH) in [('moisture_content_of_soil_layer', 'm01s08i223'),
                                       ('sea_ice_area_fraction', 'm01s00i031'),
                                       ('sea_ice_thickness', 'm01s00i032'),]:
                    # We should assign 0 instead 1e-15 only for this var!
                    regdCube.data[regdCube.data <= 1e-15] = 0.0
            elif (varName, varSTASH) == ('soil_temperature', 'm01s03i238'):
                # We should assign min instead 1e-15 only for this var!
                # because 0 will not make sense when temperature unit is Kelvin
                nmin = numpy.ma.masked_less_equal(regdCube.data, 1e-15).min()
                regdCube.data[regdCube.data <= 1e-15] = nmin
            # http://www.cpc.ncep.noaa.gov/products/wesley/g2grb.html
            # Says that 9.999e+20 value indicates as missingValue in grib2
            # by default g2ctl.pl generate "undefr 9.999e+20", so we must 
            # keep the fill_value / missingValue as 9.999e+20 only.
            numpy.ma.set_fill_value(regdCube.data, 9.999e+20)    
        # end of if exmode == 'mask':
                    
        if __fillFullyMaskedVars__ is not None and isinstance(regdCube.data, numpy.ma.masked_array):
            # yes, it is ma array
            if regdCube.data.mask.all():
                # Now data is fully masked. So lets fill with user passed value.
                # And still create ma array
                regdCube.data = regdCube.data.filled(__fillFullyMaskedVars__)
                print "filled masked vars", regdCube.data
                regdCube.data = numpy.ma.masked_array(regdCube.data.filled(__fillFullyMaskedVars__),
                                                     fill_value=9.999e+20) 
            elif regdCube.data.min() == regdCube.data.max():
                # Both min and max are same value. But its mask is not fully True.
                # So previous condition not executed, anyhow lets set 
                # fully the value of fillFullyMaskedVars.
                print "Both min and max are same. So lets fillFullyMaskedVars as", __fillFullyMaskedVars__ 
                regdCube.data = numpy.ma.masked_array(regdCube.data.filled(__fillFullyMaskedVars__), 
                                                    fill_value=9.999e+20)
        # end of if __fillFullyMaskedVars__ and ...:            
        print "regrid done"        

        # introduce ensemble dimension at first axis 
        dshape = list(regdCube.data.shape)
        dshape.insert(0, 1)    
        ensembleData = regdCube.data.reshape(dshape)
            
        print "taken into memory of all ensembles", ensembleData.shape 
        # convert data into masked array
        ensembleData = numpy.ma.masked_array(ensembleData, dtype=numpy.float64)
        if (varName, varSTASH) in [('precipitation_amount', 'm01s05i226'),]:
            # precipitation should not go less than 0.
            ensembleData.data[ensembleData.data < 0] = 0.0
        # end of if ...:
        
        # http://www.cpc.ncep.noaa.gov/products/wesley/g2grb.html
        # Says that 9.999e+20 value indicates as missingValue in grib2
        # by default g2ctl.pl generate "undefr 9.999e+20", so we must 
        # keep the fill_value / missingValue as 9.999e+20 only.
        numpy.ma.set_fill_value(ensembleData, 9.999e+20)
            
        totEns = len(ensembleData)
        member = int(infile.split('/')[-1].split('_')[0]) # get member number
        # create ensemble coordinate
        enscoord = iris.coords.DimCoord(numpy.array(member, dtype=numpy.int32), 
                             standard_name='realization', units=Unit('no_unit'), 
                                                    long_name='ensemble_member')
                                                                                                
        # get list of dimension coordinates
        dim_coords = list(regdCube.dim_coords)
        # insert ensemble dimension at first axis 
        dim_coords.insert(0, enscoord)
        # generate list of tuples contain index and coordinate
        dim_coords = [(coord, i) for i,coord in enumerate(dim_coords)]
        # get all other dimensions
        aux_factories = regdCube.aux_factories
        t = regdCube.coords('time')[0]
        fp = regdCube.coords('forecast_period')[0]
        ft = regdCube.coords('forecast_reference_time')[0]
        # create ensemble packed cubes 
        ensembleData = iris.cube.Cube(ensembleData, regdCube.standard_name, 
                                 regdCube.long_name, regdCube.var_name,
                                   unit, regdCube.attributes, 
                                       regdCube.cell_methods, dim_coords)
        # add all time coordinates
        print "setting aux_coords to", ensembleData.shape, varName, fhr 
        ensembleData.add_aux_coord(fp)
        ensembleData.add_aux_coord(ft)
        ensembleData.add_aux_coord(t)
        # create cell method for ensembles
        cm = iris.coords.CellMethod('realization', ('realization',), 
                               intervals=('1',), comments=(' ENS',))
        # add cell_methods to the ensembleData                        
        if regdCube.cell_methods:
            if (varName, varSTASH) in _accumulationVars_:
                # The following variables cell_methods should show accumulated/sum, but 
                # UM pp code doesnt support for accumulation. So lets fix it here ! 
                cm1 = iris.coords.CellMethod('sum', ('time',), 
                               intervals=('1 hour',), comments=('6 hour accumulation',))
                ensembleData.cell_methods = (cm, cm1)
            else:             
                ensembleData.cell_methods = (cm, regdCube.cell_methods[0])
        else:
            ensembleData.cell_methods = (cm,)
        print ensembleData
        # make memory free 
        del regdCube  
    
        print "To ensembleData shape", ensembleData.shape  

#        # get the regridded ensembles meta data 
#        varName, varSTASH, fcstTm, refTm, lat1, lon1 = getCubeAttr(ensembleData)
#        
#        if fcstTm.bounds is not None:                
#            # this is needed for forecast 00th simulated_hr
#            # get the last hour from bounds
#            hr = str(int(fcstTm.bounds[-1][-1]))
#            if __LPRINT__: print "Bounds comes in ", hr, fcstTm.bounds                        
#        else:
#            # get the fcst time point 
#            # this is needed for analysis/forecast 00th simulated_hr
#            hr = str(int(fcstTm.points))
#            if __LPRINT__: print "points comes in ", hr 
#        # end of if fcstTm.bounds:
        
#        outFileNameStructure = __fcstFileNameStructure__
#        # get the out fileName Structure based on pre / user defined indecies                       
#        outFnIndecies = __getAnlFcstFileNameIndecies__(outFileNameStructure)

#        # get the file name extension
#        fileExtension = outFileNameStructure[-1]  
        
#        if __fcst_step_hour__ == 24:
#            # make unique file name becase we are running in parallel            
#            if varName == 'air_temperature_maximum':
#                outFn = varSTASH + '-max_'+ outFn
#            elif varName == 'air_temperature_minimum':
#                outFn = varSTASH + '-min_'+ outFn
#            else:
#                outFn = varSTASH + '_'+ outFn  # suits for all other vars
#        # end of if __fcst_step_hour__ == 24:
                           
        ncfile = False
               
        # append out grib2 files for the purpose of creating ctl files.
        
        print ensembleData
        
        try:                
            save_tigge_tweaked_messages([ensembleData])                
        except Exception as e:
            print "ALERT !!! Error while saving!! %s" % str(e)
            print " So skipping this without saving data"
            continue
        # end of try:
        
        print "saved!"
        print ensembleData.standard_name, ensembleData.data.min(), ensembleData.data.max()
        print ensembleData
        # make memory free 
        del ensembleData
#     end of for idx, infile in enumerate(infiles):
# end of def packEnsembles(arg):                     


def packEnsemblesInParallel(arg):

    global  _startT_, _inDataPath_, __fcst_step_hour__, __LPRINT__, \
            _opPath_, _ensemble_count_, __outg2files__, __start_long_fcst_hour__, \
            _current_date_
                                    
    fpname, hr = arg 

    step_fcst_hour = __fcst_step_hour__    
    ensembleFiles_allConstraints_list = []
    
    fexthr = hr if int(hr) else '000' 
    ensembleFiles = [os.path.join(_inDataPath_, str(ens).zfill(3)+'_'+fpname+fexthr) 
                                            for ens in range(0, _ensemble_count_+1, 1)]
    fileName = '000_' + fpname + '000'  # sample file to get the variabels name.    
    fname = os.path.join(_inDataPath_, fileName)
    # get variable indices
    varNamesSTASH, fcstHours, doMultiHourlyMean, infile = umeps.getVarInOutFilesDetails(_inDataPath_,
                                                                                 fileName, hr)
    
    for fname in ensembleFiles:
        if not os.path.isfile(fname): 
            print "The file doesn't exists: %s.. \n" %fname
            return  
        # end of if not os.path.isfile(fname): 
    # end of for fname in ensembleFiles:
    
    if _convertVars_:
        # load only needed variables from this file as well sort as per user specified ordered vars!
        varNamesSTASH = [vns for vns in _convertVars_ if vns in varNamesSTASH]
    
    if not varNamesSTASH:
        print "No varibale selected to load from the file '%s' " % fname
        if __LPRINT__: 
            print "Because global variable _convertVars_ doesn't contain any one of the following variables"
            print "\n".join([str(i+1)+' : ' + str(tu) for i, tu in enumerate(varNamesSTASH)])
        return None
    else:
        print "The following variables are going to be converted from file ", fname
        print "\n".join([str(i+1)+' : ' + str(tu) for i, tu in enumerate(varNamesSTASH)])
    # end of if not varNamesSTASH:
    
    for varName, varSTASH in varNamesSTASH:        
        for fhr in fcstHours:            
            # the following vars doesnt have 0th time value, but it has 6th hour value.
            if (varName, varSTASH) in [('moisture_content_of_soil_layer', 'm01s08i223'), 
                                        ('soil_temperature', 'm01s03i238'),
                                        ('air_temperature', 'm01s03i236'),
                                        ('dew_point_temperature', 'm01s03i250'),
                                        ('x_wind', 'm01s03i209'),  
                                        ('y_wind', 'm01s03i210')] and not fhr: continue
            allConstraints = [varName, varSTASH, fhr]     
            ensembleFiles_allConstraints_list.append((ensembleFiles, allConstraints))
    # end of for varName, varSTASH in varNamesSTASH:      
    
    print "Started Processing the file:  \n" 
                                                
    ## get the no of childs process to create fcst ensemble files  
    nchild = len(ensembleFiles_allConstraints_list)     
    maxprocess = mp.cpu_count()
    if nchild > maxprocess: nchild = maxprocess
    # create the no of child parallel processes
    inner_pool = mp.Pool(processes=nchild)
    print "Creating %i (daemon) workers and jobs in child." % nchild

    print "parallel ensemble begins for", varName, varSTASH
    # pass the (ensemblefileslist, allConstraints, pressureConstraint) as 
    # argument to take one fcst ensemble file per process / core to regrid it.
    results = inner_pool.map(packEnsembles, ensembleFiles_allConstraints_list)
    # closing and joining child pools      
    inner_pool.close() 
    inner_pool.join()
    # parallel end
    # end of if __fcst_step_hour__ == 6:
              
    print "Time taken to convert the file: %8.5f seconds \n" %(time.time()-_startT_)
    print "Finished converting file: %s into grib2 format for fcst file: %s \n" %(fpname, hr)
# end of def packEnsemblesInParallel(arg):


# Start the convertFilesInParallel function
def convertEPSFilesInParallel(fnames, ftype):
    """
    convertFilesInParallel function calling all the sub-functions
    :param fnames: a simple filename as argument in a string format
    """
    
    global _startT_, _tmpDir_, _opPath_, __end_long_fcst_hour__,\
           __fcst_step_hour__, _createGrib2CtlIdxFiles_, \
           __start_long_fcst_hour__, _current_date_
    
    # calculate start hour of long fcst in multiple of days.
#    start_fcst_hour = __start_long_fcst_hour__ / 24
#    end_fcst_hour = __end_long_fcst_hour__ / 24
    fcst_times = [str(hr).zfill(3) for hr in range(__start_long_fcst_hour__, __end_long_fcst_hour__, 6)]
    fcst_filenames = [(fname, hr) for fname in fnames for hr in fcst_times]
    ## get the no of files and 
    nprocesses = len(fcst_filenames) 
    maxprocess = mp.cpu_count()
    if nprocesses > maxprocess: nprocesses = maxprocess
    # lets create no of parallel process w.r.t no of files.
    
    # parallel begin - 1 
    pool = _MyPool(nprocesses)
    print "Creating %d (non-daemon) workers and jobs in convertFilesInParallel process." % nprocesses        
    if ftype in ['fcst', 'forecast']:        
        results = pool.map(packEnsemblesInParallel, fcst_filenames)
    else:
        raise ValueError("Unknown file type !")
    # end of if ftype in ['anl', 'analysis']:    

    # closing and joining master pools
    pool.close()     
    pool.join()
    # parallel end - 1     
    print "Total time taken to convert %d files was: %8.5f seconds \n" %(len(fcst_filenames),(time.time()-_startT_))
    
    return
# end of def convertEPSFilesInParallel(fnames):

def convertEPSFcstFiles(inPath, outPath, tmpPath, **kwarg):
           
    global _targetGrid_, _targetGridRes_, _current_date_, _startT_, _tmpDir_, \
       _inDataPath_, _opPath_, _doRegrid_, _convertVars_, _requiredLat_, \
       _requiredLon_, _createGrib2CtlIdxFiles_, _createGrib1CtlIdxFiles_, \
       _convertGrib2FilestoGrib1Files_, __fcstFileNameStructure__, \
       __LPRINT__, __utc__, __fcst_step_hour__, __start_long_fcst_hour__, \
       __end_long_fcst_hour__, __outFileType__, __grib1FilesNameSuffix__, \
       __removeGrib2FilesAfterGrib1FilesCreated__, _depedendantVars_, \
       _removeVars_, _requiredPressureLevels_, __setGrib2TableParameters__, \
        __outg2files__, __start_long_fcst_hour__, __wgrib2Arguments__, \
        __UMtype__, _preExtension_, _extraPolateMethod_, _targetGridFile_, \
       __fillFullyMaskedVars__, _reverseLatitude_, epsMeanVars
     
    # load key word arguments
    UMtype = kwarg.get('UMtype', 'ensemble')
    targetGridResolution = kwarg.get('targetGridResolution', None)
    targetGridFile = kwarg.get('targetGridFile', '')
    date = kwarg.get('date', time.strftime('%Y%m%d'))
    utc = kwarg.get('utc', '00')
    overwrite = kwarg.get('overwrite', False)
    lprint = kwarg.get('lprint', False)
    convertVars = kwarg.get('convertVars', None)
    latitude = kwarg.get('latitude', None)
    longitude = kwarg.get('longitude', None)
    pressureLevels = kwarg.get('pressureLevels', None)
    fillFullyMaskedVars = kwarg.get('fillFullyMaskedVars', None)
    extraPolateMethod = kwarg.get('extraPolateMethod', 'auto')
    fcst_step_hour = kwarg.get('fcst_step_hour', 6)
    start_long_fcst_hour = kwarg.get('start_long_fcst_hour', 6)
    end_long_fcst_hour = kwarg.get('end_long_fcst_hour', 240)
    fcstFileNameStructure = kwarg.get('fcstFileNameStructure', None)
    createGrib2CtlIdxFiles = kwarg.get('createGrib2CtlIdxFiles', True)
    createGrib1CtlIdxFiles = kwarg.get('createGrib1CtlIdxFiles', False)
    convertGrib2FilestoGrib1Files = kwarg.get('convertGrib2FilestoGrib1Files', False)
    grib1FilesNameSuffix = kwarg.get('grib1FilesNameSuffix', '1')
    removeGrib2FilesAfterGrib1FilesCreated = kwarg.get('removeGrib2FilesAfterGrib1FilesCreated', False)
    callBackScript = kwarg.get('callBackScript', None)
    setGrib2TableParameters = kwarg.get('setGrib2TableParameters', None)
    wgrib2Arguments = kwarg.get('wgrib2Arguments', None)
    
    # assign out file type in global variable
    __outFileType__ = 'fcst'
    # assign the convert vars list of tuples to global variable
    if convertVars: _convertVars_ = convertVars
    # assign the analysis file name structure
    if fcstFileNameStructure: __fcstFileNameStructure__ = fcstFileNameStructure
    # set print variables details options
    __LPRINT__ = lprint    
    # update global variables
    __UMtype__ = UMtype
    __utc__ = utc
    __fcst_step_hour__ = fcst_step_hour
    __start_long_fcst_hour__ = start_long_fcst_hour
    __end_long_fcst_hour__ = end_long_fcst_hour
    __removeGrib2FilesAfterGrib1FilesCreated__ = removeGrib2FilesAfterGrib1FilesCreated
    __grib1FilesNameSuffix__ = grib1FilesNameSuffix
    _targetGridRes_ = str(targetGridResolution)
    _targetGridFile_ = targetGridFile
    _requiredLat_ = latitude
    _requiredLon_ = longitude
    _requiredPressureLevels_ = pressureLevels    
    _extraPolateMethod_ = extraPolateMethod
    __fillFullyMaskedVars__ = fillFullyMaskedVars
    _createGrib2CtlIdxFiles_ = createGrib2CtlIdxFiles
    _createGrib1CtlIdxFiles_ = createGrib1CtlIdxFiles
    _convertGrib2FilestoGrib1Files_ = convertGrib2FilestoGrib1Files
    __setGrib2TableParameters__ = setGrib2TableParameters
    __wgrib2Arguments__ = wgrib2Arguments
    # forecast filenames partial name

    fcst_fnames = ['pd', 'pg']
    
        
    # get the current date in YYYYMMDD format
    _tmpDir_ = tmpPath
    _current_date_ = date
    print "\n _current_date_ is %s" % _current_date_
    logpath = os.path.join(_tmpDir_, _current_date_)
    createDirWhileParallelRacing(logpath)
    logfile = 'um2grb2_fcst_stdout_'+ _current_date_ +'_' + utc +'Z.log'
    sys.stdout = myLog(os.path.join(logpath, logfile))
    
    # start the timer now
    _startT_ = time.time()

    # set-up base folders    
    _inDataPath_ = os.path.join(inPath, _current_date_)
    if not os.path.exists(_inDataPath_):
        raise ValueError("In datapath does not exists %s" % _inDataPath_)
    # end of if not os.path.exists(_inDataPath_):
    
    if convertVars:
        # check either depedendant vars are need to be loaded 
        for var, dvars in _depedendantVars_.iteritems():
            if var in convertVars:
                for dvar in dvars:
                    if dvar not in convertVars:               
                        _convertVars_.append(dvar)  # include depedendant var
                        _removeVars_.append(dvar)   # remove depedendant var at last
        # end of for var, dvar in _depedendantVars_.iteritems():
        for fcst_fname in fcst_fnames[:]:            
            # load only required file names to avoid unnneccessary computations
            # by cross checking with user defined variables list.
            
            hr = 0
            ## if fileName has some extension, then do not add hr to it.
            fileName = '000_' + fcst_fname + '1'
            varNamesSTASH, _, _, _ = umeps.getVarInOutFilesDetails(_inDataPath_, fileName, hr)
            print "varNamesSTASH", varNamesSTASH
            print "convertVars", convertVars
            # check either user requires this file or not!
            if not set(varNamesSTASH).intersection(convertVars):
                # remove the ext from fcst_fname, because user didn't 
                # require variabels from this fcst_fnames file.
                fcst_fnames.remove(fcst_fname)
                print "removed %s from list of files" % fcst_fname             
        # end of for fcst_fname in fcst_fnames:    
        print "Final fname list :", fcst_fnames 
    # end of if convertVars:    
    
    for fcst_fname in fcst_fnames:   
        # check either infiles are exist or not!
        status = umeps._checkInFilesStatus(_inDataPath_, 'prg', fcst_fname,         
                             start_long_fcst_hour=__start_long_fcst_hour__,
                                 end_long_fcst_hour=__end_long_fcst_hour__, 
                                         fcst_step_hour=__fcst_step_hour__, 
                                           ensemble_count=_ensemble_count_)
        print "in status+++++++++++++++++++++++++++", status
        if not status:
            raise ValueError("In datapath does not contain the above valid infiles")
        # end of if not instatus:
    # end of for fcst_fname in fcst_fnames:
    
    _opPath_ = os.path.join(outPath, _current_date_)
    createDirWhileParallelRacing(_opPath_) 
        
    # define default global lat start, lon end points
    slat, elat = (-90., 90.)
    # define default global lon start, lon end points 
    slon, elon = (0., 360.)
    # define user defined custom lat & lon start and end points
    if latitude: 
        (slat, elat) = latitude        
        if slat > elat:
            # just make sure while extracting south to north
            slat, elat = elat, slat            
            # and reverse while saving into grib2 file.
            _reverseLatitude_ = True
        # end of if slat > elat:
        _requiredLat_ = (slat, elat)
    # end of if latitude: 
    
    if os.path.isfile(_targetGridFile_):
        # load target grid from user specfied file and make it as target grid.
        _targetGrid_ = iris.load(_targetGridFile_)[0]
        _doRegrid_ = True   
    elif targetGridResolution is None:
        _doRegrid_ = False
        if longitude: (slon, elon) = longitude
        # reduce one step if user passed / default lon is 360. If we write 
        # longitude from 0 upto 360, wgrib2 reads it as 0 to 0. To avoid it, 
        # just reduct one small step in longitude only incase of 360.
        if int(elon) == 360: elon -= 0.0001
        if longitude: _requiredLon_ = (slon, elon)
    else:
        if not isinstance(targetGridResolution, (int, float)):
            raise ValueError("targetGridResolution must be either int or float")        
        if longitude: (slon, elon) = longitude
        # reduce one step if user passed / default lon is 360. If we write 
        # longitude from 0 upto 360, wgrib2 reads it as 0 to 0. To avoid it, 
        # just reduct one step in longitude only incase of 360.
        if int(elon) == 360: elon -= targetGridResolution 
        if longitude: _requiredLon_ = (slon, elon)
        # target grid as 0.25 deg (default) resolution by setting up sample points 
        # based on coord
        # generate lat, lon values
        latpoints = numpy.arange(slat, elat+targetGridResolution, targetGridResolution)
        lonpoints = numpy.arange(slon, elon+targetGridResolution, targetGridResolution)
        # correct lat, lon end points 
        if latpoints[-1] > elat: latpoints = latpoints[:-1]
        if lonpoints[-1] > elon: lonpoints = lonpoints[:-1]
        # set target grid lat, lon values pair                   
        _targetGrid_ = [('latitude', latpoints), ('longitude', lonpoints)]
        _doRegrid_ = True        
    # end of iif os.path.isfile(_targetGridFile_):
    
    # check either files are exists or not. delete the existing files in case
    # of overwrite option is True, else return without re-converting files.
    status = umeps._checkOutFilesStatus(_opPath_, 'prg', _current_date_, utc, overwrite)
    if status is 'FilesExist': 
        print "All files are already exists. So skipping convert Fcst files porcess"
        return # return back without executing conversion process.
    elif status in [None, 'FilesDoNotExist', 'FilesRemoved']:
        print "Going to start convert Fcst files freshly"
    # end of if status is 'FilesExists': 
    
    # do convert for forecast files  
    convertEPSFilesInParallel(fcst_fnames, ftype='fcst')
    time.sleep(30)  
    # make total time cummulated variables    
    for (TCV, TCVS, TCSVAR) in [('surface_net_downward_shortwave_flux', 'm01s01i202', 'ssr'),
                        ('surface_net_downward_longwave_flux', 'm01s02i201', 'str'), 
                        ('surface_upward_latent_heat_flux', 'm01s03i234', 'slhf'),   
                        ('surface_upward_sensible_heat_flux', 'm01s03i217', 'sshf'),   
                        ('toa_outgoing_longwave_flux', 'm01s02i205', 'ttr'),
                        ('precipitation_amount', 'm01s05i226', 'tp')]:
        if (TCV, TCVS) not in convertVars: continue

        # do cummulative precipitation_amount calculate for control run and ensemble members in parallel
        cummulated_ens = [(TCSVAR, TCV, 'pf', str(ensno)) for ensno in range(1, _ensemble_count_+1, 1)]
        cummulated_ens.insert(0, (TCSVAR, TCV, 'cf', '000'))

        ## get the no of files and 
        nprocesses = len(cummulated_ens) 
        maxprocess = mp.cpu_count()
        if nprocesses > maxprocess: nprocesses = maxprocess
        # lets create no of parallel process w.r.t no of files.
        
        # parallel begin - 1 
        pool = _MyPool(nprocesses)
        print "Creating %d (non-daemon) workers and jobs in convertFilesInParallel process." % nprocesses        
        results = pool.map(makeTotalCummulativeVars, cummulated_ens)
        # closing and joining master pools
        pool.close()     
        pool.join()
    # end of for (TCV, TCVS, TCSVAR) ...:
    

    
#    pwd = os.getcwd()
#    os.chdir(_opPath_)  # change to our path
#    if __fcst_step_hour__ == 6:
#        outg2files = [inf for inf in os.listdir(_opPath_) if 'hr' in inf if _preExtension_ in inf]
#        listOfInOutFiles = []
#        for fname in outg2files:
#            inFn = fname
#            outFn = fname.replace(_preExtension_, '')
#            listOfInOutFiles.append((inFn, outFn))
#        # end of for fname in outg2files:
#        
#        ## get the no of childs process to create fcst ensemble files  
#        nchild = len(listOfInOutFiles)     
#        maxprocess = mp.cpu_count()
#        if nchild > maxprocess: nchild = maxprocess
#        # create the no of child parallel processes
#        inner_pool = mp.Pool(processes=nchild)
#        print "Creating %i (daemon) workers and jobs in child." % nchild
#        # pass the (ensemblefileslist, allConstraints, pressureConstraint) as 
#        # argument to take one fcst ensemble file per process / core to regrid it.
#        results = inner_pool.map(doWgrib2cmd, listOfInOutFiles)
#        # closing and joining child pools      
#        inner_pool.close() 
#        inner_pool.join()
#        # parallel end  
#                
#        for (inFn, outFn) in listOfInOutFiles:
#            print inFn, outFn
#            # Lets create ctl and idx file. 
#            createGrib2CtlIdxFilesFn(outFn, ftype='fcst')  
#            # remove infile 
#            os.remove(inFn)
#        # end of for inFn, outFn in listOfInOutFiles:
#                        
#    elif __fcst_step_hour__ == 24:

#        dy = 'day'+str(int(__start_long_fcst_hour__) / 24).zfill(2)
#        outg2files = [inf for inf in os.listdir(_opPath_) if dy in inf if _preExtension_ in inf]
#        fname = '_'.join(outg2files[0].split('_')[1:]) # remove STASH alone
#        outFn = fname.replace(_preExtension_, '') # remove _preExtension_
#        
#        for varName, varSTASH in _convertVars_:
#            # make unique file name becase we are running in parallel            
#            if varName == 'air_temperature_maximum':
#                inFn = [inf for inf in outg2files if inf.startswith(varSTASH+'-max')]
#            elif varName == 'air_temperature_minimum':
#                inFn = [inf for inf in outg2files if inf.startswith(varSTASH+'-min')]
#            else:
#                # Generic all other vars filter with simple varSTASH
#                inFn = [inf for inf in outg2files if inf.startswith(varSTASH) if not '-' in inf]
#            # end of if varName == 'air_temperature_maximum':            
#            if not inFn: continue
#            inFn = inFn[0]
#            if __wgrib2Arguments__ is not None:
#                # execute post wgrib2 command in parellel (-ncpu 4 Best speed compare to 32)
#                cmd = "%s %s %s %s" % (wgrib2, inFn, __wgrib2Arguments__, outFn)
#                print "wgrib2 merge cmd", cmd
#                subprocess.call(cmd, shell=True)
#            else:
#                cubes = iris.load_cubes(inFn)
#                iris.fileformats.grib.save_messages(tweaked_messages(cubes), 
#                                                 outFn, append=True) # save grib2 file                
#            # end of if __wgrib2Arguments__:
#            time.sleep(15)
#            if (varName, varSTASH) not in epsMeanVars: os.remove(inFn)
#            ## epsMeanVars will be created through callback script. For that 
#            ## purpose we should not delete those files, because
#            ## it requires to create EPS MEAN VSDB INPUT. We have to load 
#            ## this file only in Python-IRIS. Because IRIS able to read it 
#            ## properly only for the simple compression algorithm not for the 
#            ## complex2 (wgrib2) algorithm. IRIS read the values wrongly,
#            ## if grib2 is written in complex2 algorithm. So... theses will 
#            ## be used to read it to create EPS mean and then will be deleted.
#            ## Dated : 05-Aug-2016.              
#        # end of for varName, varSTASH in varNamesSTASH:   
#        time.sleep(15)
#        # Lets create ctl and idx file. 
#        createGrib2CtlIdxFilesFn(outFn, ftype='fcst')       
#    # end of if __fcst_step_hour__ == 6:     
#    os.chdir(pwd) # Back to previous directory
#    
#    if callBackScript:
#        callBackScript = os.path.abspath(callBackScript)
#        if not os.path.exists(callBackScript): 
#            print "callBackScript '%s' doesn't exist" % callBackScript
#            return 
#        kwargs = ' --date=%s --start_long_fcst_hour=%d --end_long_fcst_hour=%d --fcst_step_hour=%d' % (_current_date_, start_long_fcst_hour, end_long_fcst_hour, __fcst_step_hour__)
#        scriptExecuteCmd = callBackScript + ' ' + kwargs
#        # execute user defined call back script with keyword arguments
#        subprocess.call(scriptExecuteCmd, shell=True)
#    # end of if callBackScript:
## end of def convertFcstFiles(...):



#    
# -- End code
