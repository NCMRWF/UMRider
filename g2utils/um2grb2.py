#!/usr/bin/env python

__author__ = 'arulalant'
__version__ = 'v2.0.0'
__long_name__ = 'NCUM Parallel Rider'

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
previous Update : 11-Mar-2016
latest Update : 29-Aug-2016
"""

# -- Start importing necessary modules
import os, sys, time, subprocess, errno
import numpy 
import iris
import gribapi
from cf_units import Unit
import multiprocessing as mp
import multiprocessing.pool as mppool       
# We must import this multiprocessing.pool explicitly, it is not imported
# by the top-level multiprocessing module.
import datetime
from iris.time import PartialDateTime
from cubeutils import cubeAverager, cubeAddSubtractor
from ncum_load_rules import update_cf_standard_name
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
#cnvgrib = "/gpfs1/home/Libs/INTEL/CNVGRIB/CNVGRIB-1.4.1/cnvgrib-1.4.1/cnvgrib"
cnvgrib = "/gpfs2/home/umtid/Softwares/cnvgrib/CNVGRIB-1.4.1/cnvgrib-1.4.1/cnvgrib"
wgrib2 = "/gpfs1/home/Libs/GNU/WGRIB2/v2.0.4/wgrib2/wgrib2"

# other global variables
__LPRINT__ = True
__utc__ = '00'
__UMReanalysis__ = False
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
_write2NetcdfFile_ = False
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
('upward_air_velocity_in_pascal', 'm01s15i242'),
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
('surface_downwelling_longwave_flux_in_air', 'm01s01i238'),
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
('snowfall_amount', 'm01s00i023'),
# the snowfall_amount might be changed as 
# liquid_water_content_of_surface_snow by convert it into
# water equivalent of snow amount, before re-ordering itself.
('liquid_water_content_of_surface_snow', 'm01s00i023'),
# IMDAA reanalysis extra variables other than NCUM 
('stratiform_snowfall_rate', 'm01s04i204'),
('soil_evaporation_rate', 'm01s03i296'),
('canopy_evaporation_rate', 'm01s03i297'),
('direct_surface_shortwave_flux_in_air', 'm01s01i215'),
('surface_downwelling_longwave_flux_assuming_clear_sky', 'm01s02i208'),
('open_sea_evaporation_rate', 'm01s03i232'),
('very_low_type_cloud_area_fraction', 'm01s09i202'),
('cloud_base_altitude', 'm01s09i219'),
('convective_rainfall_rate', 'm01s05i205'),
('convective_snowfall_flux', 'm01s05i206'),
('stratiform_rainfall_rate', 'm01s04i203'),
('subsurface_runoff_flux', 'm01s08i235'),
('surface_diffuse_downwelling_shortwave_flux_in_air', 'm01s01i216'),
('surface_downwelling_shortwave_flux_in_air_assuming_clear_sky', 'm01s01i210'),
('surface_net_downward_shortwave_flux', 'm01s01i201'),
('downward_heat_flux_in_soil', 'm01s03i202'),
('surface_roughness_length', 'm01s00i026'),
('surface_runoff_flux', 'm01s08i234'),
('surface_upward_water_flux', 'm01s03i223'),
('surface_upwelling_shortwave_flux_in_air_assuming_clear_sky', 'm01s01i211'),
('wind_speed_of_gust', 'm01s03i463'),
('surface_net_downward_shortwave_flux_corrected', 'm01s01i202'),
('soil_temperature', 'm01s08i225'),
# the below one is for orography which presents only in analysis file.
# so we must keep this as the last one in the ordered variables!
('surface_altitude', 'm01s00i033'),
('surface_geopotential_height', 'm01s00i033') # this is orography, but 
# some model requires orography has to be written in gpm unit.
],
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
                      ('stratiform_snowfall_amount', 'm01s04i202'),
                      ('convective_snowfall_amount', 'm01s05i202'),
                      ('stratiform_rainfall_amount', 'm01s04i201'),
                      ('convective_rainfall_amount', 'm01s05i201')]                      

## Define _ncfilesVars_
## the following variables need to be written into nc file, initially for 
## some reason (like either it may contain soil_model_level_number or 
## duplicate grib param where typeOfFirstFixedSurface [i.e toa, tropopause]
## is not implemented yet), but at the end of the program (after re-ordering)
## these intermediate nc files will be deleted automatically! 
## while storing into nc file, there wont be much problem and reading from
## nc file also wont be problem to load cf_standard_name into cube and 
## followed by storing into grib2 file. All because we need to write variables
## in the way we need (i.e. ordered always)!!
_ncfilesVars_ = [
('volumetric_moisture_of_soil_layer', 'm01s08i223'), 
# 'moisture_content_of_soil_layer' renamed as  
# 'volumetric_moisture_of_soil_layer', but same STASH m01s08i223 code.
('volumetric_moisture_of_soil_layer', 'm01s08i208'), 
# 'soil_moisture_content' renamed as  
# 'volumetric_moisture_of_soil_layer', but same STASH m01s08i208 code.
('soil_temperature', 'm01s08i225'), 
('soil_temperature', 'm01s03i238'),
('toa_incoming_shortwave_flux', 'm01s01i207'),
('toa_outgoing_longwave_flux', 'm01s02i205'),
('toa_outgoing_shortwave_flux', 'm01s01i205'),
('tropopause_altitude', 'm01s30i453'),
('tropopause_air_temperature', 'm01s30i452'),
('tropopause_air_pressure', 'm01s30i451'),
('surface_net_downward_shortwave_flux_corrected', 'm01s01i202'),
('atmosphere_optical_thickness_due_to_dust_ambient_aerosol', 'm01s02i422'),
('atmosphere_mass_content_of_dust_dry_aerosol_particles', 'm01s30i403'),
# surface_temperature grib code is same as air_temperature (for the purpose 
# of OSF, Hycom requirements). So while reading surface_temperature variable 
# from grib2 will make confusion along with air_temperature. To avoid this
# confusion, lets write this variable in nc seperate file.
('surface_temperature', 'm01s00i024'),
]



                 
## Define _ncmrGrib2LocalTableVars_
## the following variables need to be set localTableVersion no as 1 and
## master table version no as 255 (undefined), since WRF grib2 table doesnt
## support for the following variables. So we created our own local table.
_ncmrGrib2LocalTableVars_ = [
        'fog_area_fraction',
        'soil_evaporation_rate', 
        'canopy_evaporation_rate', 
        'open_sea_evaporation_rate', 
        'density_r_r_in_air',    
        'surface_net_downward_shortwave_flux_corrected',
        'direct_uv_flux_in_air', 
        'surface_downwelling_shortwave_flux_in_air_assuming_clear_sky', 
        'surface_upwelling_shortwave_flux_in_air_assuming_clear_sky'
        'toa_outgoing_shortwave_flux_assuming_clear_sky',
        'toa_outgoing_longwave_flux_assuming_clear_sky',   
        'surface_downwelling_longwave_flux_assuming_clear_sky', 
        'atmosphere_optical_thickness_due_to_dust_ambient_aerosol',
        'atmosphere_mass_content_of_dust_dry_aerosol_particles',
        'very_low_type_cloud_area_fraction', 
        'cloud_area_fraction_assuming_random_overlap',
        'cloud_area_fraction_assuming_maximum_random_overlap',
        'subsurface_runoff_flux', 
        'surface_upward_water_flux', 
        'downward_heat_flux_in_soil', 
        'cloud_volume_fraction_in_atmosphere_layer'
        'liquid_cloud_volume_fraction_in_atmosphere_layer'
        'ice_cloud_volume_fraction_in_atmosphere_layer',]


_short_name_ = {
    'convective_rainfall_amount': 'ACPCP',
    'convective_snowfall_amount': 'SNOC',
    'precipitation_amount': 'APCP',
    'stratiform_rainfall_amount': 'NCPCP',
    'stratiform_snowfall_amount': 'SNOL',
    'convective_rainfall_rate': 'CPRAT',
    'stratiform_rainfall_rate': 'LSPRATE',
    'stratiform_snowfall_rate': 'LSSRATE',
    'convective_snowfall_flux': 'CSRATE',
    'snowfall_amount': 'TSNOWP',
    'direct_surface_shortwave_flux_in_air': 'DSSWRFLX',
    'surface_diffuse_downwelling_shortwave_flux_in_air': 'DIFSSWRF',
    'surface_net_downward_shortwave_flux_corrected': 'NDDSWRFC',
    'toa_outgoing_shortwave_flux_assuming_clear_sky': 'CSUSFT',
    'toa_outgoing_longwave_flux_assuming_clear_sky': 'CSULFT',
    'surface_upwelling_shortwave_flux_in_air_assuming_clear_sky': 'CSUSFS',
    'surface_downwelling_shortwave_flux_in_air_assuming_clear_sky': 'CSDSFS',
    'surface_downwelling_longwave_flux_assuming_clear_sky': 'CSDLFS',
    'moisture_content_of_soil_layer': 'SOILM',
    'soil_temperature': 'TSOIL',
    'downward_heat_flux_in_soil': 'DSHFLUX',
    }


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
    ],

('surface_geopotential_height', 'm01s00i033'): [('surface_altitude', 'm01s00i033')],

('upward_air_velocity_in_pascal', 'm01s15i242'): [
                                ('upward_air_velocity', 'm01s15i242'),
                                ('air_temperature', 'm01s16i203')]
}
                                            

def createDirWhileParallelRacing(folder_location):
    # got same problem as below.
    # http://stackoverflow.com/questions/1586648/race-condition-creating-folder-in-python
    # So following this kind of try stuff.
    try:
        os.makedirs(folder_location)
        print "created folder", folder_location
    except OSError, e:
        if e.errno == errno.EEXIST and os.path.isdir(folder_location):
            # File exists, and it's a directory,
            # another process beat us to creating this dir, that's OK.
            print "folder already exists"
            pass
        else:
            # Our target dir exists as a file, or different error,
            # reraise the error!
            raise
# end of def createDirWhileParallelRacing(folder_location):

class myLog():
    """
    A simple class with destructor and construtor for logging the standatd I/O
    """
    def __init__(self, logfile):
        self.stdout = sys.stdout
        self.flush = sys.stdout.flush
        self.log = open(logfile, 'w')

    def write(self, text):
        self.stdout.write(text)
        self.log.write(text)
        self.log.flush()

    def close(self):
        self.stdout.close()
        self.log.close()
# end of class #1

def getCubeData(umFname, **kwarg):
    """
    This definition module reads the input file name and its location as a
    string and it returns the data as an Iris Cube.
    An upgraded version uses a GUI to read the file.

    :param umFname: UM fieldsfile filename passed as a string
    :return: Data for corresponding data file in Iris cube format
    
    KWarg : 
        constraints: multiple of iris.Constraint (by default None)
        
    Note : loaded cube may be update by callback function 
            "update_cf_standard_name" of ncum_load_rules module.
    """

    allconstraints = kwarg.get('constraints', None)        
    # check cf_standard_name of cubes and update it if necessary while loading 
    cubes = iris.load(umFname, constraints=allconstraints, 
                         callback=update_cf_standard_name)    
    return cubes
# end of def getCubeData(umFname, **kwarg):

def getYdayStr(today):
    """
    This module returns yesterday's date-time string 
        :today: today date string must follow pattern of yyyymmdd.
    
        :return: yesterday's date in string format of yyyymmdd.
    """
    tDay = datetime.datetime.strptime(today, "%Y%m%d")
    lag = datetime.timedelta(days=1)
    yDay = (tDay - lag).strftime('%Y%m%d')

    return yDay
# end of def getYdayStr(today):

def __getTodayOrYesterdayInfile__(ipath, fname):
    
    global __utc__, _current_date_
    
    ipath = ipath.split('/')
    hr = str(__utc__).zfill(2) 
    today_date = _current_date_        
    
    if hr in ['06', '12', '18']:
        hr = str(int(hr) - 6).zfill(2)
        print "Taken analysis past 6 hour data", hr, fname
    elif hr == '00':           
        # actually it returns yesterday's date.
        today_date = getYdayStr(today_date)
        # set yesterday's 18z hour.
        hr = '18'
        print "Taken analysis yesterday's date and 18z hour", today_date, fname 
    else:
        raise ValueError("hour %s method not implemented" % hr)
    # end of if hr in ['06', '12', '18']:            
        
    ## update the hour, date for 20170107/06 style
    if ipath[-1].isdigit():
        ipath[-1] = hr
        ipath[-2] = today_date        
    else:
        ## update the hour, date for 20170107T0600Z style
        for i, ip in enumerate(ipath[:]):
            if ip.startswith( _current_date_):
                ip = ip.split(_current_date_)
                ip = ip[0] + today_date + ip[-1]
                ip = ip.split('T'+__utc__)
                ip = ip[0] + 'T' + hr + ip[-1]
                ipath[i] = ip 
        # end of for i, ip in enumerate(ipath[:]):
    
    ipath = os.path.join('/', *ipath)
    # infile path (it could be current date and past 6 hour for 06,12,18 hours.  
    # but it set yesterday date and past 6 hour for 00 hour)
    infile = os.path.join(ipath, fname)  
    return infile, hr
# end of def __getTodayOrYesterdayInfile__(ipath):

def __getAnlFcstFileNameIndecies__(fileNameStructure):
    
    # define function to search in list 
    findInList = lambda searchList, elem: [[i for i, x in enumerate(searchList)
                                                     if x == e] for e in elem]
    dateFormat = None
    try:
        dateIdx = fileNameStructure.index('*YYYYMMDD*')
    except ValueError:
        # get the houIdx of hour pattern
        dateFormat = [idx for idx in fileNameStructure if idx.startswith('*') 
                                    and idx.endswith('*') and '%' in idx]

        if not dateFormat:
            raise ValueError('Couldnt find date strftime format')
        else:            
            dateFormat = dateFormat[0]
            # get index of dateFormat 
            dateIdx = fileNameStructure.index(dateFormat)
            # remove * from dateFormat
            dateFormat = dateFormat.split('*')[1]
    # end of try:
    
    # hour, utc are optional 
    hourIdx, hrFill, utcIdx, utcFill = None, None, None, None
    # day is alternate to hour 
    dayIdx, dayFill = None, None
    # get the houIdx of hour pattern
    hourIdx = [idx[0] for idx in findInList(fileNameStructure, 
                            ['*H*', '*HH*', '*HHH*']) if idx]
    dayIdx = [idx[0] for idx in findInList(fileNameStructure, 
                            ['*D*', '*DD*', '*DDD*']) if idx]
    # get the utcIdx of utc pattern
    utcIdx = [idx[0] for idx in findInList(fileNameStructure, 
                            ['*Z*', '*ZZ*', '*ZZZ*']) if idx]
                            
    # get the resolution pattern
    pIdx = [idx[0] for idx in findInList(fileNameStructure, 
                                            ['*pXp*']) if idx]
    if hourIdx:
        hourIdx = hourIdx[0]        
        hr = fileNameStructure[hourIdx]
        hrFill = len(hr.split('*')[1])
        if dayIdx: raise ValueError('Got both hour *H* and day *D*')
        
    if utcIdx:
        utcIdx = utcIdx[0]
        utc = fileNameStructure[utcIdx]
        utcFill = len(utc.split('*')[1])
        
    if dayIdx:
        dayIdx = dayIdx[0]
        day = fileNameStructure[dayIdx]
        dayFill = len(day.split('*')[1])
    
    if pIdx: pIdx = pIdx[0]
            
    return [(dateIdx, dateFormat), (hourIdx, hrFill), 
                (utcIdx, utcFill), (dayIdx, dayFill), (pIdx, None)]
# end of def _genAnlFcstFileName(fileNameStructure):


def __genAnlFcstOutFileName__(fileNameStructure, indecies, fcstDate, fcstHour, 
                             fcstUTC, preExtension='', modelResolution='0.17'):
    
    global _targetGridRes_
    
    # get the indecies 
    (dateIdx, dateFormat), (hourIdx, hrFill), (utcIdx, utcFill), (dayIdx, dayFill), (pIdx, _) = indecies
    # copy the argument list into local list, so that it wont change the arg.
    fileNameStructure = list(fileNameStructure) # copy of the original

    # update the date 
    if dateFormat is None:
        # update the date in YYYYMMDD format
        fileNameStructure[dateIdx] = fcstDate
    else:
        # construct forecast date from YYYYMMDD string format to time object
        t = time.strptime(fcstDate, '%Y%m%d')
        # from time object construct user defind string format and set it 
        fileNameStructure[dateIdx] = time.strftime(dateFormat, t)
    # end of if dateFormat is None:
    
    # update the hour    
    if hourIdx and hrFill:
        fileNameStructure[hourIdx] = str(int(fcstHour)).zfill(hrFill)
    
    # update the day instead of hour 
    if dayIdx and dayFill and not hourIdx:
        fileNameStructure[dayIdx] = str(int(fcstHour)/24).zfill(dayFill)
        
    # update the utc 
    if utcIdx and utcFill:
        fileNameStructure[utcIdx] = str(int(fcstUTC)).zfill(utcFill)
    
    # update resolution
    if pIdx:
        res = _targetGridRes_ if _targetGridRes_ else modelResolution
        if not '.' in res: res = str(float(res))
        res = res.replace('.', 'p')
        fileNameStructure[pIdx] = res + 'X' + res
        
    # insert pre-extension string
    fileNameStructure.insert(-1, preExtension)
    
    return ''.join(fileNameStructure)
# end of def __genAnlFcstOutFileName__(...):

def __completeInOutPath__(path, date, utc):
    # set-up base folders    
    path = path[:-1] if path.endswith('/') else path
    if '*' in path:
        inp = path
        if '*YYYYMMDD*' in path:
            # fill date 
            inp = path.split('*YYYYMMDD*')
            inp = inp[0] + date + inp[1]
        if '*ZZ*' in inp:
            # fill utc
            inp = inp.split('*ZZ*')
            inp = inp[0] + utc.zfill(2) + inp[1]
        # update indata path 
        return inp
    else:
        print "Couldn't find any date, utc format in path !"
        return path
    # end of if '*' in path:    
# end of def __completeInOutPath__(path, date, utc):

# start definition #2
def getVarInOutFilesDetails(inDataPath, fname, hr):
    """
    This definition module gets the required variables from the passed
    cube as per the WRF-Variables.txt file.
    (matches the contents of pgp06prepDDMMYY)
    - Improvements & Edits by AAT & MNRS
    :param inDataPath: data path which contains data and hour.
    :param fname: filename of the fieldsfile that has been passed as a string.

    :return: varNamesSTASH: a list of tuples (Variable name and its STASH code) 
    :return: fcstHours: Time slices of the cube as an array/scalar - integer (number)
    :return: doMultiHourlyMean: Logical expression as either True or False, indicating
                            whether the field is instantaneous or accumulated
    :return: infile: It returns absolute path of infile by inDataPath and fname.
                     Also it updates inDataPath yesterday, hour for analysis pf files
    :return: outfile: It returns outfile absolute path with ana or fcst type 
                      along with date and hour.
    Started by MNRS and improved by AAT!
    
    Updated : 07-12-2015
    Updated : 10-12-2015
    """
    global __anl_step_hour__, __fcst_step_hour__, _requiredPressureLevels_, \
           __outFileType__, __utc__
    
    hr = int(hr)
    simulated_hr = int(__utc__)
    
    infile = os.path.join(inDataPath, fname)    
    
    inDataPathHour = inDataPath.split('/')[-1]      
    inDataPathHour = None if not inDataPathHour.isdigit() else inDataPathHour
    
    ##### ANALYSIS FILE BEGIN     
    if fname.startswith(('qwqg00.pp0', 'umgla.pp0', 'umnsa.pp0')): # qwqg00.pp0
        varNamesSTASH = [('geopotential_height', 'm01s16i202'),
            ('air_temperature', 'm01s16i203'),
            ('relative_humidity', 'm01s16i256'),
            ('upward_air_velocity', 'm01s15i242'),
            ('air_pressure_at_sea_level', 'm01s16i222'),
            ('surface_air_pressure', 'm01s00i409'),
            ('surface_altitude', 'm01s00i033')]
        # the cube contains Instantaneous data at every 24-hours.        
        # but we need to extract every 0th hours instantaneous.
        if __anl_step_hour__ == 1:
            varNamesSTASH.remove(('geopotential_height', 'm01s16i202'))
        fcstHours = numpy.array([0,])     
        doMultiHourlyMean = False
    
    elif fname.startswith('umglc.pp0'): 
        varNamesSTASH = [('surface_altitude', 'm01s00i033')]
        # we need to extract every 0th hours instantaneous.
        fcstHours = numpy.array([0,])     
        doMultiHourlyMean = False
        
    elif fname.startswith('umglca_pb'):              # umglca_pb
        # available for use
        varNamesSTASH = [('land_binary_mask', 'm01s00i030'),
                    ('fog_area_fraction', 'm01s03i248'),
                    ('dew_point_temperature', 'm01s03i250'),
                    ('atmosphere_boundary_layer_thickness', 'm01s00i025'),
                    ('atmosphere_cloud_liquid_water_content', 'm01s30i405'),
                    ('atmosphere_cloud_ice_content', 'm01s30i406'),
                    ('atmosphere_mass_content_of_water', 'm01s30i404'),
                    ('atmosphere_mass_content_of_dust_dry_aerosol_particles', 'm01s30i403'),                    
                    ('surface_temperature', 'm01s00i024'),
                    ('relative_humidity', 'm01s03i245'),
                    ('visibility_in_air', 'm01s03i247'),
                    ('tropopause_altitude', 'm01s30i453'),
                    ('tropopause_air_temperature', 'm01s30i452'),
                    ('tropopause_air_pressure', 'm01s30i451'),
                    ('sea_ice_area_fraction', 'm01s00i031'),
                    ('sea_ice_thickness', 'm01s00i032'),
#                    ('soil_moisture_content', 'm01s08i208'), # production has -ve values, (WRONG values)
                    # the snowfall_amount need to be changed as 
                    # liquid_water_content_of_surface_snow by convert it into
                    # water equivalent of snow amount.
                    ('snowfall_amount', 'm01s00i023')] 
        # the cube contains Instantaneous data at every 3-hours.
        if __anl_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([0, 3,]) # yes, it must have both '0' & '3'
            # to get both 0 & 3 rd hour instantaneous data.
        elif __anl_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([0,])  # Yes, it must be just '0' only.
            # i.e. 0th hour instantaneous at 00, 06, 12, 18utc cycles for 6-hourly data.
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        doMultiHourlyMean = False
        
    elif fname.startswith('umglca_pd'):            # umglca_pd
        # consider variable
        if inDataPathHour == '00':
            varNamesSTASH = [('specific_humidity', 'm01s30i205'),
                             ('x_wind', 'm01s15i201'),
                             ('y_wind', 'm01s15i202'),] 
            # rest of them from taken already from qwqg00 
            # file. qwqg00 file variables are more correct than this 
            # short forecast vars.
        else:            
           varNamesSTASH = [('geopotential_height', 'm01s16i202'),
                       ('air_temperature', 'm01s16i203'), 
                       ('specific_humidity', 'm01s30i205'),
                       ('relative_humidity', 'm01s16i256'),                        
                       ('x_wind', 'm01s15i201'),
                       ('y_wind', 'm01s15i202'),
                       ('upward_air_velocity', 'm01s15i242')]
        # end of if inDataPathHour == '00':             
        
        # the cube contains Instantaneous data at every 3-hours.
        if __anl_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([0, 3,]) # yes, it must have both '0' & '3'
            # to get both 0 & 3 rd hour instantaneous data.
        elif __anl_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([0,])  # Yes, it must be just '0' only.
            # i.e. 0th hour instantaneous at 00, 06, 12, 18utc cycles for 6-hourly data.
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        doMultiHourlyMean = False
        
    elif fname.startswith('umglca_pe'):            # umglca_pe
        
        varNamesSTASH1 = [('high_type_cloud_area_fraction', 'm01s09i205'), 
                        ('medium_type_cloud_area_fraction', 'm01s09i204'),
                        ('low_type_cloud_area_fraction', 'm01s09i203'),
                        ('air_temperature', 'm01s03i236'),
                        ('air_pressure_at_sea_level', 'm01s16i222'),                              
                        ('specific_humidity', 'm01s03i237'),
                        ('surface_air_pressure', 'm01s00i409'),                        
                        ('x_wind', 'm01s03i225'),   # 10m
                        ('y_wind', 'm01s03i226'),   # 10m 
                        ('x_wind', 'm01s15i212'),    # 50m
                        ('y_wind', 'm01s15i213'),    # 50m    
                        ('x_wind', 'm01s15i201'),    # 8 pressureLevels
                        ('y_wind', 'm01s15i202'),    # 8 pressureLevels
                        ('geopotential_height', 'm01s16i202'),   # 8 pressureLevels          
                        ('surface_downwelling_longwave_flux_in_air', 'm01s01i238'),         
                        ('atmosphere_convective_available_potential_energy_wrt_surface', 'm01s05i233'), #CAPE
                        ('atmosphere_convective_inhibition_wrt_surface', 'm01s05i234'), #CIN
                        ('cloud_area_fraction_assuming_random_overlap', 'm01s09i216'),
                        ('cloud_area_fraction_assuming_maximum_random_overlap', 'm01s09i217')]

        if inDataPathHour == '00' and __anl_step_hour__ == 6:
            # remove only if __anl_step_hour__ is 6 hours.
            # for 3 hour analysis, (3rd hour) we need to extract these vars
            # from the umglca_pe file. But for 00th analysis the following vars 
            # need to be extracted from qwqg00.pp0 file. 
            for varST in [('air_pressure_at_sea_level', 'm01s16i222'), 
                            ('surface_air_pressure', 'm01s00i409'),]:
                # these vars taken already from qwqg00.pp0 file. so remove it.
                varNamesSTASH1.remove(varST)         
        # end of if inDataPathHour == '00' and ...:
        
        if __anl_step_hour__ == 1:
            # The following variable already available in pf file, but in 3-hour intervals.
            # Here in pe file its available in 1-hour intervals.
            varNamesSTASH1.append(('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'))
            # hourly average of shortwave flux
        # end of if __anl_step_hour__ == 1:
        
        # The precipitation_amount, *snowfall_amount, and *rainfall_amount 
        # variable must be at the last in this list. we will have to do 
        # 6 hourly accumulation instead of taking an instantaneous fileds. 
        # so we need to change doMultiHourlyMean as True, but rest of the other 
        # above variables are instantaneous fileds, so we can't simply make 
        # doMultiHourlyMean as True. Here we will make doMultiHourlyMean as False, 
        # but while extrating the following 5 amount variables we will change 
        # option doMultiHourlyMean as True. For this purpose we must keep these 
        # 5 variables at the last in the varNamesSTASH!
        varNamesSTASH2 = [('precipitation_amount', 'm01s05i226'),
                          ('stratiform_snowfall_amount', 'm01s04i202'),
                          ('convective_snowfall_amount', 'm01s05i202'),
                          ('stratiform_rainfall_amount', 'm01s04i201'),
                          ('convective_rainfall_amount', 'm01s05i201'),]
        # all vars 
        varNamesSTASH = varNamesSTASH1 + varNamesSTASH2
        # the cube contains Instantaneous data at every 1-hours.  
        if __anl_step_hour__ == 1: 
            fcstHours = numpy.arange(0,6,1)   
        elif __anl_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([0, 3,]) # yes, it must have both '0' & '3'
            # to get both 0 & 3 rd hour instantaneous data.
        elif __anl_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([0,])  # Yes, it must be just '0' only.
            # i.e. 0th hour instantaneous at 00, 06, 12, 18utc cycles for 6-hourly data.
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        doMultiHourlyMean = False

    elif fname.startswith('umglca_pf'):         # umglca_pf
        # other vars (these vars will be created as 6-hourly averaged)
        varNamesSTASH = [('surface_upward_latent_heat_flux', 'm01s03i234'),
                ('surface_upward_sensible_heat_flux', 'm01s03i217'),
                ('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'),
                ('surface_downwelling_longwave_flux', 'm01s02i207'),
                ('surface_net_downward_longwave_flux', 'm01s02i201'),
                ('surface_net_downward_shortwave_flux', 'm01s01i202'),
                ('toa_outgoing_longwave_flux', 'm01s02i205'),
                ('toa_outgoing_longwave_flux_assuming_clear_sky', 'm01s02i206'), 
                ('toa_incoming_shortwave_flux', 'm01s01i207'), 
                ('toa_outgoing_shortwave_flux', 'm01s01i205'), 
                ('toa_outgoing_shortwave_flux_assuming_clear_sky', 'm01s01i209'),
                # rainfall_flux, snowfall_flux, precipitation_flux are not 
                # accumulated vars, because these are averaged rate (kg m-2 s-1). 
                ('snowfall_flux', 'm01s05i215'),
                ('precipitation_flux', 'm01s05i216'),                          
                ('rainfall_flux', 'm01s05i214'),]
            
        # the cube contains data of every 3-hourly average or accumutated.  
        if __anl_step_hour__ == 1:
            # The following variable already taken from pe file which has 1-hourly intervals.
            # But in pf file it has 3-hourly intervals. So remove from pf file.
            varNamesSTASH1.remove(('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'))
            # hourly average of shortwave flux
        # end of if __anl_step_hour__ == 1:
              
        if __anl_step_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([4.5, 1.5])     
            # CAUTION : this must be 4.5 and then followed by 1.5 only. why ??
            # 4.5 extract data from yesterday date or previous 6 hourly cycle
            # simulated_hr data. whereas 1.5 extract data from current simulated_hr.
            # i.e. 1.5 means 0-3 hour from current simulated_hr
            # i.e. 4.5 means 3-6 hour from previous simulated_hr
            # such way we are changing the input file before extraction.
            # so we should not change this order 4.5 and then 1.5 ....
            
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __anl_step_hour__ == 6:       
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5)])                   
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True
        
        # get the updated infile w.r.t analysis 00 simulated_hr or 06,12,18hr
        infile, simulated_hr = __getTodayOrYesterdayInfile__(inDataPath, fname)
        
    elif fname.startswith('umglca_pi'):         # umglca_pi
        # vars (these vars will be created as 6-hourly averaged)
        varNamesSTASH = [('atmosphere_optical_thickness_due_to_dust_ambient_aerosol', 'm01s02i422'),
                         # The below two soil variable must be at the last in 
                         # this list, why because we are changing the infile
                         # to those 2 soil vars for 00utc ana.                         
                         ('moisture_content_of_soil_layer', 'm01s08i223'),
                         ('soil_temperature', 'm01s03i238'),]
        
        # the cube contains data of every 3-hourly average or instantaneous.
        # but we need to make only every 6th hourly average or instantaneous.
        
        # the dust aod contain 3-hourly averaged data. But soil temperature 
        # and moisture_content_of_soil_layer are 3-hourly instantaneous data.
        # though, here we set up fcstHours and doMultiHourlyMean values w.r.t 
        # dust aod only. For other 2 soil vars, we are fixing the values 
        # before extract those vars!
        if __anl_step_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([4.5, 1.5])
            # CAUTION : this must be 4.5 and then followed by 1.5 only. why ??
            # 4.5 extract data from yesterday date or previous 6 hourly cycle
            # simulated_hr data. whereas 1.5 extract data from current simulated_hr.
            # i.e. 1.5 means 0-3 hour from current simulated_hr
            # i.e. 4.5 means 3-6 hour from previous simulated_hr
            # such way we are changing the input file before extraction.
            # so we should not change this order 4.5 and then 1.5 ....
            
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __anl_step_hour__ == 6:       
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5)])
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True
        # get the updated infile w.r.t analysis 00 simulated_hr or 06,12,18hr
        # needed for atmosphere_optical_thickness_due_to_dust_ambient_aerosol,
        # but for soil_temperature and moisture_content_of_soil_layer we need 
        # to get current simulated_hr. WE FIXED THAT before extract it!
        infile, simulated_hr = __getTodayOrYesterdayInfile__(inDataPath, fname)
        
    ##### ANALYSIS FILE END
    
    ##### FORECAST FILE BEGIN
    elif fname.startswith('umglaa_pb'):              # umglaa_pb
        varNamesSTASH = [('land_binary_mask', 'm01s00i030'),
                    ('fog_area_fraction', 'm01s03i248'),
                    ('dew_point_temperature', 'm01s03i250'),
                    ('atmosphere_boundary_layer_thickness', 'm01s00i025'),
                    ('atmosphere_cloud_liquid_water_content', 'm01s30i405'),
                    ('atmosphere_cloud_ice_content', 'm01s30i406'),
                    ('atmosphere_mass_content_of_water', 'm01s30i404'),
                    ('atmosphere_mass_content_of_dust_dry_aerosol_particles', 'm01s30i403'),                    
                    ('surface_temperature', 'm01s00i024'),
                    ('relative_humidity', 'm01s03i245'),
                    ('visibility_in_air', 'm01s03i247'),
                    ('tropopause_altitude', 'm01s30i453'),
                    ('tropopause_air_temperature', 'm01s30i452'),
                    ('tropopause_air_pressure', 'm01s30i451'),
                    ('sea_ice_area_fraction', 'm01s00i031'),
                    ('sea_ice_thickness', 'm01s00i032'),
                    ('soil_moisture_content', 'm01s08i208'),  # production has -ve values, (WRONG values)
                    # the snowfall_amount need to be changed as 
                    # liquid_water_content_of_surface_snow by convert it into
                    # water equivalent of snow amount.
                    ('snowfall_amount', 'm01s00i023')] 
        # the cube contains Instantaneous data at every 3-hours.
        if __fcst_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour instantaneous/intervals
            fcstHours = numpy.array([24]) + hr
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        doMultiHourlyMean = False
        
    elif fname.startswith('umglaa_pd'):            # umglaa_pd
        # consider variable
        varNamesSTASH = [('geopotential_height', 'm01s16i202'),
                    ('air_temperature', 'm01s16i203'),  
                    ('specific_humidity', 'm01s30i205'),                    
                    ('relative_humidity', 'm01s16i256'),                    
                    ('x_wind', 'm01s15i201'),
                    ('y_wind', 'm01s15i202'),
                    ('upward_air_velocity', 'm01s15i242')]
        # the cube contains Instantaneous data at every 3-hours.
        if __fcst_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour instantaneous/intervals
            fcstHours = numpy.array([24]) + hr      
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.      
        doMultiHourlyMean = False
        
    elif fname.startswith('umglaa_pe'):            # umglaa_pe
        varNamesSTASH = [('high_type_cloud_area_fraction', 'm01s09i205'),
                    ('medium_type_cloud_area_fraction', 'm01s09i204'),
                    ('low_type_cloud_area_fraction', 'm01s09i203'),                    
                    ('air_temperature', 'm01s03i236'),
                    ('air_pressure_at_sea_level', 'm01s16i222'),
                    ('specific_humidity', 'm01s03i237'),
                    ('surface_air_pressure', 'm01s00i409'),
                    ('x_wind', 'm01s03i225'),   # 10m
                    ('y_wind', 'm01s03i226'),   # 10m 
                    ('x_wind', 'm01s15i212'),    # 50m
                    ('y_wind', 'm01s15i213'),    # 50m    
                    ('x_wind', 'm01s15i201'),    # 8 pressureLevels
                    ('y_wind', 'm01s15i202'),    # 8 pressureLevels
                    ('geopotential_height', 'm01s16i202'),   # 8 pressureLevels     
                    ('atmosphere_convective_available_potential_energy_wrt_surface', 'm01s05i233'), # CAPE
                    ('atmosphere_convective_inhibition_wrt_surface', 'm01s05i234'), #CIN
                    ('cloud_area_fraction_assuming_random_overlap', 'm01s09i216'),
                    ('cloud_area_fraction_assuming_maximum_random_overlap', 'm01s09i217'),
                    ('surface_downwelling_longwave_flux_in_air', 'm01s01i238'),
                    # The precipitation_amount, *snowfall_amount, and
                    # *rainfall_amount variable must be at the last
                    # in this list. we will have to do 6 hourly accumulation
                    # instead of taking an instantaneous fileds. so we need 
                    # to change doMultiHourlyMean as True, but rest of the other 
                    # above variables are instantaneous fileds, so we cant
                    # simply make doMultiHourlyMean as True. Here we will make 
                    # doMultiHourlyMean as False, but while extrating the 
                    # following 5 amount variables we will change option 
                    # doMultiHourlyMean as True. For this purpose we must keep 
                    # these 5 variables at the last in the varNamesSTASH!
                    ('precipitation_amount', 'm01s05i226'),
                    ('stratiform_snowfall_amount', 'm01s04i202'),
                    ('convective_snowfall_amount', 'm01s05i202'),
                    ('stratiform_rainfall_amount', 'm01s04i201'),
                    ('convective_rainfall_amount', 'm01s05i201'),]
        # the cube contains Instantaneous data at every 1-hours.
        if __fcst_step_hour__ == 1:
            # The following variable already available in pf file, but in 3-hour intervals.
            # Here in pe file its available in 1-hour intervals.
            varNamesSTASH.append(('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'))
            # hourly average of shortwave flux
            # applicable only for 1 hour instantaneous/intervals
            fcstHours = numpy.arange(1, 25, 1) + hr                           
        elif __fcst_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour instantaneous/intervals
            fcstHours = numpy.array([24]) + hr
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        doMultiHourlyMean = False

    elif fname.startswith('umglaa_pf'):             # umglaa_pf        
        # other vars (these vars will be created as 6-hourly averaged)
        varNamesSTASH = [('surface_upward_latent_heat_flux', 'm01s03i234'),
             ('surface_upward_sensible_heat_flux', 'm01s03i217'),
             ('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'),
             ('surface_downwelling_longwave_flux', 'm01s02i207'),
             ('surface_net_downward_longwave_flux', 'm01s02i201'),
             ('surface_net_downward_shortwave_flux', 'm01s01i202'),
             ('toa_outgoing_longwave_flux', 'm01s02i205'),
             ('toa_outgoing_longwave_flux_assuming_clear_sky', 'm01s02i206'), 
             ('toa_incoming_shortwave_flux', 'm01s01i207'), 
             ('toa_outgoing_shortwave_flux', 'm01s01i205'),
             ('toa_outgoing_shortwave_flux_assuming_clear_sky', 'm01s01i209'),
             # rainfall_flux, snowfall_flux, precipitation_flux are not 
             # accumulated vars, because these are averaged rate (kg m-2 s-1). 
             ('snowfall_flux', 'm01s05i215'),
             ('precipitation_flux', 'm01s05i216'),                          
             ('rainfall_flux', 'm01s05i214'),]
        # the cube contains data of every 3-hourly average or accumutated.
        if __fcst_step_hour__ == 1:
            # The following variable already taken from pe file which has 1-hourly intervals.
            # But in pf file it has 3-hourly intervals. So remove from pf file.
            varNamesSTASH.remove(('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'))            
            # hourly average of shortwave flux
            fcstHours = numpy.arange(25) + hr + 0.5
        elif __fcst_step_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([1.5, 4.5, 7.5, 10.5, 13.5, 16.5, 19.5, 22.5]) + hr
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __fcst_step_hour__ == 6:       
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5), (7, 11), (13, 17), (19, 23)]) + hr  
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True  
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour average or accumutated.
            fcstHours = numpy.array([(1, 23)]) + hr  
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 24 hourly average/accumulation explicitly.
            doMultiHourlyMean = True    
        
    elif fname.startswith('umglaa_pi'):             # umglaa_pi        
        # other vars (these vars will be created as 6-hourly averaged)
        varNamesSTASH = [('atmosphere_optical_thickness_due_to_dust_ambient_aerosol', 'm01s02i422'),
                         # The below two soil variable must be at the last in 
                         # this list, why because we are changing the infile
                         # to those 2 soil vars for 00utc ana. 
                         ('moisture_content_of_soil_layer', 'm01s08i223'),
                         ('soil_temperature', 'm01s03i238'),]
                
        # the cube contains data of every 3-hourly average or instantaneous.
        
        # the dust aod contain 3-hourly averaged data. But soil temperature 
        # and moisture_content_of_soil_layer are 3-hourly instantaneous data.
        # though, here we set up fcstHours and doMultiHourlyMean values w.r.t 
        # dust aod only. For other 2 soil vars, we are fixing the values 
        # before extract those vars!
        if __fcst_step_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([1.5, 4.5, 7.5, 10.5, 13.5, 16.5, 19.5, 22.5]) + hr
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5), (7, 11), (13, 17), (19, 23)]) + hr 
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True 
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour average or accumutated.
            fcstHours = numpy.array([(1, 23)]) + hr     
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 24 hourly average/accumulation explicitly.
            doMultiHourlyMean = True    
        
    ##### FORECAST FILE END
    
    ##### REGIONAL FORECAST FILE BEGIN
    elif fname.startswith('umnsaa_pb'):              # umglaa_pb
        varNamesSTASH = [('land_binary_mask', 'm01s00i030'),
                    ('fog_area_fraction', 'm01s03i248'),
                    ('dew_point_temperature', 'm01s03i250'),
                    ('atmosphere_boundary_layer_thickness', 'm01s00i025'),
                    ('atmosphere_cloud_liquid_water_content', 'm01s30i405'),
                    ('atmosphere_cloud_ice_content', 'm01s30i406'),
                    ('atmosphere_mass_content_of_water', 'm01s30i404'),
                    ('atmosphere_mass_content_of_dust_dry_aerosol_particles', 'm01s30i403'),                    
                    ('surface_temperature', 'm01s00i024'),
                    ('relative_humidity', 'm01s03i245'),
                    ('visibility_in_air', 'm01s03i247'),
                    ('tropopause_altitude', 'm01s30i453'),
                    ('tropopause_air_temperature', 'm01s30i452'),
                    ('tropopause_air_pressure', 'm01s30i451'),
                    ('sea_ice_area_fraction', 'm01s00i031'),
                    ('sea_ice_thickness', 'm01s00i032'),
                    ('soil_moisture_content', 'm01s08i208'),  # production has -ve values, (WRONG values)
                    # the snowfall_amount need to be changed as 
                    # liquid_water_content_of_surface_snow by convert it into
                    # water equivalent of snow amount.
                    ('snowfall_amount', 'm01s00i023')] 
        # the cube contains Instantaneous data at every 3-hours.
        if __fcst_step_hour__ == 1:
            # applicable only for 1 hour average or accumutated.
            fcstHours = numpy.array([1, 2, 3, 4, 5, 6]) + hr
            # model itself produced 1 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
        elif __fcst_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour instantaneous/intervals
            fcstHours = numpy.array([24]) + hr
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        if __outFileType__ == 'ana': 
            fcstHours = numpy.array([1]) # extract from 0 to 0.25, consider 0 to 15 min as anl.
        doMultiHourlyMean = False
        
    elif fname.startswith('umnsaa_pd'):            # umglaa_pd
        # consider variable
        varNamesSTASH = [('geopotential_height', 'm01s16i202'),
                    ('air_temperature', 'm01s16i203'),  
                    ('specific_humidity', 'm01s30i205'),                    
                    ('relative_humidity', 'm01s16i256'),                    
                    ('x_wind', 'm01s15i201'),
                    ('y_wind', 'm01s15i202'),
                    ('upward_air_velocity', 'm01s15i242')]
        # the cube contains Instantaneous data at every 3-hours.
        if __fcst_step_hour__ == 1:
            # applicable only for 1 hour average or accumutated.
            fcstHours = numpy.array([1, 2, 3, 4, 5, 6]) + hr            
        elif __fcst_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour instantaneous/intervals
            fcstHours = numpy.array([24]) + hr      
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.      
        doMultiHourlyMean = False
        
    elif fname.startswith('umnsaa_pe'):            # umglaa_pe
        varNamesSTASH = [('high_type_cloud_area_fraction', 'm01s09i205'),
                    ('medium_type_cloud_area_fraction', 'm01s09i204'),
                    ('low_type_cloud_area_fraction', 'm01s09i203'),                    
                    ('air_temperature', 'm01s03i236'),
                    ('air_pressure_at_sea_level', 'm01s16i222'),
                    ('specific_humidity', 'm01s03i237'),
                    ('surface_air_pressure', 'm01s00i409'),
                    ('x_wind', 'm01s15i212'), # 50meter B-Grid U component wind 
                    ('y_wind', 'm01s15i213'), # 50meter B-Grid V component wind  
                    ('x_wind', 'm01s03i225'), # 10 meter U wind 
                    ('y_wind', 'm01s03i226'), # 10 meter V wind 
                    ('x_wind', 'm01s15i201'), # 8 pressure levels
                    ('y_wind', 'm01s15i202'), # 8 pressure levels
                    ('geopotential_height', 'm01s16i202'), # 8 pressure levels 
                    ('cloud_area_fraction_assuming_random_overlap', 'm01s09i216'),
                    ('cloud_area_fraction_assuming_maximum_random_overlap', 'm01s09i217'),
                    ('water_evaporation_flux_from_soil','m01s03i229'),
                    # The precipitation_amount, *snowfall_amount, and
                    # *rainfall_amount variable must be at the last
                    # in this list. we will have to do 6 hourly accumulation
                    # instead of taking an instantaneous fileds. so we need 
                    # to change doMultiHourlyMean as True, but rest of the other 
                    # above variables are instantaneous fileds, so we cant
                    # simply make doMultiHourlyMean as True. Here we will make 
                    # doMultiHourlyMean as False, but while extrating the 
                    # following 5 amount variables we will change option 
                    # doMultiHourlyMean as True. For this purpose we must keep 
                    # these 5 variables at the last in the varNamesSTASH!
                    ('stratiform_snowfall_amount', 'm01s04i202'),
                    ('stratiform_rainfall_amount', 'm01s04i201'),]
                    
#        if _requiredPressureLevels_ and set(_requiredPressureLevels_).issubset([925., 960., 975., 980., 985., 990., 995., 1000.]):
#            # same stash available in pd file also. so include only incase of chosen pressure level 
#            # applicable to this pe file.
#            varNamesSTASH.append(('geopotential_height', 'm01s16i202')) # 8 pressure levels            
            
        # the cube contains Instantaneous data at every 1-hours.
        if __fcst_step_hour__ == 1:
            # applicable only for 1 hour average or accumutated.
            fcstHours = numpy.array([1, 2, 3, 4, 5, 6]) + hr            
        elif __fcst_step_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour instantaneous/intervals
            fcstHours = numpy.array([24]) + hr
        
        if __outFileType__ == 'ana': 
            fcstHours = [lambda cell: 0 < cell < 0.25] # extract from 0 to 0.25, consider 0 to 15 min as anl.
            
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        doMultiHourlyMean = False

    elif fname.startswith('umnsaa_pf'):             # umglaa_pf        
        # other vars (these vars will be created as 6-hourly averaged)
        varNamesSTASH = [('surface_upward_latent_heat_flux', 'm01s03i234'),
             ('surface_upward_sensible_heat_flux', 'm01s03i217'),
             ('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'),
             ('surface_downwelling_longwave_flux', 'm01s02i207'),
             ('surface_net_downward_longwave_flux', 'm01s02i201'),
             ('surface_net_downward_shortwave_flux', 'm01s01i202'),
             ('toa_outgoing_longwave_flux', 'm01s02i205'),
             ('toa_outgoing_longwave_flux_assuming_clear_sky', 'm01s02i206'), 
             ('toa_incoming_shortwave_flux', 'm01s01i207'), 
             ('toa_outgoing_shortwave_flux', 'm01s01i205'),
             ('toa_outgoing_shortwave_flux_assuming_clear_sky', 'm01s01i209'),]
        # the cube contains data of every 3-hourly average or accumutated.
        if __fcst_step_hour__ == 1:
            # applicable only for 1 hour average or accumutated.
            fcstHours = numpy.array([0.5, 1.5, 2.5, 3.5, 4.5, 5.5]) + hr
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __fcst_step_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([1.5, 4.5, 7.5, 10.5, 13.5, 16.5, 19.5, 22.5]) + hr
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __fcst_step_hour__ == 6:       
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5), (7, 11), (13, 17), (19, 23)]) + hr  
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True  
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour average or accumutated.
            fcstHours = numpy.array([(1, 23)]) + hr  
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 24 hourly average/accumulation explicitly.
            doMultiHourlyMean = True    
            
        if __outFileType__ == 'ana': 
            fcstHours = numpy.array([0.5]) # extract from 0 to 0.25, consider 0 to 15 min as anl.
            doMultiHourlyMean = False
            
    elif fname.startswith('umnsaa_pi'):             # umglaa_pi        
        # other vars (these vars will be created as 6-hourly averaged)
        varNamesSTASH = [# The below two soil variable must be at the last in 
                         # this list, why because we are changing the infile
                         # to those 2 soil vars for 00utc ana. 
                         ('moisture_content_of_soil_layer', 'm01s08i223'),
                         ('soil_temperature', 'm01s03i238'),] 
                
        # the cube contains data of every 3-hourly average or instantaneous.
        
        # the dust aod contain 3-hourly averaged data. But soil temperature 
        # and moisture_content_of_soil_layer are 3-hourly instantaneous data.
        # though, here we set up fcstHours and doMultiHourlyMean values w.r.t 
        # dust aod only. For other 2 soil vars, we are fixing the values 
        # before extract those vars!
        if __fcst_step_hour__ == 1:
            # applicable only for 1 hour average or accumutated.
            fcstHours = numpy.array([1, 2, 3, 4, 5, 6]) + hr            ###### NEED TO FIX 
            doMultiHourlyMean = False
        elif __fcst_step_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([1.5, 4.5, 7.5, 10.5, 13.5, 16.5, 19.5, 22.5]) + hr
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __fcst_step_hour__ == 6:
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5), (7, 11), (13, 17), (19, 23)]) + hr 
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True 
        elif __fcst_step_hour__ == 24:
            # applicable only for 24 hour average or accumutated.
            fcstHours = numpy.array([(1, 23)]) + hr     
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 24 hourly average/accumulation explicitly.
            doMultiHourlyMean = True    
        
    ##### REGIONAL FORECAST FILE END
            
    ##### IMDAA FORECAST FILE BEGIN #######
    elif  fname.startswith('pp3'):             # pp3
        varNamesSTASH = [    
                    ('stratiform_snowfall_rate', 'm01s04i204'),   
                    ('soil_evaporation_rate', 'm01s03i296'),   
                    ('canopy_evaporation_rate', 'm01s03i297'),   
                    ('direct_surface_shortwave_flux_in_air', 'm01s01i215'),   
                    ('surface_downwelling_longwave_flux_assuming_clear_sky', 'm01s02i208'),   
                    ('open_sea_evaporation_rate', 'm01s03i232'),   
                    ('very_low_type_cloud_area_fraction', 'm01s09i202'),   
                    ('cloud_area_fraction_assuming_random_overlap', 'm01s09i216'),   
                    ('direct_uv_flux_in_air', 'm01s01i212'),   
                    ('air_pressure_at_sea_level', 'm01s16i222'),   
                    ('air_temperature', 'm01s03i236'),   
                    ('atmosphere_boundary_layer_thickness', 'm01s00i025'),   
                    ('cloud_base_altitude', 'm01s09i219'),   
                    ('convective_rainfall_amount', 'm01s05i201'),   
                    ('convective_rainfall_rate', 'm01s05i205'),   
                    ('convective_snowfall_amount', 'm01s05i202'),   
                    ('convective_snowfall_flux', 'm01s05i206'),   
                    ('downward_heat_flux_in_soil', 'm01s03i202'),   
                    ('high_type_cloud_area_fraction', 'm01s09i205'),   
                    ('land_binary_mask', 'm01s00i030'),   
                    ('low_type_cloud_area_fraction', 'm01s09i203'),   
                    ('medium_type_cloud_area_fraction', 'm01s09i204'),   
                    ('moisture_content_of_soil_layer', 'm01s08i223'),   
                    ('precipitation_amount', 'm01s05i226'),   
                    ('relative_humidity', 'm01s03i245'),   
                    ('relative_humidity', 'm01s09i229'),   
                    ('snowfall_amount', 'm01s00i023'),   
                    ('soil_temperature', 'm01s08i225'),   
                    ('stratiform_rainfall_amount', 'm01s04i201'),   
                    ('stratiform_rainfall_rate', 'm01s04i203'),   
                    ('stratiform_snowfall_amount', 'm01s04i202'),   
                    ('subsurface_runoff_flux', 'm01s08i235'),   
                    ('surface_air_pressure', 'm01s00i409'),   
                    ('surface_diffuse_downwelling_shortwave_flux_in_air', 'm01s01i216'),   
                    ('surface_downwelling_longwave_flux', 'm01s02i207'),   
                    ('surface_downwelling_shortwave_flux_in_air', 'm01s01i235'),   
                    ('surface_downwelling_shortwave_flux_in_air_assuming_clear_sky', 'm01s01i210'),   
                    ('surface_net_downward_longwave_flux', 'm01s02i201'),   
                    ('surface_net_downward_shortwave_flux', 'm01s01i201'),   
                    ('surface_net_downward_shortwave_flux', 'm01s01i202'),   
                    ('surface_net_downward_shortwave_flux_corrected', 'm01s01i202'),
                    ('surface_roughness_length', 'm01s00i026'),   
                    ('surface_runoff_flux', 'm01s08i234'),   
                    ('surface_temperature', 'm01s00i024'),   
                    ('surface_upward_latent_heat_flux', 'm01s03i234'),   
                    ('surface_upward_sensible_heat_flux', 'm01s03i217'),   
                    ('surface_upward_water_flux', 'm01s03i223'),   
                    ('surface_upwelling_shortwave_flux_in_air_assuming_clear_sky', 'm01s01i211'),   
                    ('toa_incoming_shortwave_flux', 'm01s01i207'),   
                    ('toa_outgoing_longwave_flux', 'm01s02i205'),   
                    ('toa_outgoing_longwave_flux_assuming_clear_sky', 'm01s02i206'),   
                    ('toa_outgoing_shortwave_flux', 'm01s01i205'),   
                    ('toa_outgoing_shortwave_flux_assuming_clear_sky', 'm01s01i209'),   
                    ('visibility_in_air', 'm01s03i247'),   
                    ('wind_speed_of_gust', 'm01s03i463'),   
                    ('x_wind', 'm01s03i225'),   
                    ('x_wind', 'm01s15i212'),   
                    ('y_wind', 'm01s03i226'),   
                    ('y_wind', 'm01s15i213'),] 
        # Just convert pp/ff file to grib2/nc file. So no need to extract 
        # individual fcst hours.
        fcstHours = [lambda cell: 0 <= cell <= 5.0] # extract from 0 to 9
        doMultiHourlyMean = False
        
    elif  fname.startswith('pp5'):             # pp5

        varNamesSTASH = [
                    ('density_r_r_in_air', 'm01s00i253'),   
                    ('cloud_volume_fraction_in_atmosphere_layer', 'm01s00i266'),   
                    ('liquid_cloud_volume_fraction_in_atmosphere_layer', 'm01s00i267'),   
                    ('ice_cloud_volume_fraction_in_atmosphere_layer', 'm01s00i268'),   
                    ('air_potential_temperature', 'm01s00i004'),   
                    ('air_pressure', 'm01s00i408'),   
                    ('dimensionless_exner_function', 'm01s00i255'),   
                    ('mass_fraction_of_cloud_ice_in_air', 'm01s00i012'),   
                    ('mass_fraction_of_cloud_liquid_water_in_air', 'm01s00i254'),   
                    ('potential_vorticity_of_atmosphere_layer', 'm01s15i217'),   
                    ('specific_humidity', 'm01s00i010'),   
                    ('surface_altitude', 'm01s00i033'),   
                    ('upward_air_velocity', 'm01s00i150'),   
                    ('x_wind', 'm01s00i002'),   
                    ('y_wind', 'm01s00i003'),]
        # Just convert pp/ff file to grib2/nc file. So no need to extract 
        # individual fcst hours.
        fcstHours = [lambda cell: 0 <= cell <= 5.0] # extract from 0 to 9
        doMultiHourlyMean = False    
            
    elif  fname.startswith('pp6'):             # pp6

        varNamesSTASH = [('air_temperature', 'm01s16i203'),
                         ('geopotential_height', 'm01s16i202'),
                         ('relative_humidity', 'm01s16i256'),
                         ('x_wind', 'm01s15i201'),
                         ('y_wind', 'm01s15i202'),]
        # Just convert pp/ff file to grib2/nc file. So no need to extract 
        # individual fcst hours.
        fcstHours = [lambda cell: 0 <= cell <= 5.0] # extract from 0 to 9
        doMultiHourlyMean = False    
    ##### IMDAA FORECAST FILE END #######
    else:
        raise ValueError("Filename not implemented yet!")
    # end if-loop

    return varNamesSTASH, fcstHours, doMultiHourlyMean, infile, simulated_hr
# end of definition #2

# start definition #3
def getCubeAttr(tmpCube):
    """
    This module returns basic coordinate & attribute info about any Iris data cube.
    :param tmpCube: a temporary Iris cube containing a single geophysical field/parameter
    :return: stdNm: CF-compliant Standard name of the field/parameter
    :return: fcstTm: forecast time period for eg: 00, 06, 12 etc -- units as in hours
    :return: refTm: reference time -- units as date  in Gregorian
    :return: lat as scalar array (1D) units as degree (from 90S to 90N)
    :return: lon as scalar array (1D) units as degree (from 0E to 360E)
    Original by MNRS
    """
    stdNm = tmpCube.standard_name
    stdNm = stdNm if stdNm else tmpCube.long_name
    stash = str(tmpCube.attributes['STASH'])
    fcstTm = tmpCube.coord('forecast_period')
    refTm = tmpCube.coord('forecast_reference_time')
    lat = tmpCube.coord('latitude')
    lon = tmpCube.coord('longitude')

    return stdNm, stash, fcstTm, refTm, lat, lon
# end of definition #3

# create a class #2 to initiate mp daemon processes
class _NoDaemonProcess(mp.Process):
    # make 'daemon' attribute always return False
    # A class created by AAT
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)
# end of class #2

# create a class #3 to set-up worker-pools
class _MyPool(mppool.Pool):
    # We sub-class multiprocessing.pool. Pool instead of multiprocessing.Pool
    # because the latter is only a wrapper function, not a proper class.
    ### http://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic
    ### refer the above link to invoke child processes
    # A class created by AAT
    Process = _NoDaemonProcess
# end of class #3

def _createDepthBelowLandSurfaceCoords1Lev(cube):
    # Dr. Saji / UM_Model_DOC suggested that UM produce Root zone soil model
    # level number is equivalent to 0 to 2m. (i.e. from 1 to 4 layer no)
    
    global __soilFirstSecondFixedSurfaceUnit__ 

    if __soilFirstSecondFixedSurfaceUnit__ == 'cm':
        # So we kept here unit as 'cm'. But points are muliplied by
        # 100 with its  corresponding cm values. Why because, that 
        # 100 will be factorized (divied) in grib_message by setting 
        # scaleFactorOfFirstFixedSurface as 2 and 
        # scaleFactorOfFirstFixedSurface as 2. So we must follow 
        # Lets create new coords with 0, 2m infomation.   
        depth_below_land_surface = iris.coords.DimCoord(numpy.array([15000]), 
                         bounds=numpy.array([[0, 30000]]), units=Unit('cm'),
                                       long_name='depth_below_land_surface')
    elif __soilFirstSecondFixedSurfaceUnit__ == 'mm':  
        # We kept here unit as 'mm'. But points are muliplied by
        # 1000 with its  corresponding cm values. Why because, that 
        # 1000 will be factorized (divied) in grib_message by setting 
        # scaleFactorOfFirstFixedSurface as 3 and 
        # scaleFactorOfSecondFixedSurface as 3. So we must follow 
        # this procedure to get correct results.

        # Lets create new coords with 0, 3m infomation.   
        depth_below_land_surface = iris.coords.DimCoord(numpy.array([1500000]), 
                          bounds=numpy.array([[0, 3000000]]), units=Unit('mm'), 
                                        long_name='depth_below_land_surface')    
    else:
        return 
    # end of if __soilFirstSecondFixedSurfaceUnit__ == 'cm':
        
    # add the above created new coords to the cube 
    cube.add_aux_coord(depth_below_land_surface)    
# end of def _createDepthBelowLandSurfaceCoords1Lev():

def _updateDepthBelowLandSurfaceCoords4Levs(depth_below_land_surface):
    # Dr. Saji / UM_Model_DOC suggested that UM produce soil model
    # level number is equivalent to 10cm, 35cm, 1m & 2m. 
    
    global __soilFirstSecondFixedSurfaceUnit__ 

    if __soilFirstSecondFixedSurfaceUnit__ == 'cm':
        # So we kept here unit as 'cm'. But points are muliplied by
        # 100 with its  corresponding cm values. Why because, that 
        # 100 will be factorized (divied) in grib_message by setting 
        # scaleFactorOfFirstFixedSurface as 2 and 
        # scaleFactorOfFirstFixedSurface as 2. So that in grib2 will
        # be able to read as 0.1 m, 0.35m, 1m & 2m. Iris will convert 
        # cm to m while saving into grib2 file. So we must follow 
        # this procedure to get correct results. (tested and suggested for 
        # WRF-Noah model input)
        
        # 1000 cm -> 10 m -> 10 m / 100 (scaleFactorOfFirstFixedSurface = 2) -> 0.1 m
        # 3500 cm -> 35 m -> 35 m / 100 (scaleFactorOfSecondFixedSurface = 2) -> 0.35 m
        # 10000 cm -> 100 m -> 100 m / 100 (scaleFactorOfSecondFixedSurface = 2) -> 1.0 m
        # 30000 cm -> 300 m -> 300 m / 100 (scaleFactorOfSecondFixedSurface = 2) -> 3.0 m
        
        depth_below_land_surface.points = numpy.array([500, 2250, 6750, 20000])
        # we must set the bounds in vertical depths, since we required
        # to mention the four different layers depth properly.
        depth_below_land_surface.bounds = numpy.array([[0, 1000], 
                                   [1000, 3500], [3500,10000],[10000,30000]])
        depth_below_land_surface.units = Unit('cm')
    elif __soilFirstSecondFixedSurfaceUnit__ == 'mm':
        # Here we kept unit as 'mm'. But points are muliplied by
        # 1000 with its  corresponding mm values. Why because, that 
        # 1000 will be factorized (divied) in grib_message by setting 
        # scaleFactorOfFirstFixedSurface as 3 and 
        # scaleFactorOfSecondFixedSurface as 3. So that in grib2 will
        # be able to read as 0.1m, 0.35m, 1m & 3m. Iris will convert 
        # mm to m while saving into grib2 file. So we must follow 
        # this procedure to get correct results.
        # Moreover IMD-MFI model required to be scaling range of 100000. So we 
        # must follow this procedure only (i.e. mm to m conversion and not cm to m conversion) 
        
        # 100000 mm -> 100 m -> 100 m / 1000 (scaleFactorOfFirstFixedSurface = 3) -> 0.1 m
        # 350000 mm -> 350 m -> 350 m / 1000 (scaleFactorOfSecondFixedSurface = 3) -> 0.35 m
        # 1000000 mm -> 1000 m -> 1000 m / 1000 (scaleFactorOfSecondFixedSurface = 3) -> 1.0 m
        # 3000000 mm -> 3000 m -> 3000 m / 1000 (scaleFactorOfSecondFixedSurface = 3) -> 3.0 m
        
        depth_below_land_surface.points = numpy.array([50000, 225000, 675000, 2000000])
        # we must set the bounds in vertical depths, since we required
        # to mention the four different layers depth properly.
        depth_below_land_surface.bounds = numpy.array([[0, 100000], 
                           [100000, 350000], [350000,1000000],[1000000,3000000]])
        depth_below_land_surface.units = Unit('mm')
    # end of if __soilFirstSecondFixedSurfaceUnit__ == 'cm':
    
    depth_below_land_surface.long_name = 'depth_below_land_surface'    
    depth_below_land_surface.standard_name = 'depth'
# end of def _updateDepthBelowLandSurfaceCoords4Levs():

def _convert2VolumetricMoisture(cube, levels=[100.0, 250.0, 650.0, 2000.0]):
    #### Lets convert moisture_content_of_soil_layer into 
    ##  volumetric_moisture_of_soil_layer by divide each layer 
    ## with its layer depth in mm.
    ## Unit also gets changed from Kg/m2 into m3/m3. How ?
    ## voulumetric_soil_moisture = moisture_content_of_soil_layer / (density_of_water x depth_of_soil_layer)
    ## density_of_water is 1000 Kg/m3
    ## depth_of_soil_layer of first layer from 0 to 10 cm = 10/100 m
    ## depth_of_soil_layer of first layer from 10 to 35 cm = 25/100 m
    ## depth_of_soil_layer of first layer from 35 to 100 cm = 65/100 m
    ## depth_of_soil_layer of first layer from 100 to 300 cm = 200/100 m
    
    ## So if we apply the above values of density 1000 Kg/m3 
    ## & depth in meter in the denominator of voulumetric_soil_moisture
    ## equavation, we will endup with just divide first layer 
    ## by 100, second layer by 250, third layer by 650 and 
    ## fourth layer by 2000.
    
    ## By this way, we converted moisture_content_of_soil_layer 
    ## from Kg/m2 into volumetric_soil_moisture_of_layer m3/m3.
    
    ## Reference : "Comparison of the Met Office soil moisture
    ## analyses with SMOS retrievals (2010-2011)", MARCH 2013.
    
    ## Link : http://www.researchgate.net/publication/257940913
    
    print "before volumetirc", cube.data.min(), cube.data.max()
    if isinstance(levels, (list, tuple)):   
        # This block of code for 4 different layers 
        for idx, dval in enumerate(levels):
            cube.data[idx] /= dval
    elif isinstance(levels, float):
        # this block of code for single layer 
        cube.data /= levels
    # end of for idx, denominator in enumerate([...]):
    print "after volumetirc", cube.data.min(), cube.data.max()
    # WRF-WPS requires minimum vlaue as 0.005. If it is < 0.005 then 
    # Noah thorws segmentation error due to low value of soil moisture. 
    # Reference : look at the lines from 1219 t0 1260 in the below link
    # http://www.cisl.ucar.edu/staff/huangwei/WRFV3/dyn_em/module_initialize_real.F.html
    # though the above Noah code replace the <0.005 grid values with 0.005,
    # but it does only for the first time step (say analysis 00hr), and then 
    # model will blow up for the next time step (say forecast 06hr).
    # And either we should do mask grid points < 0.005 or replace with 0.0051.
    # Here we are replacing with 0.0051 since soil moisture masking will not 
    # make proper sense!. so replace the values less than 0.005 with 0.0051.
    cube.data[numpy.ma.logical_and(cube.data > 0.0, cube.data < 0.005)] = 0.0051
    
    # update the units as m3 / m3
    cube.units = Unit('m3 m-3')
    # make sure that standard_name as None, so that it will  
    # not messup with units while writing as grib2. 
    cube.standard_name = None
    # set long name as volumetric_moisture_of_soil_layer, 
    # though its not standard cf name, I made it as 
    # understandable long name which points into volumetirc 
    # grib2 param code in _grib_cf_map.py.
    cube.long_name = 'volumetric_moisture_of_soil_layer'        
# end of def _convert2VolumetricMoisture(cube):

def _convert2WEASD(cube):
    
    # http://www.nrcs.usda.gov/wps/portal/nrcs/detail/or/snow/?cid=nrcs142p2_046155
    if cube.standard_name == 'snowfall_amount':
        cube.standard_name = 'liquid_water_content_of_surface_snow'
        # convert the snow amount data to water equivalent by divide by 10 or 
        # multiply by 0.1.
        # reference link : look above        
        cube.data *= 0.1 
    # end of if cube.standard_name == 'snowfall_amount':
# end of def _convert2WEASD(cube):
    

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
           __fillFullyMaskedVars__,  _reverseLatitude_, __outFileType__, \
           _write2NetcdfFile_, __UMReanalysis__, __end_long_fcst_hour__ 
   
    fpname, hr, varIdx = arg 
    
    if __UMReanalysis__:
        fileName = fpname # keep filename for IMDAA reanalysis
    elif  __UMtype__ == 'global':
        ### if fileName has some extension, then do not add hr to it.
        fileName = fpname + hr.zfill(3) if not '.' in fpname else fpname
    elif  __UMtype__ == 'regional':
        if '.' in fpname:
            fileName = fpname 
        else:
           fileName = fpname if '.' in fpname else fpname + hr.zfill(3) 
        # end of if '.' in pfname:
    # end of if  __UMtype__ == 'global':
    
    fname = os.path.join(_inDataPath_, fileName)        
    inDataPathHour = _inDataPath_.split('/')[-1]  
    inDataPathHour = inDataPathHour if inDataPathHour.isdigit() else None
    # call definition to get variable indices
    varNamesSTASH, fcstHours, doMultiHourlyMean, infile, simulated_hr = getVarInOutFilesDetails(_inDataPath_, fileName, hr)
    
    if not os.path.isfile(fname): 
        print "Error : The file doesn't exists: %s .. \n" %fname
        return  
    # end of if not os.path.isfile(fname): 
    
    if _convertVars_:
        # load only needed variables from this file !
        varNamesSTASH = [vns for vns in varNamesSTASH if vns in _convertVars_]
    
    # load only one varNamesSTASH (used for variable wise parallel conversion) 
    if varIdx: varNamesSTASH = [varNamesSTASH[varIdx]]
    
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
        
    if fpname.startswith(('umglaa', 'umnsaa')) or __outFileType__ == 'fcst':
        dtype = 'fcst'         
        outFileNameStructure = __fcstFileNameStructure__
        start_step_fcst_hour = __fcst_step_hour__
    elif fpname.startswith(('umglca', 'qwqg00', 'umnsa')) or __outFileType__ in ['ana', 'rea']:
        dtype = 'ana'
        outFileNameStructure = __anlFileNameStructure__
        start_step_fcst_hour = __anl_step_hour__
    # end of if fpname.startswith('umglaa'):
    if __outFileType__ in ['rea', 'reanalysis']: dtype = 'rea'
        
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
    if dtype == 'fcst':        
        ### But if we want to set access time point as per out file hour's
        ### ref time, then we can enable the following options. otherwise 
        ### disable it, because 'cbound' will works for ctl file.
        timepoint = 'rbound'        # TESTED, OK, on 05-01-2016
        fcstpoint = 'rbound'        # TESTED, OK, on 05-01-2016
    elif dtype == 'ana':        
        ### But if we want to set access time point as per out file hour's
        ### ref time, then we can enable the following options. otherwise 
        ### disable it, because 'cbound' will works for ctl file.
        if __anl_aavars_reference_time__ == 'shortforecast':
            timepoint = 'lbound'        # TESTED, OK, on 23-02-2016
            fcstpoint = 'lbound'        # TESTED, OK, on 23-02-2016
            ## g2ctl -verf option bring end forecast time bounds to set time in 
            ## ctl file. So we no need to pass options like -0 or -b.
            ## here lbound in both timepoint and fcstpoint will give correct 
            ## time reference and forecast time in both grib2 files and grads 
            ## control files.           # TESTED, OK, on 23-02-2016
        elif __anl_aavars_reference_time__ == 'analysis':
            timepoint = 'rbound'        # TESTED, OK, on 22-03-2016
            fcstpoint = 'lbound'        # TESTED, OK, on 22-03-2016
            ## In this option, we must pass -0 option to g2ctl and gribmap.
            ## Otherwise, it will make 2 time points in ctl file.
            if not __anl_aavars_time_bounds__: 
                # This option applicable only if __anl_aavars_reference_time__ 
                # option set as 'analysis'. This false will remove the time 
                # bounds and make the var as instantaneous one instead of 
                # average/accumulation.
                timebound = False
                fcstbound = False
            # end of if not __anl_aavars_time_bounds__: 
    # end of if dtype == 'fcst':
    
    # Note : if we are not correcting ana, fcst fcstpoint as above, in g2ctl
    # ctl file will has 2 time points. To avoid that we have to tell to g2ctl
    # to use start time bound for analysis and last time bound for fcst, 
    # which brings to  1 time point.
    
    # Define default lat, lon, pressure contraint (None just bring model global data)
    latConstraint, lonConstraint, pressureConstraint, fpConstraint = None, None, None, None
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
            raise ValueError("unable to extract variable %s %s %s" % (varName, varSTASH, infile))
        
        # get the standard_name of variable 
        stdNm = cubes.extract(varConstraint & STASHConstraint)[0].standard_name
        longNm = cubes.extract(varConstraint & STASHConstraint)[0].long_name
        print "stdNm", stdNm, infile
        if stdNm is None and longNm is None:
            print "Unknown variable standard_name for '%s' of %s. So skipping it" % (varName, infile)
            continue
        # end of if stdNm is None and longNm is None:
        print "  Working on variable: %s \n" % stdNm
        
        if __UMReanalysis__:
            simulated_hr = int(__utc__) # lets store the simulated_hr
        else:
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
                        # previously defined in getVarInOutFilesDetails function.
                        fcstHours = numpy.array([fhr[idx] for fhr in fcstHours])
                    print varName,"fcstHours", fcstHours
            # end of if (varName, varSTASH) in [...]:
            if (varName, varSTASH) in [('surface_downwelling_shortwave_flux_in_air', 'm01s01i235')]:
                if dtype == 'ana' and fileName == 'umglca_pe000':
                    fcstHours = numpy.array([0.5, 1.5, 2.5, 3.5, 4.5, 5.5])
                    
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
                    if __UMtype__ == 'global':
                        if __fcst_step_hour__ == 6:
                            fcstHours = numpy.arange(24).reshape(4, 6) + int(fileName[-3:]) + 0.5
                        elif __fcst_step_hour__ == 24:
                            # precipitation_amount should be from 03z till next day 03z to make it as 
                            # 24 hourly accumulation, because IMD merged rainfall data starts from
                            # 03z to next day 03z.
                            fcstHours = [numpy.arange(3, 27, 1) + int(fileName[-3:]) + 0.5]
                            # get next day file to access next day 03z hour data 
                            infile2 = infile[:-3] + str(int(hr)+24).zfill(3)
                            cubes = getCubeData([infile, infile2])
                            
                    elif __UMtype__ == 'regional':
                        fhr1 = int(fileName[-3:])
                        fcstHours = numpy.arange(0., 6., 0.25).reshape(6, 4) + fhr1 + 0.125
                    print varName, "fcstHours ", fcstHours, int(fileName[-3:])
                elif dtype == 'ana':
                    # for analysis pe file, and this varibale we need to set the 
                    # extract time as follows. 
                    # the cube contains data of every 1-hourly accumutated.
                    # but we need to make only every 6th hourly accumutated.
                    fcstHours = numpy.array([(0, 1, 2, 3, 4, 5)]) + 0.5 # required since NCUM 10.2 onwards
                    if __anl_step_hour__ == 1: fcstHours = numpy.array([0, 1, 2, 3, 4, 5]) + 0.5
                        
                    if __UMtype__ != 'regional':
                        ana_precip_infile, simulated_hr = __getTodayOrYesterdayInfile__(_inDataPath_, fileName)    
                        if ana_precip_infile != infile: 
                            cubes = getCubeData(ana_precip_infile)
                            print varName, "loaded from file, ", ana_precip_infile
                            print "simulated_hr = ", simulated_hr
                    # end of if ana_infile != infile:               
            # end of if (varName, varSTASH) in _accumulationVars_:
        # end of if __UMReanalysis__:
        print "simulated_hr----", simulated_hr        
        # define (simulated_hr) forecast_reference_time constraint
        fcstRefTimeConstraint = iris.Constraint(forecast_reference_time=PartialDateTime(hour=int(simulated_hr)))
        if __LPRINT__: print fcstRefTimeConstraint
        if __UMtype__ == 'regional' and int(hr) >= 72 and __end_long_fcst_hour__ > 72: 
            fcstHours = fcstHours[:3] # extract upto 75th hour only.
            # CAUTION : This __end_long_fcst_hour__ > 72 checking will be correct if serially given 
            # process from 1-75. it will create 73, 74, 75 without any problem.
            # But 67 to 72 grib2 files, especially 72th hour will make problem because of slicing [:3]
            # Here we must check >= 72, becase rainfall variables need it.
        print "fcstHours++", fcstHours, hr, __UMtype__
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
            
            if __anl_step_hour__ == 3 and inDataPathHour == '00' and fhr == 0 \
                                            and fpname.startswith('umglca_pe'):
                if (varName, varSTASH) in [('air_pressure_at_sea_level', 'm01s16i222'), 
                            ('surface_air_pressure', 'm01s00i409'),]:
                    # these vars taken already from qwqg00.pp0 file. 
                    continue                    
            # end of if __anl_step_hour__ == 3 and fhr == 0:
            
            if fhr is not None:
                # make forecast_period constraint
                fpConstraint = iris.Constraint(forecast_period=fhr)
                # IMDAA requirements
                if __UMReanalysis__:
                    if 'flux' in varName and not varName == 'convective_snowfall_flux':
                        umrfhr = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
                        fpConstraint = iris.Constraint(forecast_period=umrfhr)
                    if 'amount' in varName:
                        umrfhr = lambda cell: 0 <= cell <= 6.0
                        fpConstraint = iris.Constraint(forecast_period=umrfhr)
                    if varName in ['convective_snowfall_flux', 'snowfall_amount']:
                        umrfhr = [1., 2., 3., 4., 5., 6.]
                        fpConstraint = iris.Constraint(forecast_period=umrfhr)
                # end of if __UMReanalysis__:
                       
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
                                    fcstRefTimeConstraint & fpConstraint &
                                    latConstraint & lonConstraint)
            # end of if __anl_step_hour__ == 3 and fhr == 1.5:
            print varConstraint , STASHConstraint ,  fcstRefTimeConstraint , fpConstraint ,       latConstraint , lonConstraint
            if not tmpCube: raise ValueError("unable to extract variable %s %s %s %s" % (varName, varSTASH, str(fhr), infile))
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
            
            if not __UMReanalysis__:            
                if (varName, varSTASH) == ('snowfall_amount', 'm01s00i023'):
                    # the snowfall_amount need to be changed as 
                    # liquid_water_content_of_surface_snow by convert it into
                    # water equivalent of snow amount.                    
                    _convert2WEASD(tmpCube)
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
                    tmpCube = cubeAverager(tmpCube, action, dt='1 hour', 
                                actionIntervals=str(start_step_fcst_hour)+' hour', 
                                               tpoint=timepoint, fpoint=fcstpoint, 
                                             tbounds=timebound, fbounds=fcstbound)
                # end of if doMultiHourlyMean and tmpCube.coords('forecast_period')[0].shape[0] > 1:     
            # end of if not __UMReanalysis__:
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
            
            if (varName, varSTASH) in _precipVars_:
                # Since we are not using 'mask' option for extrapolate while 
                # doing linear regrid, which bring -ve values after regrid in 
                # extrapolated grids. So lets make it as 0 as minimum value.
                regdCube.data[regdCube.data < 0.0] = 0.0
            # end of if (varName, varSTASH) in _precipVars_:
            
            if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
                regdCube.data[regdCube.data > 0] = 1                
            # end of if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
            
            if exmode == 'mask':
                # For the above set of variables we shouldnot convert into 
                # masked array. Otherwise its full data goes as nan.                
                # convert data into masked array
                regdCube.data = numpy.ma.masked_array(regdCube.data, 
                                    dtype=numpy.float64, fill_value=9.999e+20) 
                
                if (varName, varSTASH) in [('soil_moisture_content', 'm01s08i208'),
                                           ('moisture_content_of_soil_layer', 'm01s08i223'),
                                           ('sea_ice_area_fraction', 'm01s00i031'),
                                           ('sea_ice_thickness', 'm01s00i032'),]:
                        # We should assign 0 instead 1e-15 only for this var!
                        regdCube.data[regdCube.data <= 1e-15] = 0.0
                        regdCube.data[regdCube.data < 0.0] = 0.0
                elif (varName, varSTASH) in [('soil_temperature', 'm01s03i238'), 
                                       ('soil_temperature', 'm01s08i225')]:
                    # We should mask 1e-15 only for this var!
                    # because 0 will not make sense when temperature unit is Kelvin
                    regdCube.data = numpy.ma.masked_less_equal(regdCube.data, 1e-15)
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
            print "after regrid", varName, regdCube.data.min(), regdCube.data.max() 
            if __LPRINT__: print "To shape", regdCube.shape  
            regdCube.attributes = tmpCube.attributes
            if __LPRINT__: print "set the attributes back to regdCube"              
            if __LPRINT__: print "regdCube => ", regdCube
            # get the regridded lat/lons
            stdNm, stash, fcstTm, refTm, lat1, lon1 = getCubeAttr(regdCube)
            if __LPRINT__: print "Got attributes from regdCube"
            # save the cube in append mode as a grib2 file       
            if __UMReanalysis__:
                hr = '00'
            elif fcstTm.bounds is not None:
                # (need this for pf files)
                if dtype == 'ana':
                    # this is needed for analysis 00th simulated_hr
                    # get the first hour from bounds
                    if __anl_step_hour__ == 1: 
                        hr = int(fhr)
                    elif __anl_step_hour__ == 3:                        
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
                    if (varName, varSTASH) in _accumulationVars_ and __fcst_step_hour__ == 24:
                        # just subtract 3 hour. so that file name will be consistent with other 
                        # variable, file names.
                        hr = str(int(fcstTm.bounds[-1][-1]) - 3)   
                
                if __LPRINT__: print "Bounds comes in ", hr, fcstTm.bounds, fileName                        
            else:
                # get the fcst time point 
                # this is needed for analysis/forecast 00th simulated_hr
                hr = str(int(fcstTm.points))
                if __LPRINT__: print "points comes in ", hr, fileName 
            # end of if fcstTm.bounds:
            if dtype == 'ana': hr = str(int(hr) + int(__utc__))   # IMPORTANT
            # generate the out file name based on actual informations                                 
            outFn = __genAnlFcstOutFileName__(outFileNameStructure, 
                                 outFnIndecies, _current_date_, hr, 
                                           __utc__, _preExtension_) 
            # get the file full name except last extension, for the purpose
            # of writing intermediate nc files
            ofname = outFn.split(fileExtension)[0]                    
            ncfile = False
            if regdCube.coords('soil_model_level_number') and __UMReanalysis__:
                if (varName, varSTASH) == ('downward_heat_flux_in_soil', 'm01s03i202'):
                    if len(regdCube.coords('soil_model_level_number')[0].points) == 1:
                        # just remove this single 0th level coords
                        # reason : couldnt write back properly.
                        regdCube.remove_coord('soil_model_level_number')
                        
            if regdCube.coords('soil_model_level_number') or regdCube.coords('depth'):
                # NOTE : THIS SECTION WILL WORKS ONLY FOR SOIL MOISTURE AND
                # SOIL TEMPERATUE AT 4 LAYERS, NOT FOR SINGLE LAYER OR 
                # NOT FOR Root zone Soil Moisture Content !!!
                 
                # Get soil_model_level_number coords from the cube.
                # We need to update this variable, which will be replicated
                # in the cube attributes. By default iris-1.9 will not 
                # support to handle soil_model_level_number, so we need to 
                # tweak it by following way.
                depth_below_land_surface = regdCube.coords('soil_model_level_number')
                if not depth_below_land_surface:
                    depth_below_land_surface = regdCube.coords('depth')
                
                depth_below_land_surface = depth_below_land_surface[0]
                _updateDepthBelowLandSurfaceCoords4Levs(depth_below_land_surface)
                if __LPRINT__: print "depth_below_land_surface", depth_below_land_surface
                
                if (regdCube.standard_name == 'moisture_content_of_soil_layer') and not __UMReanalysis__:
                    # pass the vertical layer depth in millimeter
                    _convert2VolumetricMoisture(regdCube, 
                                        levels=[100.0, 250.0, 650.0, 2000.0])
                    print "converted four layer soil moisture to volumetric"                
                    # We need to save this variable into nc file, why because
                    # if we saved into grib2 and then re-read it while re-ordering
                    # variables, iris couldnt load variables with 
                    # depth_below_land_surfacer properly. We need to touch the 
                    # _load_rules. So for timebeing, we saved it as seperate nc 
                    # file. In iris-1.9 we couldnt append more variables into 
                    # nc file. so we saved into muliple individual nc files, only
                    # those who have depth_below_land_surface and will be deleted
                    # after inserted properly into orderd grib2 files.
                    ncfile = True
                # end of if regdCube.standard_name == 'moisture_content_of_soil_layer':                
                print "after soil_model_level_number", regdCube.data 
            # end of if regdCube.coords('soil_model_level_number'):
            
            if (varName, varSTASH) == ('soil_moisture_content', 'm01s08i208'):
                # NOTE : THIS SECTION WILL WORKS ONLY FOR SINGLE LAYERED 
                # Root zone Soil Moisture Content, NOT FOR 4 LAYERS.
                
                # By default this variable doesn't have any vertical coords 
                # inforomation. So we must add explicitly by ourself.
                _createDepthBelowLandSurfaceCoords1Lev(regdCube)
                if not __UMReanalysis__:
                    # Convert this into volumetirc soil moisture. This varibale
                    # vertical level at 2meter in millimeter.
                    _convert2VolumetricMoisture(regdCube, levels=3000.0)
                    print "converted single layer soil moisture to volumetric"
                    ncfile = True
            # end of if (varName, varSTASH) in (...):
            
            if (varName, varSTASH) in [('convective_rainfall_amount', 'm01s05i201'),
                            ('convective_snowfall_amount', 'm01s05i202'),
                            ('precipitation_amount', 'm01s05i226'),
                            ('stratiform_rainfall_amount', 'm01s04i201'),
                            ('stratiform_snowfall_amount', 'm01s04i202'),] and __UMReanalysis__:
                ### This should be done only for IMDAA reanalysis project.
                print regdCube.data.min(), regdCube.data.max()
                clength = regdCube.shape[0]
                # subtract from previously cummulated to make it as hourly accumulated, 
                # instead of writing as hourly cummulated.
                for ci in range(clength-1, 1, -1): regdCube.data[ci] -= regdCube.data[ci-1]
                
                # removing cummulative time informations
                regdCube.remove_coord('forecast_period')
                regdCube.remove_coord('time')
                
                # here the snowfall_amount extract from 0 to 9 timestep
                snowvarCon = iris.Constraint(name='snowfall_amount')
                snowSTASHCon = iris.AttributeConstraint(STASH='m01s00i023')
                snowVar = cubes.extract(snowvarCon & snowSTASHCon)[0]
                # adding time information same as snowfall_amount
                regdCube.add_dim_coord(snowVar.coord('time'), 0)
                regdCube.add_aux_coord(snowVar.coord('forecast_period'), 0)
                
                # extract only 6 hours (hourly) time steps in all 4 cycles, so that it will become 
                # 24 hours (hourly) time steps.
                regdCube = regdCube.extract(iris.Constraint(forecast_period=[1, 2, 3, 4, 5, 6]))
            # end of if (varName, varSTASH) ... and __UMReanalysis__:
            
            
            if (varName, varSTASH) in _ncfilesVars_:
                # other than soil_model_level_number, few variables may be 
                # need to write into nc file and then convert to grib2. why 
                # because of duplicate grib param id (but actually not, if 
                # we implement typeOfFirstFixedSurface). so we are stoing into 
                # nc file, then load into memory (cf_standard_name) while 
                # re-ordering, followed by save into grib2 file. cf -> grib2 
                # dictionary may not throw error, due to different key cfname.
                ncfile = True                
            # end of if (varName, varSTASH) in _ncfilesVars_:
            
            if _write2NetcdfFile_:
               ncfile = True
               # store all vars into ncfileVars list
            # generate intermediate nc filename 
            if ncfile: outFn = varSTASH + '_'+ ofname + '.nc' 
            # generate complete outfile path 
            outFn = os.path.join(_opPath_, outFn)
            print "Going to be save into ", outFn
            print "regfCube =====", regdCube
            if ncfile:
                try:
                    # save nc files . writing individual nc files with stash name in paralelly. 
                    # so no need to lock the file.
                    iris.fileformats.netcdf.save(regdCube, outFn,netcdf_format="NETCDF4")            
                except Exception as e:
                    print "ALERT !!! Error while saving!! %s" % str(e)
                    print " So skipping this without saving data"
                    continue            

            else:
                try:                
                    # _lock_ other threads / processors from being access same file 
                    # to write other variables
                    _lock_.acquire() 
                    iris.fileformats.grib.save_grib2(regdCube, outFn, append=True) # save grib2 file 
                except Exception as e:
                    print "ALERT !!! Error while saving!! %s" % str(e)
                    print " So skipping this without saving data"
                    continue
                finally:
                    # release the _lock_, let other threads/processors access this file.
                    _lock_.release()
                # end of try:
            # end of if ncfile:
            print "saved"            
            # make memory free 
            del regdCube, tmpCube
        # end of for fhr in fcstHours:
    # end of for varName, varSTASH in varNamesSTASH:
    # make memory free
    del cubes
    
    print "  Time taken to convert the file: %8.5f seconds \n" %(time.time()-_startT_)
    print " Finished converting file: %s into grib2 format for fcst file: %s \n" %(fileName,hr)
# end of def regridAnlFcstFiles(fname):

def tweaked_messages(cubeList):
    global _ncmrGrib2LocalTableVars_, _aod_pseudo_level_var_, __UMtype__, \
           __setGrib2TableParameters__, __soilFirstSecondFixedSurfaceUnit__           
    
    for cube in cubeList:
        for cube, grib_message in iris.fileformats.grib.as_pairs(cube): #save_pairs_from_cube(cube):
            print "Tweaking begin ", cube.standard_name
            # post process the GRIB2 message, prior to saving
            gribapi.grib_set_long(grib_message, "centre", 29) # RMC of India
            gribapi.grib_set_long(grib_message, "subCentre", 0) # No subcentre
            print "reset the centre as 29"
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
                print 'reset typeOfTimeIncrement as 2 for', cube.standard_name
                
                if __UMtype__ == 'regional':
                    # fixing floating precesion point problem
                    forecast_period = cube.coords('forecast_period')[0]
                    forecast_period.points = numpy.round(forecast_period.points, 3)
                    forecast_period.bounds = numpy.round(forecast_period.bounds, 3)
                    print "forecast_period = ", forecast_period
                # end of if __UMtype__ == 'regional':
                
            # end of if cube.coord("forecast_period").bounds is not None:
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
                
                # here str conversion is essential to avoid checking 'cloud' in None
                # (for long_name in some case), which will throw error.
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
            # end of if cube.standard_name or ...:
            if __setGrib2TableParameters__:
                # This user defined parameters must be at last of this function!
                for key, val in __setGrib2TableParameters__:
                    gribapi.grib_set_long(grib_message, key, val)
                    print "set user defined grib2table parameter ('%s', %s)" % (key, val)
            # end of if __setGrib2TableParameters__:
            print "Tweaking end ", cube.standard_name
            
            yield grib_message
        # end of for cube, grib_message in iris.fileformats.grib.save_pairs_from_cube(cube):
    # end of for cube in cubeList:
# end of def tweaked_messages(cube):

def doShuffleVarsInOrder(fpath):
    """
    order the variables and create new grib2 files;
    delete the older shuffled variables grib2 files.
    create ctl, idx files using g2ctl.pl, gribmap scripts for the ordered grib2 files.
    
    Arulalan/T
    11-12-2015
    """
    global  _orderedVars_, _preExtension_, _ncfilesVars_, _inDataPath_, \
           _maskOverOceanVars_, _aod_pseudo_level_var_, _createGrib2CtlIdxFiles_, \
           _createGrib1CtlIdxFiles_, _convertGrib2FilestoGrib1Files_, _short_name_, \
           _requiredLat_, _convertVars_, __outFileType__, __grib1FilesNameSuffix__, \
           __removeGrib2FilesAfterGrib1FilesCreated__, _removeVars_, cnvgrib, \
           __fcst_step_hour__, __anl_step_hour__, g2ctl, grib2ctl, gribmap, \
           __anl_aavars_reference_time__, _reverseLatitude_, __wgrib2Arguments__, \
           _write2NetcdfFile_, __UMReanalysis__
    
    print "doShuffleVarsInOrder Begins", fpath
    # need to store the ordered variables in this empty list
    orderedVars = []
    ncloaddic = {}
    ncloadedfiles = []
    
    if _write2NetcdfFile_:
        for (varName, varSTASH) in _convertVars_:
            # load and store all intermediate nc files
            ncfpath = varSTASH + '_' + '.'.join(fpath.split('.')[:-1]) + '.nc'
            if not os.path.isfile(ncfpath): continue
            if varSTASH not in ncloaddic:
                try:
                    ncloaddic['varSTASH'] = iris.load(ncfpath)
                    ncloadedfiles.append(ncfpath)
                except Exception as e:
                    print "ALERT!!! ERROR!!! couldn't read nc file to re-order", e
                    return
                # end of try:             
            # end of if varSTASH not in ncloaddic:
            # define variable name constraint
            varConstraint = iris.Constraint(name=varName)
            # define varibale stash code constraint
            STASHConstraint = iris.AttributeConstraint(STASH=varSTASH)
            var = ncloaddic['varSTASH'].extract(varConstraint & STASHConstraint)[0]
            if var and varName in _short_name_:
                # set shortname to var_name which will be used to write 
                # into nc file (essential to be accessed by grads)!
                var.var_name = _short_name_[varName]
            orderedVars.append(var)
        # end of for (varName, varSTASH) in _convertVars_:  

    elif os.path.isfile(fpath):
        try:        
            f = iris.load(fpath, callback=update_cf_standard_name) # load intermediate grib2 file
        except gribapi.GribInternalError as e:
            if str(e) == "Wrong message length":
                print "ALERT!!!! ERROR!!! Couldn't read grib2 file to re-order", e
            else:
                print "ALERT!!! ERROR!!! couldn't read grib2 file to re-order", e
            return 
        except Exception as e:
            print "ALERT!!! ERROR!!! couldn't read grib2 file to re-order", e
            return
  	 
        print "f = ", f
        # get only the pressure coordinate variables
        unOrderedPressureLevelVarsList = [i for i in f if len(i.coords('pressure')) == 1]
        # get only the non pressure coordinate variables
        unOrderedNonPressureLevelVarsList = list(set(f) - set(unOrderedPressureLevelVarsList))
    
        # generate dictionary (standard_name, STASH) as key and cube variable as value
        unOrderedPressureLevelVars = {}
        for i in unOrderedPressureLevelVarsList:
            name = i.standard_name if i.standard_name else i.long_name
            unOrderedPressureLevelVars[name] = i
        
        unOrderedNonPressureLevelVars = {}
        for i in unOrderedNonPressureLevelVarsList:
            name = i.standard_name if i.standard_name else i.long_name
            unOrderedNonPressureLevelVars[name] = i   
            
        if _convertVars_:
            # user has passed their own ordered and limited vars 
            orderedVarsList = _convertVars_
        else:
            # use inbuilt ordered list from this module itself
            orderedVarsList = _orderedVars_['PressureLevel'] + _orderedVars_['nonPressureLevel']
        
        for (varName, varSTASH) in orderedVarsList:
            # skip if user specified var not in pressure level vars list 
            if not (varName, varSTASH) in _orderedVars_['PressureLevel']: continue
            # got pressure vars, add to ordered final vars list  
            if varName in unOrderedPressureLevelVars: orderedVars.append(unOrderedPressureLevelVars[varName])
        # end of for name, STASH in _orderedVars_['PressureLevel']:
        
        nonpressurevarslist = []  # CAUTION: Try to omit duplicate wind 50m and 10m twice.
        for (varName, varSTASH) in orderedVarsList:
            # skip if user specified var not in non-pressure level vars list 
            if not (varName, varSTASH) in _orderedVars_['nonPressureLevel']: 
                print "Error : (%s, %s) not available in _orderedVars_. Pl add it!" % (varName, varSTASH)
                continue
            # got non-pressure vars, add to ordered final vars list  
            if varName in unOrderedNonPressureLevelVars: 
                if not varName in nonpressurevarslist:
                    orderedVars.append(unOrderedNonPressureLevelVars[varName])
                    nonpressurevarslist.append(varName)
            elif (varName, varSTASH) in _ncfilesVars_:
                ## generate nc file name
                ncfpath = varSTASH + '_' + '.'.join(fpath.split('.')[:-1]) + '.nc'
                if not os.path.isfile(ncfpath): continue
                if varSTASH not in ncloaddic:
                    try:
                        ncloaddic['varSTASH'] = iris.load(ncfpath)
                        ncloadedfiles.append(ncfpath)
                    except Exception as e:
                        print "ALERT!!! ERROR!!! couldn't read nc file to re-order", e
                        return 
                    # end of try:             
                # end of if varSTASH not in ncloaddic:
                # define variable name constraint
                varConstraint = iris.Constraint(name=varName)
                # define varibale stash code constraint
                STASHConstraint = iris.AttributeConstraint(STASH=varSTASH)
                var = ncloaddic['varSTASH'].extract(varConstraint & STASHConstraint)
            
                if var: 
                    # apped the ordered / corrected vars into the list, which will  
                    # be going to saved into grib2/nc files by tweaking it further!   
                    if varName in _short_name_:
                        pvar = var[0]
                        # set shortname to var_name which will be used to write 
                        # into nc file (essential to be accessed by grads)!
                        pvar.var_name = _short_name_[varName]
                    if varName in _aod_pseudo_level_var_:
                        for plev, pval in _aod_pseudo_level_var_[varName]:
                            pvar = var[0].extract(iris.Constraint(pseudo_level=plev))
                            # set standard_name as None
                            pvar.standard_name = None
                            # set long_name as standard_name + '_at_micronwavelength'
                            # so that _grib_cf_map will be able to identify local 
                            # table grib2 param code. 
                            pvar.long_name = varName + '_at_%sum' % pval
                            orderedVars.append(pvar)
                    else:
                        orderedVars.append(var[0])
                # end of if var:
        # end of for (varName, STASH) in orderedVarsList:
    else:
        print "In file doesn't exists", fpath
        return
    # end of if _write2NetcdfFile_:

    # store the land_binary_mask data into temporary variable
    land_binary_mask_var = [var for var in orderedVars 
                            if var.standard_name == 'land_binary_mask']
        
    # Define lat min, max of 60S to 60N and 30S to 30N
    lat_60N_start_val, lat_60N_end_val = -60, 60
    lat_30N_start_val, lat_30N_end_val = -30, 30 
        
    if _requiredLat_ is not None:
        # User has defined their own sub region.
        # So lets set min, max lat as user defined in case it falls within 
        # subdomain of 60S to 60N and 30S to 30N.
        if _requiredLat_[0] > lat_60N_start_val: lat_60N_start_val = _requiredLat_[0]
        if _requiredLat_[-1] < lat_60N_end_val: lat_60N_end_val = _requiredLat_[-1]
        if _requiredLat_[0] > lat_30N_start_val: lat_30N_start_val = _requiredLat_[0]
        if _requiredLat_[-1] < lat_30N_end_val: lat_30N_end_val = _requiredLat_[-1]
        # If user defined regions is out of 60S to 60N region, then we no need 
        # to adjust  the soil moisture min with 0.0051 and soil temperature 
        # min with its next mean.
        if _requiredLat_[0] < -60 or _requiredLat_[0] > 60: lat_60N_start_val = None
        # in case we endup with lat_60N_start_val as None, then we no need to 
        # correct min values of soil moisture and temperature.
    # end of if _requiredLat_ is not None:
        
    if (_maskOverOceanVars_ and land_binary_mask_var and 
            lat_60N_start_val is not None and lat_60N_end_val is not None) and not __UMReanalysis__:

        land_binary_mask = land_binary_mask_var[0].data < 1
        # here we are masking less than 1. we can do just simply == 0 also, 
        # but somehow it retains fraction values between 0 to 1. To get 
        # ride out of this fraction values, just mask out < 1.
        # get the shapes
        lsh = land_binary_mask.shape
        
        if _reverseLatitude_:
            # Just reverse latitudes before extract the actual subdomains
            lat_60N_start_val, lat_60N_end_val = lat_60N_end_val, lat_60N_start_val
            lat_30N_start_val, lat_30N_end_val = lat_30N_end_val, lat_30N_start_val
            # Define constraint to extract latitude from 60S to 60N
            lat_60S_60N = iris.Constraint(latitude=lambda cell: lat_60N_start_val > cell > lat_60N_end_val)
            lat_30S_30N = iris.Constraint(latitude=lambda cell: lat_30N_start_val > cell > lat_30N_end_val)
        else:
            # Define constraint to extract latitude from 60S to 60N
            lat_60S_60N = iris.Constraint(latitude=lambda cell: lat_60N_start_val < cell < lat_60N_end_val)
            lat_30S_30N = iris.Constraint(latitude=lambda cell: lat_30N_start_val < cell < lat_30N_end_val)
        # end of if _reverseLatitude_:
        
        for vidx, var in enumerate(orderedVars):
            vname = var.standard_name if var.standard_name else var.long_name
            if vname in _maskOverOceanVars_:    
                # Lets reset zero values lies within 60S to 60N band
                # with 0.0051, before ocean region has been masked.
                # Now extract data only lies between 60S to 60N
                var_60S_60N = var.extract(lat_60S_60N)
                print "before resetting ", vname, var_60S_60N.data.min(), var_60S_60N.data.max()
                if vname == 'volumetric_moisture_of_soil_layer':
                    # reset the minimum values as 0.01
                    var_60S_60N.data[var_60S_60N.data < 0.005] = 0.0051
                    print "resetting min of volumetric_moisture_of_soil_layer as ", var_60S_60N.data.min()
                elif vname == 'soil_temperature':
                    # We should assign min of extra tropical band !
                    # because polar minimum might have been assigned 
                    # while extracting data (function regridAnlFcstFiles).
                    # So lets re-set here!
                    # zero will not make sense when temperature unit is Kelvin
                    # get tropical data 
                    var_30S_30N = var.extract(lat_30S_30N) 
                    # find next mean value of tropical data 
                    nmean = numpy.ma.masked_less_equal(var_30S_30N.data, var_30S_30N.data.min()).mean()
                    # make memory free 
                    del var_30S_30N
                    # set mean value (of tropical data 30S to 30N) as 
                    # min value full extra tropical data (60S to 60N).
                    # This will solve the abnormal temperature values over 
                    # small islands in tropical ocean regions.
                    var_60S_60N.data[var_60S_60N.data <= var_60S_60N.data.min()] = nmean
                    print  "resetting min of soil_temperature as nmean", nmean
                # end of if vname == 'volumetric_moisture_of_soil_layer':
                
                # extract latitude coords of 60S to 60N data 
                lat_60S_60N_points = var_60S_60N.coords('latitude')[0].points
                # get its start and end lat values of 60S and 60N
                lat_60S_start, lat_60N_end = lat_60S_60N_points[0], lat_60S_60N_points[-1]
                # get the original global data latitude points 
                originalLat = var.coords('latitude')[0].points.tolist()
                # find the 60S index in original global latitude
                lat_60S_index = originalLat.index(lat_60S_start)
                # find the 60N index in original global latitude
                lat_60N_index = originalLat.index(lat_60N_end) + 1
                # Lets insert the updated data (0.0051) within the 
                # original global data itself.
                # Now Lets do masking over Ocean regions!
                vsh = var.shape
                if lsh != vsh:
                    # first dimension points 4 layer depth_below_land_surface
                    # so second dimension points latitude.
                    var.data[:, lat_60S_index: lat_60N_index, :] = var_60S_60N.data                        
                    # get the ocean mask by masking 0s of land_binary_mask 
                    # (0-sea, 1-land) and set it to the required variables. 
                    land_binary_mask_grown = land_binary_mask.reshape(1, lsh[0], lsh[-1])
                    land_binary_mask_grown = land_binary_mask_grown.repeat(vsh[0], axis=0)                    
                    var.data = numpy.ma.masked_where(land_binary_mask_grown, var.data)
                else:    
                    # single layer only. so first dimension points latitude
                    var.data[lat_60S_index: lat_60N_index, :] = var_60S_60N.data
                    # get the ocean mask by masking 0s of land_binary_mask 
                    # (0-sea, 1-land) and set it to the required variables. 
                    var.data = numpy.ma.masked_where(land_binary_mask, var.data)
                # end of if lsh != vsh:
                
                print "updated ocean masked vars",var.data.min(), var.data.max()
        # end of for vidx, var in enumerate(orderedVars):
    # end of if _maskOverOceanVars_ and ...:
    
    # removing land_binary_mask_var from out files if it is forecast grib2 file
    # why do we need to repeat the same static variables in all the 
    # forecast files... So removing it, but keeps in analysis file.
    if __outFileType__ in ['prg', 'fcst'] and land_binary_mask_var and \
                                  __fcst_step_hour__ in [6]: 
        # remove only for 6 hourly ncum post prodction. Not for others!
        # say for 3 hourly hycom model input landsea binary mask needed in all
        # forecast files.
        orderedVars.remove(land_binary_mask_var[0])
    # But still we have to use land_binary_mask variable to set 
    # ocean mask for the soil variables. Thats why we included it in vars list.
    
    oidx = None
    if ('surface_upwelling_shortwave_flux_in_air', 'None') in _convertVars_:
        # find the index in _convertVars_
        idx = _convertVars_.index(('surface_upwelling_shortwave_flux_in_air', 'None'))
        # adjust the current index by subtract 1, because in previous insertion 
        # causes order index increased by 1.
        idx = idx-1 if (idx and oidx is None) else idx
        oidx = idx
        # store the surface_net_downward_shortwave_flux data into temporary variable
        surface_net_downward_shortwave_flux = [var for var in orderedVars 
               if var.standard_name == 'surface_net_downward_shortwave_flux']    
        if not surface_net_downward_shortwave_flux:
            raise ValueError("Can not calculate surface_upwelling_shortwave_flux, because unable to load surface_net_downward_shortwave")    
        # store the surface_downwelling_shortwave_flux_in_air data into temporary variable
        surface_downwelling_shortwave_flux = [var for var in orderedVars 
               if var.standard_name == 'surface_downwelling_shortwave_flux_in_air']
        if not surface_downwelling_shortwave_flux:
            raise ValueError("Can not calculate surface_upwelling_shortwave_flux, because unable to load surface_downwelling_shortwave_flux")
        # calculate 'surface_upwelling_shortwave_flux' by subtract 'surface_net_downward_shortwave_flux'
        # from 'surface_downwelling_shortwave_flux'       
        surface_upwelling_shortwave_flux = cubeAddSubtractor(surface_downwelling_shortwave_flux[0], 
                                           surface_net_downward_shortwave_flux[0],
                                           action='sub', 
                       standard_name='surface_upwelling_shortwave_flux_in_air',
                                                              removeSTASH=True)
        # store the 'surface_upwelling_shortwave_flux' into orderedVars
        orderedVars.insert(idx, surface_upwelling_shortwave_flux)
    # end of if ('surface_upwelling_shortwave_flux_in_air', 'None') in _convertVars_:
    
    if ('surface_upwelling_longwave_flux_in_air', 'None') in _convertVars_:
        # find the index in _convertVars_
        idx = _convertVars_.index(('surface_upwelling_longwave_flux_in_air', 'None'))
        # adjust the current index by subtract 1, because in previous insertion 
        # causes order index increased by 1.
        idx = idx-1 if (idx and oidx is None) else idx
        oidx = idx
        # store the surface_net_downward_longwave_flux data into temporary variable
        surface_net_downward_longwave_flux = [var for var in orderedVars 
               if var.standard_name == 'surface_net_downward_longwave_flux'] 
        if not surface_net_downward_longwave_flux:
            raise ValueError("Can not calculate surface_upwelling_longwave_flux, because unable to load surface_downwelling_longwave_flux")           
        # store the surface_downwelling_longwave_flux data into temporary variable
        surface_downwelling_longwave_flux = [var for var in orderedVars 
               if var.standard_name == 'surface_downwelling_longwave_flux']
        if not surface_downwelling_longwave_flux:
            raise ValueError("Can not calculate surface_upwelling_longwave_flux, because unable to load surface_downwelling_shortwave_flux")
        # calculate 'surface_upwelling_longwave_flux' by subtract 'surface_net_downward_longwave_flux'
        # from 'surface_downwelling_longwave_flux'       
        surface_upwelling_longwave_flux = cubeAddSubtractor(surface_downwelling_longwave_flux[0], 
                                           surface_net_downward_longwave_flux[0], 
                                           action='sub',
                       standard_name='surface_upwelling_longwave_flux_in_air',
                                                              removeSTASH=True)
        # store the 'surface_upwelling_longwave_flux' into orderedVars
        orderedVars.insert(idx, surface_upwelling_longwave_flux)
    # end of if ('surface_upwelling_longwave_flux_in_air', 'None') in _convertVars_:
    
    if ('precipitation_amount', 'None') in _convertVars_:
        print "Calculating, ('precipitation_amount', 'None')"
        # find the index in _convertVars_
        idx = _convertVars_.index(('precipitation_amount', 'None'))
        # adjust the current index by subtract 1, because in previous insertion 
        # causes order index increased by 1.
        idx = idx-1 if (idx and oidx is None) else idx
        oidx = idx
        # store the stratiform_snowfall_amount data into temporary variable
        stratiform_snowfall_amount = [var for var in orderedVars 
               if var.standard_name == 'stratiform_snowfall_amount'] 
        if not stratiform_snowfall_amount:
            raise ValueError("Can not calculate precipitation_amount (regional), because unable to load stratiform_snowfall_amount")           
        # store the stratiform_rainfall_amount data into temporary variable
        stratiform_rainfall_amount = [var for var in orderedVars 
               if var.standard_name == 'stratiform_rainfall_amount']
        if not stratiform_rainfall_amount:
            raise ValueError("Can not calculate precipitation_amount (regional), because unable to load stratiform_rainfall_amount")
        # calculate 'precipitation_amount' by adding 'stratiform_rainfall_amount'
        # and 'stratiform_snowfall_amount' together.      
        precipitation_amount = cubeAddSubtractor(stratiform_rainfall_amount[0], 
                                           stratiform_snowfall_amount[0], 
                                           action='add',
                                           standard_name='precipitation_amount',
                                                              removeSTASH=True)
        # lets fix -ve precipitation as 0.0        
        precipitation_amount.data[precipitation_amount.data <= 0.0] = 0.0
        
        # store the 'precipitation_amount' into orderedVars
        orderedVars.insert(idx, precipitation_amount)
        print precipitation_amount.data.min(), precipitation_amount.data.max()
    # end of if ('precipitation_amount', 'None') in _convertVars_:    
    
    if ('atmosphere_precipitable_water_content', 'None') in _convertVars_:

        # find the index in _convertVars_
        idx = _convertVars_.index(('atmosphere_precipitable_water_content', 'None'))
        # adjust the current index by subtract 1, because in previous insertion 
        # causes order index increased by 1.
        idx = idx-1 if (idx and oidx is None) else idx
        oidx = idx
        # store the atmosphere_mass_content_of_water data into temporary variable
        atmosphere_mass_content_of_water = [var for var in orderedVars 
               if var.standard_name == 'atmosphere_mass_content_of_water'] 
        if not atmosphere_mass_content_of_water:
            raise ValueError("Can not calculate atmosphere_precipitable_water_content, because unable to load atmosphere_mass_content_of_water")           
        # store the atmosphere_mass_content_of_dust_dry_aerosol_particles data into temporary variable
        atmosphere_mass_content_of_dust_dry_aerosol_particles = [var for var in orderedVars 
               if var.standard_name == 'atmosphere_mass_content_of_dust_dry_aerosol_particles']
        if not atmosphere_mass_content_of_dust_dry_aerosol_particles:
            raise ValueError("Can not calculate atmosphere_precipitable_water_content, because unable to load atmosphere_mass_content_of_dust_dry_aerosol_particles")
        # store the atmosphere_cloud_liquid_water_content data into temporary variable
        atmosphere_cloud_liquid_water_content = [var for var in orderedVars 
               if var.standard_name == 'atmosphere_cloud_liquid_water_content'] 
        if not atmosphere_cloud_liquid_water_content:
            raise ValueError("Can not calculate atmosphere_precipitable_water_content, because unable to load atmosphere_cloud_liquid_water_content")           
        
        # store the atmosphere_cloud_ice_content data into temporary variable
        atmosphere_cloud_ice_content = [var for var in orderedVars 
               if var.standard_name == 'atmosphere_cloud_ice_content']       
        if not atmosphere_cloud_ice_content:
            raise ValueError("Can not calculate atmosphere_precipitable_water_content, because unable to load atmosphere_cloud_ice_content")
        # calculate 'atmosphere_precipitable_water_content' by subtracting [1] - [2] - [3] -[4] 
        # [1] 'atmosphere_mass_content_of_water'
        # [2] 'atmosphere_mass_content_of_dust_dry_aerosol_particles'
        # [3] 'atmosphere_cloud_liquid_water_content'
        # [4] 'atmosphere_cloud_ice_content'
        
        # Lets do first subtraction,  out = [1] - [2],        
        atmosphere_precipitable_water_content = cubeAddSubtractor(atmosphere_mass_content_of_water[0], 
                            atmosphere_mass_content_of_dust_dry_aerosol_particles[0], 
                            action='sub',
                            long_name='atmosphere_precipitable_water_content',        
                                                             removeSTASH=True)
        # Lets make sure that standard_name is None for this variable.
        atmosphere_precipitable_water_content.standard_name = None
        # Lets do second subtraction,  out = out - [3],     
        atmosphere_precipitable_water_content = cubeAddSubtractor(atmosphere_precipitable_water_content,
                                     atmosphere_cloud_liquid_water_content[0],
                                     action='sub',
                            long_name='atmosphere_precipitable_water_content',
                                                             removeSTASH=True) 

        # Lets do third / last subtraction,  out = out - [4],
        atmosphere_precipitable_water_content = cubeAddSubtractor(atmosphere_precipitable_water_content,
                                              atmosphere_cloud_ice_content[0],
                                              action='sub',
                            long_name='atmosphere_precipitable_water_content', 
                                                             removeSTASH=True)

        # lets store the 'atmosphere_precipitable_water_content' into orderedVars
        orderedVars.insert(idx, atmosphere_precipitable_water_content)
    # end of if ('atmosphere_precipitable_water_content', 'None') in _convertVars_:
    
    
    if ('upward_air_velocity_in_pascal', 'm01s15i242') in _convertVars_:

        # find the index in _convertVars_
        idx = _convertVars_.index(('upward_air_velocity_in_pascal', 'm01s15i242'))
        # adjust the current index by subtract 1, because in previous insertion 
        # causes order index increased by 1.
        idx = idx-1 if (idx and oidx is None) else idx
        oidx = idx
        # store the upward_air_velocity data into temporary variable
        upward_air_velocity = [var for var in orderedVars 
               if var.standard_name == 'upward_air_velocity'] 
        if not upward_air_velocity:
            raise ValueError("Can not calculate upward_air_velocity_in_pascal, because unable to load upward_air_velocity")           
        # store the air_temperature data into temporary variable
        air_temperature = [var for var in orderedVars 
               if var.standard_name == 'air_temperature']
        if not air_temperature:
            raise ValueError("Can not calculate upward_air_velocity_in_pascal, because unable to load air_temperature")
        
        # calculate 'upward_air_velocity_in_pascal' by subtracting [1] - [2] - [3] -[4] 
        # upward_air_velocity_in_pascal = (upward_air_velocity / air_temperature) * -3.4162608
        # For eg : (VVEL(850)/Temp(850))*-3.4162608
        # ref : https://www.ncl.ucar.edu/Document/Functions/Contributed/omega_to_w.shtml
        # Formula given by Dr.Sumit, Project Scientist-D, NCMRWF
        upward_air_velocity = upward_air_velocity[0]
        air_temperature = air_temperature[0]
        print "upward_air_velocity=", upward_air_velocity.data.min(), upward_air_velocity.data.max()
        print "air_temperature=", air_temperature.data.min(), air_temperature.data.max()
        pressure = upward_air_velocity.coords('pressure')[0].points
        upward_air_velocity_in_pascal = (upward_air_velocity / air_temperature) * -0.034162608
        for idx, p in enumerate(pressure): upward_air_velocity_in_pascal.data[idx] *= float(int(p))    
        print "pressure=", pressure    
        print "upward_air_velocity_in_pascal", upward_air_velocity_in_pascal.data.min(), upward_air_velocity_in_pascal.data.max()
        # Lets make sure that standard_name is None for this variable.
        upward_air_velocity_in_pascal.standard_name = None
        upward_air_velocity_in_pascal.long_name = 'upward_air_velocity_in_pascal'
        upward_air_velocity_in_pascal.attributes = upward_air_velocity[0].attributes
        
        upward_air_velocity_in_pascal.units = Unit('Pa s-1')
        
        # lets store the 'upward_air_velocity_in_pascal' into orderedVars
        orderedVars.insert(idx, upward_air_velocity_in_pascal)
    # end of if ('upward_air_velocity_in_pascal', 'm01s15i242') in _convertVars_:    
    
    if ('surface_geopotential_height', 'm01s00i033') in _convertVars_:

        # find the index in _convertVars_
        idx = _convertVars_.index(('surface_geopotential_height', 'm01s00i033'))
        # adjust the current index by subtract 1, because in previous insertion 
        # causes order index increased by 1.
        idx = idx-1 if (idx and oidx is None) else idx
        oidx = idx
        # store the surface_altitude data into temporary variable
        surface_altitude = [var for var in orderedVars 
               if var.standard_name == 'surface_altitude'] 
        if not surface_altitude:
            raise ValueError("Can not calculate surface_geopotential_height, because unable to load surface_altitude")         
        surface_geopotential_height = surface_altitude[0] 
        surface_geopotential_height.standard_name = None
        surface_geopotential_height.long_name = 'surface_geopotential_height'
        # remove older orography variable (to avoid duplicate)
        orderedVars.remove(surface_altitude[0])
        # lets store the 'surface_geopotential_height' into orderedVars
        orderedVars.insert(idx, surface_geopotential_height)
    # end of if ('surface_geopotential_height', 'm01s00i033') in _convertVars_:
    
    # remove temporary variables from ordered vars list 
    for dvar, dSTASH in _removeVars_:
        for ovar in orderedVars:
            # removed temporary vars from ordered vars list        
            if ovar.standard_name == dvar: orderedVars.remove(ovar)
    # end of for dvar in _removeVars_:
    print "fpath doShuffleVarsInOrder", fpath
    # generate correct file name by removing _preExtension_
    g2filepath = fpath.split(_preExtension_)
    ncfilepath = g2filepath[0] + '.nc'
    wg2filepath = g2filepath[0] + g2filepath[-1]
    # set ordered extension is empty incase wgrib2 argument is empyt
    orderedExtension = '_Ordered' if __wgrib2Arguments__ else ''    
    g2filepath = g2filepath[0] + orderedExtension + g2filepath[-1]
    outstatus = False
    
    if _write2NetcdfFile_:
        if _write2NetcdfFile_ in [True, 'True']:
            _write2NetcdfFile_ = 'NETCDF4'  # use default as nc4.
            # otherwise lets use user passed nc type 
        ## lets save into compressed netcdf4 file 
        try:
            iris.fileformats.netcdf.save(orderedVars, ncfilepath, netcdf_format=_write2NetcdfFile_, 
                                       zlib=True, shuffle=True, least_significant_digit=6) 
        except Exception as e:
            print "ALERT !!! Error while saving orderd variables into nc!! %s" % str(e)
            print " So skipping this without saving data"
            outstatus = False
            return 
        finally:
            outstatus = True
    else:
        # now lets save the ordered variables into same file
        try:   
            # before save it, tweak the cubes by setting centre no and 
            # address other temporary issues before saving into grib2.
            iris.fileformats.grib.save_messages(tweaked_messages(orderedVars), 
                                                    g2filepath, append=True)
        except Exception as e:
            print "ALERT !!! Error while saving orderd variables into grib2!! %s" % str(e)
            print " So skipping this without saving data"
            outstatus = True
            return 
        finally:
            outstatus = True
        # end of try:
    # end of if _write2NetcdfFile_:
    time.sleep(30)  # lets wait 30 more seconds to be written properly.    
    while not outstatus: time.sleep(30)   # lets wait till grib2 file written status to be completed.        
    
    # make memory free 
    del orderedVars
    
    # remove intermediate nc files.
    for ncf in ncloadedfiles: 
        print "removed ncf file:", ncf
        os.remove(ncf)
        
    print "Created the variables in ordered fassion and saved into", 
    if _write2NetcdfFile_: 
        print ncfilepath
        return
         
    print g2filepath
    # remove the older grib2 file 
    print "removed older grib2 file", fpath
    os.remove(fpath)
    
    if __wgrib2Arguments__ is not None:
        # execute post wgrib2 command # strick to no of cpu is 2.
        ncpu = ' -ncpu 2 ' if not '-ncpu' in __wgrib2Arguments__ else ' '
        cmd = "%s %s %s %s" % (wgrib2, g2filepath, ncpu+__wgrib2Arguments__, wg2filepath)
        print cmd
        subprocess.call(cmd, shell=True)            
        time.sleep(10)
        # remove the grib2 file generated by IRIS
        os.remove(g2filepath)
        # rename g2filepath as wg2filepath
        g2filepath = wg2filepath
        print "Created grib2 file using wgrib2 command with compress arguments " 
    # end of if __wgrib2Arguments__:
                
    if _convertGrib2FilestoGrib1Files_:
        g1filepath = '.'.join(g2filepath.split('.')[:-1])
        g1filepath = g1filepath if g1filepath else g2filepath[:-1]
        if __grib1FilesNameSuffix__: g1filepath += str(__grib1FilesNameSuffix__)
        
        if os.path.isfile(g1filepath): os.remove(g1filepath)
        
        cmd = [cnvgrib, '-g21', g2filepath, g1filepath]
        subprocess.call(cmd, shell=False)
        cmd = ['chmod', '644', g1filepath]
        subprocess.call(cmd, shell=False)
        print "Converted grib2 to grib1 file : -", g1filepath
        
        if  _createGrib1CtlIdxFiles_:
            ## grib2ctl.pl usage option refer the below link 
            ## https://tuxcoder.wordpress.com/2011/04/11/how-to-install-grib2ctl-pl-and-wgrib-in-linux/    
            ctlfile = open(g1filepath+'.ctl', 'w')
            if __outFileType__ in ['ana', 'anl']:
                # create ctl & idx files for analysis file 
                tsahr = '-ts%dhr' %  int(__anl_step_hour__)
                subprocess.call([grib2ctl, tsahr, g1filepath], stdout=ctlfile)
                subprocess.call([gribmap, tsahr, '-0', '-i', g1filepath+'.ctl'])
            elif __outFileType__ in ['prg', 'fcst']:
                # create ctl & idx files for forecast file
                tsfhr = '-ts%dhr' %  int(__fcst_step_hour__)
                subprocess.call([grib2ctl, tsfhr, '-verf', g1filepath], stdout=ctlfile)
                subprocess.call([gribmap, '-i', g1filepath+'.ctl'])
            else:
                raise ValueError("unknown file type while executing grib2ctl.pl!!")
            
            print "Successfully created control and index file using grib2ctl !", g1filepath+'.ctl'
        # end of if _createGrib1CtlIdxFiles_:
    # end of if _convertGrib2FilestoGrib1Files_:
    
    if __removeGrib2FilesAfterGrib1FilesCreated__ and _convertGrib2FilestoGrib1Files_:
        # grib1 files are converted. so we can remove grib2 files.
        os.remove(g2filepath)
        print "deleted grib2 file", g2filepath        
    elif _createGrib2CtlIdxFiles_:
        ## g2ctl.pl usage option refer the below link 
        ## https://tuxcoder.wordpress.com/2011/08/31/how-to-install-g2ctl-pl-and-wgrib2-in-linux/
        ## though options says -verf for forecast end time, -0 for analysis time 
        ## -b for forecast start time, its all about setting reference in ctl file.
        ## Nothing more than that. We already set correct reference and forecast time bounds 
        ## in analysis files (whichever variables are actually taken from previous short forecast 0-6 hours).
        ## so here we no need to pass any options like -0 or -b. 
        ## By default g2ctl takes -verf option, same option we are passing 
        ## here to make sure that in future it will not affect.
        ctlfile = open(g2filepath+'.ctl', 'w')
        # create ctl & idx files for forecast file        
        if __outFileType__ in ['ana', 'anl'] and __anl_aavars_reference_time__ == 'analysis':
            # -0 will set the base reference time as analysis utc time. 
            tsahr = '-ts%dhr' %  int(__anl_step_hour__)
            subprocess.call([g2ctl, tsahr, '-0', g2filepath], stdout=ctlfile)
            subprocess.call([gribmap, '-0', '-i', g2filepath+'.ctl']) 
        elif __outFileType__ in ['rea', 'reanalysis']:
            # by default -verf as passed which takes end time of fcst bounds to set as base time.
            tsfhr = '-ts%dhr' %  int(__anl_step_hour__)
            subprocess.call([g2ctl, tsfhr, '-verf', g2filepath], stdout=ctlfile)
            subprocess.call([gribmap, '-i', g2filepath+'.ctl'])                
        else:
            # by default -verf as passed which takes end time of fcst bounds to set as base time.
            tsfhr = '-ts%dhr' %  int(__fcst_step_hour__)
            subprocess.call([g2ctl, tsfhr, '-verf', g2filepath], stdout=ctlfile)
            subprocess.call([gribmap, '-i', g2filepath+'.ctl'])                
        print "Successfully created control and index file using g2ctl !", g2filepath+'.ctl'
    # end of if __removeGrib2FilesAfterGrib1FilesCreated__:    
# end of def doShuffleVarsInOrder(fpath):

def doShuffleVarsInOrderInParallel(ftype, simulated_hr):
            
    global _current_date_, _opPath_, _preExtension_, __end_long_fcst_hour__, \
           __anlFileNameStructure__, __fcstFileNameStructure__, __anl_step_hour__, \
           __end_long_fcst_hour__, __fcst_step_hour__, __utc__, __start_long_fcst_hour__
            
    print "Lets re-order variables for all the files!!!"
    #####
    ## 6-hourly Files have been created with extension.
    ## Now lets do re-order variables within those individual files, in parallel mode.  
            
    # get current working directory
    current_dir = os.getcwd()
    # lets change current working directory as out path
    os.chdir(_opPath_)
    if ftype in ['fcst', 'forecast']:
        ## generate all the forecast filenames w.r.t forecast hours 
        # get the out fileName Structure based on pre / user defined indecies                       
        outFnIndecies = __getAnlFcstFileNameIndecies__(__fcstFileNameStructure__)
        fcstFiles = []
        for fcsthr in range(__start_long_fcst_hour__, 
                   __end_long_fcst_hour__+1, __fcst_step_hour__):            
            # generate the out file name based on actual informations                                 
            outFn = __genAnlFcstOutFileName__(__fcstFileNameStructure__, 
                                  outFnIndecies, _current_date_, fcsthr, 
                                           simulated_hr, _preExtension_)  
            fcstFiles.append(outFn)
        # end of for fcsthr in range(...):
        if __start_long_fcst_hour__ > 72 and __end_long_fcst_hour__ > 72:
             fcstFiles = fcstFiles[:3] # we need to extract upto 75 hours only
             
        ## get the no of created fcst files  
        nprocesses = len(fcstFiles)  
        maxprocess = mp.cpu_count()
        if nprocesses > maxprocess: nprocesses = maxprocess
        # parallel begin - 3
        pool = _MyPool(nprocesses)
        print "Creating %d (non-daemon) workers and jobs in doShuffleVarsInOrder process." % nprocesses
        results = pool.map(doShuffleVarsInOrder, fcstFiles)   
        
        # closing and joining master pools
        pool.close()     
        pool.join()
        # parallel end - 3    
    elif ftype in ['anl', 'analysis', 'rea', 'reanalysis']:
        ## generate the analysis filename w.r.t simulated_hr
        # get the out fileName Structure based on pre / user defined indecies                       
        outFnIndecies = __getAnlFcstFileNameIndecies__(__anlFileNameStructure__) 
        anlFiles = []
        simulated_hr = int(__utc__)
        # since ncum producing analysis files 00, 06, 12, 18 utc cycles and 
        # its forecast time starting from 0 and reference time based on utc.
        # so we should calculate correct hour as below.
        astep = 1 if __anl_step_hour__ == 1 else 6
        for fcsthr in range(0+simulated_hr, 6+simulated_hr, astep):            
            # generate the out file name based on actual informations                                 
            outFn = __genAnlFcstOutFileName__(__anlFileNameStructure__, 
                                  outFnIndecies, _current_date_, fcsthr, 
                                           simulated_hr, _preExtension_)  
            anlFiles.append(outFn)
        # end of for fcsthr in range(...):
        ## get the no of created anl files  
        nprocesses = len(anlFiles)   
        maxprocess = mp.cpu_count()
        if nprocesses > maxprocess: nprocesses = maxprocess 
        # parallel begin - 3 # parallel analysis required for 3-hourly analysis files.
        pool = _MyPool(nprocesses)
        print "Creating %d (non-daemon) workers and jobs in doShuffleVarsInOrder process." % nprocesses
        results = pool.map(doShuffleVarsInOrder, anlFiles)
        # closing and joining master pools
        pool.close()     
        pool.join()
        # parallel end - 3        
    # end of if ftype in ['fcst', 'forecast']: 
    print "Total time taken to convert and re-order all files was: %8.5f seconds \n" % (time.time()-_startT_)
    # reset current working directory
    os.chdir(current_dir)
    return 
# end of def doShuffleVarsInOrderInParallel(arg):
    
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
    global __start_long_fcst_hour__, __end_long_fcst_hour__, __UMtype__, __fcst_step_hour__
    
    
    if __UMtype__ == 'global':
        # calculate start hour of long fcst in multiples of 24. Why?
        # 00 hr contains from 06 to 24 hours data.
        # 24 hr contains from 24 to 48 hours data, and so on.
        if __fcst_step_hour__ == 24:
            start_fcst_hour = ((__start_long_fcst_hour__ / 24) - 1) * 24
        else:
            # < 24 hour, will it creat negative (-1) hour and try to looking for filename with -1.
            # to avoild, it we created condition here.
            start_fcst_hour = (__start_long_fcst_hour__ / 24) * 24
        # Here we are reducing one 24 because, 00 file contains upto 24 hour,
        # and 24 hour files contains upto 48 hour and so on.
            
        # here max fcst hours goes upto 240 only, not 241. why ??
        # because 216 long fcst hours contains upto 240th hour fcst.
        # and 240th long fcst contains upto 264th hour fcst.
        # so here no need to add +1 to __end_long_fcst_hour__.
        fcst_times = [str(hr).zfill(3) for hr in range(start_fcst_hour, __end_long_fcst_hour__, 24)]
        
    elif __UMtype__ == 'regional':
        start_fcst_hour = (__start_long_fcst_hour__ / 6) * 6
        fcst_times = [str(hr).zfill(2) for hr in range(start_fcst_hour, __end_long_fcst_hour__, 6)]
    # end of if __UMtype__ == 'global':
    
    fcst_filenames = [(fname, hr, None) for hr in fcst_times]
    print "fcst_filenames = ", fcst_filenames
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
    global _inDataPath_, _convertVars_, __UMReanalysis__
    
    hr = '000'
    if __UMReanalysis__:
        # call definition to get variable indices
        varNamesSTASH, _, _, _, _ = getVarInOutFilesDetails(_inDataPath_, fname, hr)
        if _convertVars_:
            # load only needed variables from this file !
            varNamesSTASH = [vns for vns in varNamesSTASH if vns in _convertVars_]    
        varCount = len(varNamesSTASH)
        anl_filenames = [(fname, hr, idx) for idx in range(varCount)]
        nchild = len(anl_filenames)
        if not nchild: raise ValueError("Got 0 varCount, couldn't make parallel !")
        # create the no of child parallel processes
        inner_pool = mp.Pool(processes=nchild)
        print "Creating %i (daemon) workers and jobs in child." % nchild        
        # pass the forecast hours as argument to take one fcst file per process / core to regrid it.
        results = inner_pool.map(regridAnlFcstFiles, anl_filenames)
        # closing and joining child pools      
        inner_pool.close() 
        inner_pool.join()
        # parallel end
    else:
        # convert all variables in serial manner
        regridAnlFcstFiles((fname, hr, None))  
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
    maxprocess = mp.cpu_count()
    if nprocesses > maxprocess: nprocesses = maxprocess 
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
    
    if ftype in ['rea', 'reanalysis']:
        fhrs = [None] 
    elif ftype in ['ana', 'anl']:
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
        # end of if __UMtype__ == 'global':
    # end of if ftype in ['ana', 'anl']:
    
    fileNotExistList = []
    for pfname in pfnames:
        for fhr in fhrs:
            # constrct the correct fileName from partial fileName and hours
            # add hour only if doenst have any extension on partial filename.
            if ftype in ['rea', 'reanalysis']:
                fname = pfname
            elif __UMtype__ == 'global':
                fname = pfname if '.' in pfname else pfname + fhr
            elif __UMtype__ == 'regional':
                # generate filenames like 'umnsaa_pb000', 'umnsaa_pb006', etc
                fname = pfname if '.' in pfname else pfname + fhr.zfill(3)                
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
        if __fcst_step_hour__ == 1: fhrs = fhrs[1:]
    # get the out fileName Structure based on pre / user defined indecies
    outFnIndecies = __getAnlFcstFileNameIndecies__(outFileNameStructure)
    status = None
    fnames = [] 
    for fhr in fhrs:
        # generate the out file name based on actual informations.
        # here preExtension is empty string to create final needed out file name                        
        fname = __genAnlFcstOutFileName__(outFileNameStructure, outFnIndecies,  
                                                               date, fhr, utc)
        fpath = os.path.join(path, fname) 
        fnames.append(fname)       
        for ext in ['', '.ctl', '.idx']:
            fpath = os.path.join(path, fname+ext)
            if os.path.isfile(fpath):
                print "Out File already exists", fpath,
                if overwrite: 
                    try:
                        os.remove(fpath)
                    except Exception, e:
                        print "Got error while removing file", e
                    finally:
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
        
        for ext in [_preExtension_, '_Ordered']:
            fpath = os.path.join(path, fname)
            if os.path.isfile(fpath) and ext in fpath:
                try:
                    os.remove(fpath)
                    print "removed file : ", fpath
                except Exception, e:
                        print "Got error while removing file", e
                finally:
                    status = 'IntermediateFilesExist'
                    print "removed intermediate file" 
        # end of for ext in [_preExtension_, '_Ordered']:
    # end of for fhr in fhrs:
    
    ifiles = [fname for fname in os.listdir(path) if fname.endswith('.nc')]    
    if ifiles:        
        print "Intermediate files are exists in the outdirectory.", path
        for ifile in ifiles:    
            if not [ifile for fname in fnames if fname.split('.')[0] in ifile]: continue
            if outFileNameStructure[0] in ifile and utc in ifile and _preExtension_ in ifile:
                status = 'IntermediateFilesExist'
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
       __fillFullyMaskedVars__, _write2NetcdfFile_
     
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
    write2netcdf = kwarg.get('write2NetcdfFile', False)
    
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
    _write2NetcdfFile_ = write2netcdf
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
    
    # update indata path 
    _inDataPath_ = __completeInOutPath__(inPath, _current_date_, utc)    
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
            varNamesSTASH, _, _, _, _ = getVarInOutFilesDetails(_inDataPath_, fileName, hr)
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
    
    # update outdate path 
    _opPath_ = __completeInOutPath__(outPath, _current_date_, utc)  
    # create out directory
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
    
    # do re-order variables within files in parallel
    doShuffleVarsInOrderInParallel('fcst', utc)
    
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
       __UMtype__, __fillFullyMaskedVars__, _write2NetcdfFile_, __UMReanalysis__  
           
    # load key word arguments
    UMtype = kwarg.get('UMtype', 'global')
    UMReanalysis = kwarg.get('UMReanalysis', False)
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
    write2netcdf = kwarg.get('write2NetcdfFile', False)
        
    # assign out file type in global variable    
    __UMReanalysis__ = UMReanalysis
    
    if UMReanalysis:
        __outFileType__ = 'rea' 
    else:
        __outFileType__ = 'ana' 
        
    # assign the convert vars list of tuples to global variable
    if convertVars: _convertVars_ = convertVars
    # assign the analysis file name structure
    if anlFileNameStructure: __anlFileNameStructure__ = anlFileNameStructure
    # set print variables details options
    __LPRINT__ = lprint
    # update global variables
    __anl_step_hour__ = anl_step_hour
    __UMtype__ = UMtype
    __utc__ = utc    
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
    _write2NetcdfFile_ = write2netcdf
    # analysis filenames partial name
    if UMReanalysis:
        anl_fnames = UMInShortFcstFiles
    elif __UMtype__ in ['global', 'regional']:
        if __UMtype__ == 'global':
            # pass user passed short forecast in files otherwise pass proper infiles.
            anl_fnames = UMInShortFcstFiles if UMInShortFcstFiles else ['umglca_pb', 'umglca_pd', 'umglca_pe', 'umglca_pf', 'umglca_pi']            
        elif __UMtype__ == 'regional':
            anl_fnames = UMInShortFcstFiles if UMInShortFcstFiles else []
            
        if utc == '00':
            # pass user passed analysis in files valid for 00UTC otherwise pass proper infile.
            anl_fnames = UMInAnlFiles + anl_fnames if UMInAnlFiles else anl_fnames
            # remove duplicate orography files.
            if 'qwqg00.pp0' in anl_fnames and 'umglc.pp0' in anl_fnames: anl_fnames.remove('umglc.pp0')
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

    # update indata path 
    _inDataPath_ = __completeInOutPath__(inPath, _current_date_, utc)
    print '_inDataPath_', _inDataPath_
    if not os.path.exists(_inDataPath_):
        raise ValueError("In datapath does not exists %s" % _inDataPath_)
    # end of if not os.path.exists(_inDataPath_):
    print     
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
            if UMReanalysis:
                fileName = fpname 
            else:
                ### if fileName has some extension, then do not add hr to it.
                fileName = fpname + hr if not '.' in fpname else fpname
            varNamesSTASH, _, _, _, _ = getVarInOutFilesDetails(_inDataPath_, fileName, hr)
            # check either user requires this file or not!
            if not set(varNamesSTASH).intersection(convertVars):
                # remove the fpname from fcst_fnames, because user didn't 
                # require variabels from this fpname file.
                anl_fnames.remove(fpname)
                print "removed %s from list of files" % fpname            
    # end of if convertVars:    
    print "Final fpname list :", anl_fnames    
    # check either infiles are exist or not!
    status = _checkInFilesStatus(_inDataPath_, __outFileType__, anl_fnames)
    if not status:
        raise ValueError("In datapath does not contain the above valid infiles")
    # end of if not instatus:
    
    # update outdate path 
    _opPath_ = __completeInOutPath__(outPath, _current_date_, utc)    
    # create out directory
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
    
    # do re-order variables within files in parallel
    doShuffleVarsInOrderInParallel('anl', utc)
    
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


## feeder!
#if __name__ == '__main__':
#    
#    
#    # call analysis conversion function w.r.t data assimilated during short forecast hour.
#    convertAnlFiles(hr='00')
#    #########################################################
#    ## Can be called the above function as below also.      #
#    ### for hour in ['00', '06', '12', '18']:               #
#    ###     convertAnlFiles(hr=hour)                        #
#    ### end of for hour in ['00', '06', '12', '18']:        #
#    ##                                                      #
#    #########################################################
#    
#    # call forecast conversion function w.r.t data assimilated at 00z long forecast hour.
#    convertFcstFiles(hr='00')
#    
# -- End code
