#!/usr/bin/env python

__author__ = 'arulalant'
__version__ = 'v2.0.0'
__long_name__ = 'NCUM Ensembles Parallel Rider'

"""
Inputs: NCUM fieldsfile / pp format files

Outputs: WMO-NCEP Grib2 format files

Disclaimers (if any!)
This is just test code as of now and is meant for a specific purpose only!

Copyright: ESSO-NCMRWF, MoES, 2015-2016, 2016-2017.

Author : Arulalan.T
initial code : 15-Mar-2016
Previous Update : 30-Mar-2016
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
from um2grb2 import (createDirWhileParallelRacing, getCubeData, myLog, 
             __getAnlFcstFileNameIndecies__, __genAnlFcstOutFileName__, 
            getCubeAttr, _NoDaemonProcess, _MyPool, _convert2WEASD,
            _updateDepthBelowLandSurfaceCoords4Levs, 
            _convert2VolumetricMoisture)

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
cnvgrib = "/gpfs1/home/Libs/INTEL/cnvgrib-1.4.0/cnvgrib"
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
_targetGridRes_ = None
_targetGridFile_ = ''
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
_ensemble_count_ = 44
__UMtype__ = 'ensemble'
__soilFirstSecondFixedSurfaceUnit__ = 'cm'
# store out grib2 files name for the purpose of creat ctl files in parallel
__outg2files__ = []
# global ordered variables (the order we want to write into grib2)
_orderedVars_ = {'PressureLevel': [
## Pressure Level Variable names & STASH codes
('geopotential_height', 'm01s16i202'),        
('x_wind', 'm01s15i243'), 
('y_wind', 'm01s15i244'),   
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
('x_wind', 'm01s03i209'), 
('y_wind', 'm01s03i210'),    
('visibility_in_air', 'm01s03i247'),
('precipitation_amount', 'm01s05i226'),
('stratiform_snowfall_amount', 'm01s04i202'),
('convective_snowfall_amount', 'm01s05i202'),
('stratiform_rainfall_amount', 'm01s04i201'),
('convective_rainfall_amount', 'm01s05i201'),
('rainfall_flux', 'm01s05i214'),
('snowfall_flux', 'm01s05i215'),
('precipitation_flux', 'm01s05i216'),
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
('surface_snow_amount_where_land', 'm01s00i023'),
# the surface_snow_amount_where_land might be changed as 
# liquid_water_content_of_surface_snow by convert it into
# water equivalent of snow amount, before re-ordering itself.
('liquid_water_content_of_surface_snow', 'm01s00i023'),
# the below one is for orography which presents only in analysis 00 file.
# so we must keep this as the last one in the ordered variables!
('surface_altitude', 'm01s00i033')],
}

# Define _accumulationVars_
# The following variables cell_methods should show accumulated/sum, but 
# UM pp code doesnt support for accumulation. So lets fix it here ! 
_accumulationVars_ = [('precipitation_amount', 'm01s05i226'),]                      

#Define _precipVars_
# The following vars should contains only precipitation, rainfall, snow 
# variables, those whose regrid extrapolate should be only in 'linear' mode
# and not in 'mask' mode, and should not have -ve values.
_precipVars_ = [('precipitation_amount', 'm01s05i226'),]

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
_ncfilesVars_ = []
                 
## Define _ncmrGrib2LocalTableVars_
## the following variables need to be set localTableVersion no as 1 and
## master table version no as 255 (undefined), since WRF grib2 table doesnt
## support for the following variables. So we created our own local table.
_ncmrGrib2LocalTableVars_ = ['fog_area_fraction',
                            'toa_outgoing_longwave_flux_assuming_clear_sky',   
                            'toa_outgoing_shortwave_flux_assuming_clear_sky',
                  'atmosphere_optical_thickness_due_to_dust_ambient_aerosol']

## Define _maskOverOceanVars_
## the following variables need to be set mask over ocean because the original
## model itself producing mask over ocean. but when we are doing regrid it 
## couldnt retain the mask ! dont know why ! So using land_binary_mask 
## variable, we are resetting mask over ocean for the following vars.
_maskOverOceanVars_ = []

## Define dust aerosol optical thickness of model pseudo level with its 
## corresponding micron / micro wavelength. We need to tweak with following 
## information before writing into final grib2 file.
_aod_pseudo_level_var_ = {}

## Define _depedendantVars_ where A is key, B is value. A is depedendant on B,
## B is not. B not necessarily to be written in out file. User may just specify
## only A in var.cfg configure file.
_depedendantVars_ = {}

## These are all the variables need to be averaged across all ensembles.
epsMeanVars = [
    ## Pressure Level Variable names & STASH codes
    ('geopotential_height', 'm01s16i202'),      
    ('x_wind', 'm01s15i243'),
    ('y_wind', 'm01s15i244'), 
    ('air_temperature', 'm01s16i203'),
    ('relative_humidity', 'm01s16i256'),
    ## Non Pressure Level Variable names & STASH codes
    ('air_pressure_at_sea_level', 'm01s16i222'),
    ]                                            

# start definition #2
def getVarInOutFilesDetails(inDataPath, fname, hr):
    """
    This definition module gets the required variables from the passed
    cube as per the WRF-Variables.txt file.

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

    """
    global __anl_step_hour__, __fcst_step_hour__, __start_long_fcst_hour__, \
           __end_long_fcst_hour__ 
    
    hr = int(hr)
    if __fcst_step_hour__ == 24: hr = (hr - 1) * 24 if hr > 0 else hr
    
    infile = os.path.join(inDataPath, fname)    
            
    ##### ENSEMBLES FILE BEGIN     
    if 'pb' in fname:                   
        varNamesSTASH = [('air_pressure_at_sea_level', 'm01s16i222'),
            ('air_temperature', 'm01s03i236'),
            ('relative_humidity', 'm01s03i245'),
            ('specific_humidity', 'm01s03i237'),
            ('precipitation_amount', 'm01s05i226'),
            ('x_wind', 'm01s03i209'), 
            ('y_wind', 'm01s03i210'),]
        # the cube contains Instantaneous data at every 6-hours.        
                
        if __fcst_step_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr       
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.
        doMultiHourlyMean = False
        
    elif 'pa' in fname:            
        # consider variable
        varNamesSTASH = [('air_pressure_at_sea_level', 'm01s16i222'),
                    ('air_temperature', 'm01s16i203'),  
                    ('geopotential_height', 'm01s16i202'),                    
                    ('relative_humidity', 'm01s16i256'), 
                    ('surface_air_pressure', 'm01s00i409'),                   
                    ('x_wind', 'm01s15i243'),
                    ('y_wind', 'm01s15i244'),
                    ('upward_air_velocity', 'm01s15i242')]
        # the cube contains Instantaneous data at every 24-hours.        
        if __fcst_step_hour__ == 24:
            # applicable only for 24 hour instantaneous/intervals
             fcstHours = numpy.arange(__start_long_fcst_hour__, __end_long_fcst_hour__+1, 24)       
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.      
        doMultiHourlyMean = False    
        
    elif 'pc' in fname:            
        # consider variable
        varNamesSTASH = [('air_temperature_maximum', 'm01s03i236'),  
                    ('air_temperature_minimum', 'm01s03i236'),  
                    ('precipitation_amount', 'm01s05i226')]              
        # the cube contains accumulated/min/max data at every 24-hours.        
        if __fcst_step_hour__ == 24:
            # applicable only for 24 hour intervals
            # __start_long_fcst_hour__
            # calculate start hour of long fcst in increment of 12. Why?
            # 12 hr centered at 0hr to 24hr
            # 24 hr centered at 24hr to 48hr data, and so on.          
            start_fcst_hour = 24 if __start_long_fcst_hour__ < 24 else __start_long_fcst_hour__
            fcstHours = numpy.arange(__start_long_fcst_hour__, __end_long_fcst_hour__+24, 24) - 12 # WORKS correctly.
        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.      
        doMultiHourlyMean = False    
        
    elif 'pd' in fname:            
        # consider variable
        # consider variable
        varNamesSTASH = [('air_temperature', 'm01s16i203'),  
                    ('geopotential_height', 'm01s16i202'),                    
                    ('relative_humidity', 'm01s16i256'), 
                    ('specific_humidity', 'm01s30i205'),                                   
                    ('x_wind', 'm01s15i243'),
                    ('y_wind', 'm01s15i244'),
                    ('upward_air_velocity', 'm01s15i242')]         
        # the cube contains accumulated/min/max data at every 24-hours.        
        
        if hr: 
            fcstHours = numpy.array([hr+6])
        else:
            fcstHours = numpy.array([0, 6])

        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.      
        doMultiHourlyMean = False    
    
    elif 'pg' in fname:            
        # consider variable
        # consider variable
        varNamesSTASH = [('air_pressure_at_sea_level', 'm01s16i222'),
                        ('air_temperature', 'm01s03i236'),   
                        ('air_temperature_maximum', 'm01s03i236'),   
                        ('air_temperature_minimum', 'm01s03i236'),   
                        ('dew_point_temperature', 'm01s03i250'),   
                        ('surface_temperature', 'm01s00i024'),   
                        ('land_binary_mask', 'm01s00i030'),   
                        ('moisture_content_of_soil_layer', 'm01s08i223'),
                        ('soil_temperature', 'm01s03i238'),    
                        ('precipitation_amount', 'm01s05i226'),   
                        ('relative_humidity', 'm01s03i245'),           
                        ('specific_humidity', 'm01s03i237'),   
                        ('surface_air_pressure', 'm01s00i409'),   
                        ('surface_altitude', 'm01s00i033'),   
                        ('x_wind', 'm01s03i209'),  
                        ('y_wind', 'm01s03i210'),
                        ('surface_net_downward_shortwave_flux', 'm01s01i202'),
                        ('surface_net_downward_longwave_flux', 'm01s02i201'), 
                        ('surface_upward_latent_heat_flux', 'm01s03i234'),   
                        ('surface_upward_sensible_heat_flux', 'm01s03i217'),   
                        ('toa_outgoing_longwave_flux', 'm01s02i205'),
                        ('cloud_area_fraction_assuming_random_overlap', 'm01s09i216'),
                        ('surface_snow_amount_where_land', 'm01s00i023')]         
        # the cube contains accumulated/min/max data at every 24-hours.        
        
        if hr: 
            fcstHours = numpy.array([hr+6])        
        else:
            fcstHours = numpy.array([0, 6])

        # we are extracting at particular instantaneous value, so no need to 
        # do hourly mean.      
        doMultiHourlyMean = False  
    ##### FORECAST FILE END
    else:
        raise ValueError("Filename '%s' not implemented yet!" % fname)
    # end if-loop

    return varNamesSTASH, fcstHours, doMultiHourlyMean, infile
# end of def getVarInOutFilesDetails(inDataPath, fname, hr):

def packEnsembles(arg):
    
    global _targetGrid_, _targetGridRes_,  _startT_, _inDataPath_, _opPath_, \
            _preExtension_, _ncfilesVars_, _requiredLat_, _requiredLon_, \
            _doRegrid_, __utc__, _requiredPressureLevels_, __LPRINT__, \
            __outg2files__, _lock_, _accumulationVars_, __fcst_step_hour__, \
            _targetGridFile_, _extraPolateMethod_, _current_date_, \
             _reverseLatitude_, _precipVars_, _maskOverOceanVars_
                 
    infiles, varNamesSTASHFcstHour = arg
    varName, varSTASH, fhr = varNamesSTASHFcstHour
    
    if (varName, varSTASH) in _accumulationVars_:
        # update the forecast hour, since precipitation_amount is accumulated
        # var, not instantaneous one.
        fhr -= 3
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
        
        if (varName, varSTASH) in [('surface_snow_amount_where_land', 'm01s00i023')]:
            # the surface_snow_amount_where_land need to be changed as 
            # liquid_water_content_of_surface_snow by convert it into
            # water equivalent of snow amount.                    
            _convert2WEASD(regdCube)
        # end of if (varName, varSTASH) == ('surface_snow_amount_where_land', 'm01s00i023'):
                
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
            
            if (regdCube.standard_name == 'moisture_content_of_soil_layer'):
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
        aux_coords = list(regdCube.aux_coords)
        aux_factories = regdCube.aux_factories
        t = regdCube.coords('time')[0]
        fp = regdCube.coords('forecast_period')[0]
        ft = regdCube.coords('forecast_reference_time')[0]
        # create ensemble packed cubes 
        ensembleData = iris.cube.Cube(ensembleData, regdCube.standard_name, 
                                 regdCube.long_name, regdCube.var_name,
                                   regdCube.units, regdCube.attributes, 
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

        # get the regridded ensembles meta data 
        fcstTm = getCubeAttr(ensembleData)[2]
        
        if fcstTm.bounds is not None:                
            # this is needed for forecast 00th simulated_hr
            # get the last hour from bounds
            hr = str(int(fcstTm.bounds[-1][-1]))
            if __LPRINT__: print "Bounds comes in ", hr, fcstTm.bounds                        
        else:
            # get the fcst time point 
            # this is needed for analysis/forecast 00th simulated_hr
            hr = str(int(fcstTm.points))
            if __LPRINT__: print "points comes in ", hr 
        # end of if fcstTm.bounds:
        
        outFileNameStructure = __fcstFileNameStructure__
        # get the out fileName Structure based on pre / user defined indecies                       
        outFnIndecies = __getAnlFcstFileNameIndecies__(outFileNameStructure)
        # get the file name extension
        fileExtension = outFileNameStructure[-1]  
        # generate the out file name based on actual informations                                 
        outFn = __genAnlFcstOutFileName__(outFileNameStructure, 
                             outFnIndecies, _current_date_, hr, 
                                       __utc__, _preExtension_) 
        # get the file full name except last extension, for the purpose
        # of writing intermediate nc files
        ofname = outFn.split(fileExtension)[0] 
        
        # make unique file name becase we are running in parallel            
        if varName == 'air_temperature_maximum':
            outFn = varSTASH + '-max_'+ outFn
        elif varName == 'air_temperature_minimum':
            outFn = varSTASH + '-min_'+ outFn
        else:
            outFn = varSTASH + '_'+ outFn  # suits for all other vars
                           
        ncfile = False
        print "outFn = ", outFn
                
        # append out grib2 files for the purpose of creating ctl files.
        if not outFn in __outg2files__: __outg2files__.append(outFn)
        print "__outg2files__ = ", __outg2files__
        outFn = os.path.join(_opPath_, outFn)
        print "Going to be save into ", outFn
        print "ensembleData-var", ensembleData.standard_name
        print ensembleData
                
        try:                
            # _lock_ other threads / processors from being access same file 
            # to write other variables. 
#            _lock_.acquire()
            
            # before save it, tweak the cubes by setting centre no and 
            # address other temporary issues before saving into grib2.
            iris.fileformats.grib.save_messages(tweaked_messages([ensembleData,]), 
                                                           outFn, append=True) # save grib2 file 
            # release the _lock_, let other threads/processors access this file.
#            _lock_.release()
        except Exception as e:
            print "ALERT !!! Error while saving!! %s" % str(e)
            print " So skipping this without saving data"        
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
            _opPath_, _ensemble_count_, __outg2files__, __start_long_fcst_hour__
   
    fpname, hr = arg 

    step_fcst_hour = __fcst_step_hour__    
    ensembleFiles_allConstraints_list = []
    
    fexthr = str(hr).zfill(3) 
    ensembleFiles = [os.path.join(_inDataPath_, str(ens).zfill(3)+'_'+fpname+fexthr) 
                                            for ens in range(0, _ensemble_count_+1, 1)]
    fileName = '000_' + fpname   # sample file to get the variabels name.
    
    fname = os.path.join(_inDataPath_, fileName)
    # get variable indices
    varNamesSTASH, fcstHours, doMultiHourlyMean, infile = getVarInOutFilesDetails(_inDataPath_,
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
            # the following vars doesnt have value at 00th instantaneous, but has 06th value.
            if not fhr and (varName, varSTASH) in [('air_temperature_maximum', 'm01s03i236'),   
('air_temperature_minimum', 'm01s03i236'), ('relative_humidity', 'm01s03i245'),
('precipitation_amount', 'm01s05i226'), ('specific_humidity', 'm01s03i237'),]: continue
            if not fhr and 'flux' in varName: continue
            allConstraints = [varName, varSTASH, fhr]     
            ensembleFiles_allConstraints_list.append((ensembleFiles, allConstraints))
    # end of for varName, varSTASH in varNamesSTASH:      
    
    print "Started Processing the file:  \n" 
    print "ensembleFiles_allConstraints_list", ensembleFiles_allConstraints_list
                                                
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

def doWgrib2cmd(arg):
    global wgrib2, __wgrib2Arguments__
    
    if __wgrib2Arguments__ is not None:
        inFn, outFn = arg 
        cmd = "%s %s %s %s" % (wgrib2, inFn, __wgrib2Arguments__, outFn)
        print cmd
        subprocess.call(cmd, shell=True)
        
            
def createGrib2CtlIdxFilesFn(g2filepath, ftype='fcst'):
    ## g2ctl.pl usage option refer the below link 
    ## https://tuxcoder.wordpress.com/2011/08/31/how-to-install-g2ctl-pl-and-wgrib2-in-linux/
    ## though options says -verf for forecast end time, -0 for analysis time 
    ## -b for forecast start time, its all about setting reference in ctl file.
    ## Nothing more than that. We already set correct reference and forecast time bounds 
    ## in analysis files (whichever variables are actually taken from previous short forecast 0-6 hours).
    ## so here we no need to pass any options like -0 or -b. 
    ## By default g2ctl takes -verf option, same option we are passing 
    ## here to make sure that in future it will not affect.
    
    global __fcst_step_hour__
    
    ctlfile = open(g2filepath+'.ctl', 'w')
    if ftype == 'fcst':
        # create ctl & idx files for forecast file
        tsfhr = '-ts%dhr' %  int(__fcst_step_hour__)
        # by default -verf as passed which takes end time of fcst bounds to set as base time.
        subprocess.call([g2ctl, tsfhr, '-verf', g2filepath], stdout=ctlfile)
        subprocess.call([gribmap, '-i', g2filepath+'.ctl'])  
        print "Successfully created control and index file using g2ctl !", g2filepath+'.ctl'       
# end of def createGrib2CtlIdxFilesFn(g2filepath, ...):

def tweaked_messages(cubeList):
    global _ncmrGrib2LocalTableVars_, __setGrib2TableParameters__
    
    for cube in cubeList:
        for cube, grib_message in iris.fileformats.grib.as_pairs(cube):
            print "Tweaking begin ", cube.standard_name            
            # post process the GRIB2 message, prior to saving
            gribapi.grib_set_long(grib_message, "centre", 29) # RMC of India
            gribapi.grib_set_long(grib_message, "subCentre", 0) # No subcentre
            print "reset the centre as 29"
            
            # ensembles tweak begin
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
                print 'reset typeOfTimeIncrement as 2 for', cube.standard_name
            # end of if cube.coord("forecast_period").bounds is None:       
            
            # setting ensemble no   
            gribapi.grib_set(grib_message, "perturbationNumber",
                         int(cube.coord('realization').points[0]))
            # no encoding at present in Iris, set to missing
            gribapi.grib_set(grib_message, "numberOfForecastsInEnsemble", 255)
            #http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_table4-6.shtml 
            # 3 would be better, since we keep on increasing ensmble points 
            # from 0 to 44
            gribapi.grib_set(grib_message, "typeOfEnsembleForecast", 3)
            # ensembles tweak end
            
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
                    # end of if cube.standard_name.startswith('tropopause'): 
                    if cube.standard_name == 'surface_temperature':
                        gribapi.grib_set(grib_message, "parameterNumber", 17) # skintemp
                # end of if cube.standard_name:

                if cube.long_name:                     
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
                    print "setting localTable for", cube.standard_name
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
        # end of for cube, grib_message in iris.fileformats.grib.as_pairs(cube):
    # end of for cube in cubeList:
# end of def tweaked_messages(cube):

# Start the convertFilesInParallel function
def convertFilesInParallel(fnames, ftype):
    """
    convertFilesInParallel function calling all the sub-functions
    :param fnames: a simple filename as argument in a string format
    """
    
    global _startT_, _tmpDir_, _opPath_, __end_long_fcst_hour__,\
           __fcst_step_hour__, _createGrib2CtlIdxFiles_, \
           __start_long_fcst_hour__
    
    # calculate start hour of long fcst in multiple of days.
    start_fcst_hour = __start_long_fcst_hour__
    end_fcst_hour = __end_long_fcst_hour__ 
    fcst_times = [str(hr) for hr in range(start_fcst_hour, end_fcst_hour, __fcst_step_hour__)]
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
# end of def convertFilesInParallel(fnames):

def _checkInFilesStatus(path, ftype, pfname, **kwarg):
    
    global __start_long_fcst_hour__, __end_long_fcst_hour__, _ensemble_count_, __fcst_step_hour__
    
    start_long_fcst_hour = kwarg.get('start_long_fcst_hour', __start_long_fcst_hour__)
    end_long_fcst_hour = kwarg.get('end_long_fcst_hour', __end_long_fcst_hour__)
    fcst_step_hour = kwarg.get('fcst_step_hour', __fcst_step_hour__)
    ensemble_count = kwarg.get('ensemble_count', _ensemble_count_)
    
    if ftype in ['ana', 'anl']:
        fhrs = ['000'] 
    elif ftype in ['fcst', 'prg']:
        # calculate start hour of long fcst in multiple of days. 
        if fcst_step_hour == 24:
            start_fcst_hour = (start_long_fcst_hour / 24) 
            end_fcst_hour = end_fcst_hour/24        
            fhrs = [str(hr) for hr in range(start_fcst_hour, end_fcst_hour+1, 1)]
            pfiles = ['pa', 'pb', 'pc']
        elif fcst_step_hour == 6:
            fhrs = [str(hr).zfill(3) for hr in range(start_long_fcst_hour, end_long_fcst_hour, 6)]
            pfiles = ['pd', 'pg']
    fileNotExistList = []

    for ehr in range(0, ensemble_count+1, 1):
        if pfname in pfiles:
            for fhr in fhrs:
                # construct the correct fileName from partial fileName and hours
                # add hour only if doenst have any extension on partial filename.
                fexthr = fhr #if int(fhr) else '1'
                fname = str(ehr).zfill(3) + '_' + pfname + fexthr
                # becase extension 1 file contains both 00 hr and 24 hour.
                fpath = os.path.join(path, fname)
                if not os.path.isfile(fpath): fileNotExistList.append(fpath)
    # end of for ehr in range(0, _ensemble_count_+1, 1):
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
        if __fcst_step_hour__ == 6 and __start_long_fcst_hour__: fhrs = fhrs[1:]
        print "fhrs++", fhrs, __fcst_step_hour__, __start_long_fcst_hour__
    # get the out fileName Structure based on pre / user defined indecies
    outFnIndecies = __getAnlFcstFileNameIndecies__(outFileNameStructure)
    status = None
    fnames = [] 
    print "fhrs = ", fhrs
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
    if __fcst_step_hour__ == 6:
        fcst_fnames = ['pd', 'pg']  # ['pb'] old filename 
    elif __fcst_step_hour__ == 24:
        fcst_fnames = ['pa', 'pc']
        
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
            fileName = '000_' + fcst_fname 
            varNamesSTASH, _, _, _ = getVarInOutFilesDetails(_inDataPath_, fileName, hr)
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
        status = _checkInFilesStatus(_inDataPath_, 'prg', fcst_fname)
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
    status = _checkOutFilesStatus(_opPath_, 'prg', _current_date_, utc, overwrite)
    if status is 'FilesExist': 
        print "All files are already exists. So skipping convert Fcst files porcess"
        return # return back without executing conversion process.
    elif status in [None, 'FilesDoNotExist', 'FilesRemoved']:
        print "Going to start convert Fcst files freshly"
    # end of if status is 'FilesExists': 
    
    # do convert for forecast files  
    convertFilesInParallel(fcst_fnames, ftype='fcst')    
    
    pwd = os.getcwd()
    os.chdir(_opPath_)  # change to our path
    
    fhrs = (numpy.arange(start_long_fcst_hour, end_long_fcst_hour, fcst_step_hour) + fcst_step_hour).tolist()
    if start_long_fcst_hour == 0: fhrs = [0] + fhrs
    ffns = fcstFileNameStructure[0]
    print "ffns---->", ffns, fhrs
    for fhr in fhrs:
        hrs = str(fhr).zfill(3) + 'hr'
        outg2files = [inf for inf in os.listdir(_opPath_) if ffns in inf if hrs in inf if _preExtension_ in inf]
        if not outg2files: continue
        fname = '_'.join(outg2files[0].split('_')[1:]) # remove STASH alone
        outFn = fname.replace(_preExtension_, '') # remove _preExtension_
        print "_convertVars_====>", _convertVars_
        for varName, varSTASH in _convertVars_:
            # make unique file name becase we are running in parallel            
            if varName == 'air_temperature_maximum':
                inFn = [inf for inf in outg2files if inf.startswith(varSTASH+'-max')]
            elif varName == 'air_temperature_minimum':
                inFn = [inf for inf in outg2files if inf.startswith(varSTASH+'-min')]
            else:
                # Generic all other vars filter with simple varSTASH
                inFn = [inf for inf in outg2files if inf.startswith(varSTASH) if not '-' in inf]
            # end of if varName == 'air_temperature_maximum':            
            if not inFn: continue
            inFn = inFn[0]
            if __wgrib2Arguments__ is not None:
                # execute post wgrib2 command in parellel (-ncpu 4 Best speed compare to 32)            
                cmd = "%s %s %s %s" % (wgrib2, inFn, __wgrib2Arguments__, outFn)
                print "wgrib2 merge cmd", cmd
                subprocess.call(cmd, shell=True)
            else:
                cubes = iris.load_cubes(inFn)
                iris.fileformats.grib.save_messages(tweaked_messages(cubes), 
                                                 outFn, append=True) # save grib2 file                
            # end of if __wgrib2Arguments__:
            time.sleep(15)            
            if not ((varName, varSTASH) in epsMeanVars and fhr % 24 == 0): 
                os.remove(inFn)
                print "removed", inFn                        
            ## epsMeanVars will be created through callback script. For that 
            ## purpose we should not delete those files, because
            ## it requires to create EPS MEAN VSDB INPUT. We have to load 
            ## this file only in Python-IRIS. Because IRIS able to read it 
            ## properly only for the simple compression algorithm not for the 
            ## complex2 (wgrib2) algorithm. IRIS read the values wrongly,
            ## if grib2 is written in complex2 algorithm. So... theses will 
            ## be used to read it to create EPS mean and then will be deleted.
            ## Dated : 05-Aug-2016.              
        # end of for varName, varSTASH in varNamesSTASH:   
        time.sleep(15)
        # Lets create ctl and idx file. 
        createGrib2CtlIdxFilesFn(outFn, ftype='fcst')       
    # end of for fhr in range(start_long_fcst_hour, end_long_fcst_hour, fcst_step_hour):
    
    os.chdir(pwd) # Back to previous directory
    
    if callBackScript:
        callBackScript = os.path.abspath(callBackScript)
        if not os.path.exists(callBackScript): 
            print "callBackScript '%s' doesn't exist" % callBackScript
            return 
        kwargs = ' --date=%s --start_long_fcst_hour=%d --end_long_fcst_hour=%d --fcst_step_hour=%d' % (_current_date_, start_long_fcst_hour, end_long_fcst_hour, __fcst_step_hour__)
        scriptExecuteCmd = callBackScript + ' ' + kwargs
        # execute user defined call back script with keyword arguments
        subprocess.call(scriptExecuteCmd, shell=True)
    # end of if callBackScript:
# end of def convertFcstFiles(...):



# -- End code
