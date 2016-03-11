#!/usr/bin/env python

__author__ = 'arulalant'
__version__ = 'v1.0.1'
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
latest Update : 11-Mar-2016
"""

# -- Start importing necessary modules
import os, sys, time, subprocess
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
from cubeutils import cubeAverager, cubeSubtractor
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
cnvgrib = "/gpfs1/home/Libs/INTEL/cnvgrib-1.4.0/cnvgrib"

# other global variables
__LPRINT__ = False
__utc__ = '00'
__outFileType__ = 'ana'
# start and step hour in short forecast files
__anl_step_hour__ = 6
# start and step hour in long forecast files
__start_step_long_fcst_hour__ = 6
# maximum long forecast hours produced by model
__max_long_fcst_hours__ = 240
# grib1 file suffix
__grib1FilesNameSuffix__ = '.grib1'
# flag for removing grib2 files after grib1 has been converted 
__removeGrib2FilesAfterGrib1FilesCreated__ = False

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
_requiredLat_ = None
_requiredLon_ = None
_requiredPressureLevels_ = None
_preExtension_ = '_unOrdered'
_createGrib2CtlIdxFiles_ = True
_createGrib1CtlIdxFiles_ = False
_convertGrib2FilestoGrib1Files_ = False
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
# the snowfall_amount might be changed as 
# liquid_water_content_of_surface_snow by convert it into
# water equivalent of snow amount, before re-ordering itself.
('liquid_water_content_of_surface_snow', 'm01s00i023'),
# the below one is for orography which presents only in analysis 00 file.
# so we must keep this as the last one in the ordered variables!
('surface_altitude', 'm01s00i033')],
}

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
_ncfilesVars_ = [('volumetric_moisture_of_soil_layer', 'm01s08i223'), 
        # 'moisture_content_of_soil_layer' renamed as  
        # 'volumetric_moisture_of_soil_layer', but same STASH m01s08i223 code.
        ('volumetric_moisture_of_soil_layer', 'm01s08i208'), 
        # 'soil_moisture_content' renamed as  
        # 'volumetric_moisture_of_soil_layer', but same STASH m01s08i208 code.
                 ('soil_temperature', 'm01s03i238'),
                 ('toa_incoming_shortwave_flux', 'm01s01i207'),
                 ('tropopause_altitude', 'm01s30i453'),
                 ('tropopause_air_temperature', 'm01s30i452'),
                 ('tropopause_air_pressure', 'm01s30i451'),
('atmosphere_optical_thickness_due_to_dust_ambient_aerosol', 'm01s02i422'),]
                 
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
_maskOverOceanVars_ = ['volumetric_moisture_of_soil_layer', 
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
                        ('surface_downwelling_longwave_flux', 'm01s02i207')]
}
                                            
# create a class #1 for capturing stdin, stdout and stderr
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

# start definition #1
def getCubeData(umFname):
    """
    This definition module reads the input file name and its location as a
    string and it returns the data as an Iris Cube.
    An upgraded version uses a GUI to read the file.

    :param umFname: UM fieldsfile filename passed as a string
    :return: Data for corresponding data file in Iris cube format
    
    Note : loaded cube may be update by callback function 
            "update_cf_standard_name" of ncum_load_rules module.
    """
    # check cf_standard_name of cubes and update it if necessary while loading 
    cubes = iris.load(umFname, callback=update_cf_standard_name)
    
    return cubes
# end of definition #1

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
    
    ipath = ipath.split('/')
    hr = ipath[-1]
    today_date = ipath[-2]
    
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
        
    ## update the hour, date 
    ipath[-1] = hr
    ipath[-2] = today_date
    ipath = os.path.join('/', *ipath)
    # infile path (it could be current date and past 6 hour for 06,12,18 hours.  
    # but it set yesterday date and past 6 hour for 00 hour)
    infile = os.path.join(ipath, fname)  
    return infile
# end of def __getTodayOrYesterdayInfile__(ipath):

def __getAnlFcstFileNameIdecies__(fileNameStructure):
    
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
                            ['*D*', '*D*', '*DDD*']) if idx]
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
    global __anl_step_hour__, __start_step_long_fcst_hour__
    
    hr = int(hr)
    
    infile = os.path.join(inDataPath, fname)    
    
    inDataPathHour = inDataPath.split('/')[-1]      
    
    ##### ANALYSIS FILE BEGIN     
    if fname.startswith('qwqg00.pp0'):                   # qwqg00.pp0
        varNamesSTASH = [('geopotential_height', 'm01s16i202'),
            ('air_temperature', 'm01s16i203'),
            ('relative_humidity', 'm01s16i256'),
            ('x_wind', 'm01s15i243'), 
            ('y_wind', 'm01s15i244'),
            ('upward_air_velocity', 'm01s15i242'),
            ('air_pressure_at_sea_level', 'm01s16i222'),
            ('surface_air_pressure', 'm01s00i409'),
            ('surface_altitude', 'm01s00i033')]
        # the cube contains Instantaneous data at every 24-hours.        
        # but we need to extract every 0th hours instantaneous.
        fcstHours = numpy.array([0,])     
        doMultiHourlyMean = False
            
    elif fname.startswith('umglca_pb'):              # umglca_pb
        # available for use
        varNamesSTASH = [('land_binary_mask', 'm01s00i030'),
                    ('fog_area_fraction', 'm01s03i248'),
                    ('dew_point_temperature', 'm01s03i250'),
                    ('atmosphere_boundary_layer_thickness', 'm01s00i025'),
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
            varNamesSTASH = [('specific_humidity', 'm01s30i205'),] 
            # rest of them from taken already from qwqg00 
            # file. qwqg00 file variables are more correct than this 
            # short forecast vars.
        else:            
           varNamesSTASH = [('geopotential_height', 'm01s16i202'),
                       ('air_temperature', 'm01s16i203'), 
                       ('specific_humidity', 'm01s30i205'),
                       ('relative_humidity', 'm01s16i256'),                        
                       ('x_wind', 'm01s15i243'),
                       ('y_wind', 'm01s15i244'),
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
                        ('x_wind', 'm01s03i209'), 
                        ('y_wind', 'm01s03i210'),
                        ('atmosphere_convective_available_potential_energy_wrt_surface', 'm01s05i233'), # CAPE
                        ('atmosphere_convective_inhibition_wrt_surface', 'm01s05i234'), #CIN
                        ]
       
        if inDataPathHour == '00' and __anl_step_hour__ != 3:
            # remove only if __anl_step_hour__ is 6 hours.
            # for 3 hour analysis, (3rd hour) we need to extract these vars
            # from the umglca_pe file. But for 00th analysis the following vars 
            # need to be extracted from qwqg00.pp0 file. 
            for varST in [('air_pressure_at_sea_level', 'm01s16i222'), 
                            ('surface_air_pressure', 'm01s00i409'),]:
                # these vars taken already from qwqg00.pp0 file. so remove it.
                varNamesSTASH1.remove(varST)         
        # end of if inDataPathHour == '00' and ...:
        
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
        infile = __getTodayOrYesterdayInfile__(inDataPath, fname)
        
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
        infile = __getTodayOrYesterdayInfile__(inDataPath, fname)
        
    ##### ANALYSIS FILE END
    
    ##### FORECAST FILE BEGIN
    elif fname.startswith('umglaa_pb'):              # umglaa_pb
        varNamesSTASH = [('land_binary_mask', 'm01s00i030'),
                    ('fog_area_fraction', 'm01s03i248'),
                    ('dew_point_temperature', 'm01s03i250'),
                    ('atmosphere_boundary_layer_thickness', 'm01s00i025'),
                    ('surface_temperature', 'm01s00i024'),
                    ('relative_humidity', 'm01s03i245'),
                    ('visibility_in_air', 'm01s03i247'),
                    ('tropopause_altitude', 'm01s30i453'),
                    ('tropopause_air_temperature', 'm01s30i452'),
                    ('tropopause_air_pressure', 'm01s30i451'),
                    ('sea_ice_area_fraction', 'm01s00i031'),
                    ('sea_ice_thickness', 'm01s00i032'),
#                    ('soil_moisture_content', 'm01s08i208'),  # production has -ve values, (WRONG values)
                    # the snowfall_amount need to be changed as 
                    # liquid_water_content_of_surface_snow by convert it into
                    # water equivalent of snow amount.
                    ('snowfall_amount', 'm01s00i023')] 
        # the cube contains Instantaneous data at every 3-hours.
        if __start_step_long_fcst_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __start_step_long_fcst_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __start_step_long_fcst_hour__ == 24:
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
                    ('x_wind', 'm01s15i243'),
                    ('y_wind', 'm01s15i244'),
                    ('upward_air_velocity', 'm01s15i242')]
        # the cube contains Instantaneous data at every 3-hours.
        if __start_step_long_fcst_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __start_step_long_fcst_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __start_step_long_fcst_hour__ == 24:
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
                    ('x_wind', 'm01s03i209'), 
                    ('y_wind', 'm01s03i210'),
                    ('atmosphere_convective_available_potential_energy_wrt_surface', 'm01s05i233'), # CAPE
                    ('atmosphere_convective_inhibition_wrt_surface', 'm01s05i234'), #CIN
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
        if __start_step_long_fcst_hour__ == 3:
            # applicable only for 3 hour instantaneous/intervals
            fcstHours = numpy.array([3, 6, 9, 12, 15, 18, 21, 24]) + hr
        elif __start_step_long_fcst_hour__ == 6:
            # applicable only for 6 hour instantaneous/intervals
            fcstHours = numpy.array([6, 12, 18, 24]) + hr
        elif __start_step_long_fcst_hour__ == 24:
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
        if __start_step_long_fcst_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([1.5, 4.5, 7.5, 10.5, 13.5, 16.5, 19.5, 22.5]) + hr
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __start_step_long_fcst_hour__ == 6:       
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5), (7, 11), (13, 17), (19, 23)]) + hr  
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True  
        elif __start_step_long_fcst_hour__ == 24:
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
        if __start_step_long_fcst_hour__ == 3:
            # applicable only for 3 hour average or accumutated.
            fcstHours = numpy.array([1.5, 4.5, 7.5, 10.5, 13.5, 16.5, 19.5, 22.5]) + hr
            # model itself produced 3 hourly average or accumutated. So we 
            # no need to do average/accumulation explicitly.
            doMultiHourlyMean = False
        elif __start_step_long_fcst_hour__ == 6:
            # applicable only for 6 hour average or accumutated.
            fcstHours = numpy.array([(1, 5), (7, 11), (13, 17), (19, 23)]) + hr 
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 6 hourly average/accumulation explicitly.
            doMultiHourlyMean = True 
        elif __start_step_long_fcst_hour__ == 24:
            # applicable only for 24 hour average or accumutated.
            fcstHours = numpy.array([(1, 23)]) + hr     
            # model produced 3 hourly average or accumutated. So we must 
            # need to do 24 hourly average/accumulation explicitly.
            doMultiHourlyMean = True    
        
    ##### FORECAST FILE END
    else:
        raise ValueError("Filename not implemented yet!")
    # end if-loop

    return varNamesSTASH, fcstHours, doMultiHourlyMean, infile
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
    fcstTm = tmpCube.coord('forecast_period')
    refTm = tmpCube.coord('forecast_reference_time')
    lat = tmpCube.coord('latitude')
    lon = tmpCube.coord('longitude')

    return stdNm, fcstTm, refTm, lat, lon
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
    # So we kept here unit as 'cm'. But points are muliplied by
    # 100 with its  corresponding cm values. Why because, that 
    # 100 will be factorized (divied) in grib_message by setting 
    # scaleFactorOfFirstFixedSurface as 2 and 
    # scaleFactorOfFirstFixedSurface as 2. So we must follow 
    # this procedure to get correct results.

    # Lets create new coords with 0, 2m infomation.   
    depth_below_land_surface = iris.coords.DimCoord(numpy.array([20000]), 
                      bounds=numpy.array([[0, 20000]]), units=Unit('cm'), 
                                    long_name='depth_below_land_surface') 
    # add the above created new coords to the cube 
    cube.add_aux_coord(depth_below_land_surface)    
# end of def _createDepthBelowLandSurfaceCoords1Lev():

def _updateDepthBelowLandSurfaceCoords4Levs(depth_below_land_surface):
    # Dr. Saji / UM_Model_DOC suggested that UM produce soil model
    # level number is equivalent to 10cm, 35cm, 1m & 2m. 
    # So we kept here unit as 'cm'. But points are muliplied by
    # 100 with its  corresponding cm values. Why because, that 
    # 100 will be factorized (divied) in grib_message by setting 
    # scaleFactorOfFirstFixedSurface as 2 and 
    # scaleFactorOfFirstFixedSurface as 2. So that in grib2 will
    # be able to read as 0.1 m, 0.35m, 1m & 2m. Iris will convert 
    # cm to m while saving into grib2 file. So we must follow 
    # this procedure to get correct results.
    depth_below_land_surface.points = numpy.array([1000, 3500, 10000, 20000])
    # we must set the bounds in vertical depths, since we required
    # to mention the four different layers depth properly.
    depth_below_land_surface.bounds = numpy.array([[0, 1000], 
                       [1000, 3500], [3500,10000],[10000,20000]])
    depth_below_land_surface.units = Unit('cm')
    depth_below_land_surface.long_name = 'depth_below_land_surface'    
    depth_below_land_surface.standard_name = None
# end of def _updateDepthBelowLandSurfaceCoords4Levs():

def _convert2VolumetricMoisture(cube, levels=[100.0, 250.0, 650.0, 1000.0]):
    #### Lets convert moisture_content_of_soil_layer into 
    ##  volumetric_moisture_of_soil_layer by divide each layer 
    ## with its layer depth in mm.
    ## Unit also gets changed from Kg/m2 into m3/m3. How ?
    ## voulumetric_soil_moisture = moisture_content_of_soil_layer / (density_of_water x depth_of_soil_layer)
    ## density_of_water is 1000 Kg/m3
    ## depth_of_soil_layer of first layer from 0 to 10 cm = 10/100 m
    ## depth_of_soil_layer of first layer from 10 to 35 cm = 25/100 m
    ## depth_of_soil_layer of first layer from 35 to 100 cm = 65/100 m
    ## depth_of_soil_layer of first layer from 100 to 200 cm = 100/100 m
    
    ## So if we apply the above values of density 1000 Kg/m3 
    ## & depth in meter in the denominator of voulumetric_soil_moisture
    ## equavation, we will endup with just divide first layer 
    ## by 100, second layer by 250, third layer by 650 and 
    ## fourth layer by 1000.
    
    ## By this way, we converted moisture_content_of_soil_layer 
    ## from Kg/m2 into voulumetric_soil_moisture_of_layer m3/m3.
    
    ## Reference : "Comparison of the Met Office soil moisture
    ## analyses with SMOS retrievals (2010-2011)", MARCH 2013.
    
    ## Link : http://www.researchgate.net/publication/257940913
    
    if isinstance(levels, (list, tuple)):   
        # This block of code for 4 different layers 
        for idx, dval in enumerate(levels):
            cube.data[idx] /= dval
    elif isinstance(levels, float):
        # this block of code for single layer 
        cube.data /= levels
    # end of for idx, denominator in enumerate([...]):
    
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
           __start_step_long_fcst_hour__, __anl_step_hour__, _requiredPressureLevels_ 
   
    fpname, hr = arg 
    
    ### if fileName has some extension, then do not add hr to it.
    fileName = fpname + hr if not '.' in fpname else fpname
    
    fname = os.path.join(_inDataPath_, fileName)        
    
    # call definition to get variable indices
    varNamesSTASH, fcstHours, doMultiHourlyMean, infile = getVarInOutFilesDetails(_inDataPath_,
                                                                               fileName, hr)
   
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
    
    if fpname.startswith('umglaa'):
        dtype = 'fcst'         
        outFileNameStructure = __fcstFileNameStructure__
        start_step_fcst_hour = __start_step_long_fcst_hour__
    elif fpname.startswith(('umglca', 'qwqg00')):
        dtype = 'ana'
        outFileNameStructure = __anlFileNameStructure__
        start_step_fcst_hour = __anl_step_hour__
    # end of if fpname.startswith('umglaa'):
    
    # get the out fileName Structure based on pre / user defined indecies                       
    outFnIndecies = __getAnlFcstFileNameIdecies__(outFileNameStructure)
    # get the file name extension
    fileExtension = outFileNameStructure[-1]
    #####
    ### setting timebound, fcstbound as 'centre' bounds, will not affect
    ### in g2ctl.pl because it uses flag -verf by default which will set 
    ### access time point as end time point of fcst bounds.
    timebound = 'cbound'            # TESTED, OK, on 05-01-2016
    fcstbound = 'cbound'            # TESTED, OK, on 05-01-2016
    if dtype == 'fcst':        
        ### But if we want to set access time point as per out file hour's
        ### ref time, then we can enable the following options. otherwise 
        ### disable it, because 'cbound' will works for ctl file.
        timebound = 'rbound'        # TESTED, OK, on 05-01-2016
        fcstbound = 'rbound'        # TESTED, OK, on 05-01-2016
    elif dtype == 'ana':        
        ### But if we want to set access time point as per out file hour's
        ### ref time, then we can enable the following options. otherwise 
        ### disable it, because 'cbound' will works for ctl file.
        timebound = 'lbound'        # TESTED, OK, on 23-02-2016
        fcstbound = 'lbound'        # TESTED, OK, on 23-02-2016
        ## g2ctl -verf option bring end forecast time bounds to set time in 
        ## ctl file. So we no need to pass options like -0 or -b.
        ## here lbound in both timebound and fcstbound will give correct 
        ## time reference and forecast time in both grib2 files and grads 
        ## control files.           # TESTED, OK, on 23-02-2016
    # end of if dtype == 'fcst':
    
    # Note : if we are not correcting ana, fcst fcstbound as above, in g2ctl
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
        # get the standard_name of variable 
        stdNm = cubes.extract(varConstraint & STASHConstraint)[0].standard_name
        print "stdNm", stdNm, infile
        if stdNm is None:
            print "Unknown variable standard_name for '%s' of %s. So skipping it" % (varName, infile)
            continue
        # end of if 'unknown' in stdNm: 
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
                    # previously defined in getVarInOutFilesDetails function.
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
                fcstHours = numpy.arange(24).reshape(4, 6) + int(fileName[-3:])
                print varName, "fcstHours ", fcstHours, int(fileName[-3:])
            elif dtype == 'ana':
                # for analysis pe file, and this varibale we need to set the 
                # extract time as follows. 
                # the cube contains data of every 1-hourly accumutated.
                # but we need to make only every 6th hourly accumutated.
                fcstHours = numpy.array([(1, 2, 3, 4, 5, 6)])
                ana_precip_infile = __getTodayOrYesterdayInfile__(_inDataPath_, fileName)    
                if ana_precip_infile != infile: 
                    cubes = getCubeData(ana_precip_infile)   
                    simulated_hr = int(ana_precip_infile.split('/')[-2])
                    print varName, "loaded from file, ", ana_precip_infile
                    print "simulated_hr = ", simulated_hr
                # end of if ana_infile != infile:               
        # end of if (varName, varSTASH) in _accumulationVars_:
        
        # define (simulated_hr) forecast_reference_time constraint
        fcstRefTimeConstraint = iris.Constraint(forecast_reference_time=PartialDateTime(hour=simulated_hr))
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
            
            if __anl_step_hour__ == 3 and fhr == 0 and fpname.startswith('umglca_pe'):
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
                                    iris.Constraint(forecast_period=fhr) &
                                    latConstraint & lonConstraint)[0]
                    print "special load of ana_hour 1.5"
                    print varName, "loaded from today infile, ", ana_today_infile
                    print "simulated_hr = ", simulated_hr            
            else:
                # extract cube with possible and required constraints
                tmpCube = cubes.extract(varConstraint & STASHConstraint & 
                                    fcstRefTimeConstraint &
                                    iris.Constraint(forecast_period=fhr) &
                                    latConstraint & lonConstraint)[0]
            # end of if __anl_step_hour__ == 3 and fhr == 1.5:
            
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
                                  tpoint=timebound, fpoint=fcstbound)
            # end of if doMultiHourlyMean and tmpCube.coords('forecast_period')[0].shape[0] > 1:     

            # interpolate it as per targetGridResolution deg resolution by 
            # setting up sample points based on coord
            print "\n Regridding data to %sx%s degree spatial resolution \n" % (_targetGridRes_, _targetGridRes_)
            if __LPRINT__: print "From shape", tmpCube.shape 
            if _doRegrid_:
                try:
                    # This lienar interpolate will do extra polate over ocean even 
                    # though original data doesnt have values over ocean and wise versa.
                    # So lets be aware of this.
                    # DO NOT APPLY iris.analysis.Linear(extrapolation_mode='mask'), 
                    # which writes nan every where for the snowfall_flux,  
                    # rainfall_flux, precipitation_flux. So donot apply that.               
                    regdCube = tmpCube.interpolate(_targetGrid_, iris.analysis.Linear())
                except Exception as e:
                    print "ALERT !!! Error while regridding!! %s" % str(e)
                    print " So skipping this without saving data"
                    continue
                # end of try:      
            else:
                # do not apply regrid. this is temporary fix. 
                regdCube = tmpCube
            # end of if _doRegrid_:
            
            if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
                regdCube.data[regdCube.data > 0] = 1
                # trying to keep values either 0 or 1. Not fraction!
                regdCube.data = numpy.ma.array(regdCube.data, dtype=numpy.int)
            # end of if (varName, varSTASH) in [('land_binary_mask', 'm01s00i030')]:
            
            if (varName, varSTASH) not in [('snowfall_flux', 'm01s05i215'),
                          ('precipitation_flux', 'm01s05i216'),
                          ('rainfall_flux', 'm01s05i214'),
                          ('stratiform_snowfall_amount', 'm01s04i202'),
                          ('convective_snowfall_amount', 'm01s05i202'),
                          ('stratiform_rainfall_amount', 'm01s04i201'),
                          ('convective_rainfall_amount', 'm01s05i201'),]:
                # For the above set of variables we shouldnot convert into 
                # masked array. Otherwise its full data goes as nan.                
                # convert data into masked array
                regdCube.data = numpy.ma.masked_array(regdCube.data, dtype=numpy.float64)
                                                
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
                # end of if ...:         
                # http://www.cpc.ncep.noaa.gov/products/wesley/g2grb.html
                # Says that 9.999e+20 value indicates as missingValue in grib2
                # by default g2ctl.pl generate "undefr 9.999e+20", so we must 
                # keep the fill_value / missingValue as 9.999e+20 only.
                numpy.ma.set_fill_value(regdCube.data, 9.999e+20)
            # end of if varName not in ['rainfall_flux', 'precipitation_flux', 'snowfall_flux']:            
            print "regrid done"
             
            if __LPRINT__: print "To shape", regdCube.shape  
                
            regdCube.attributes = tmpCube.attributes
            if __LPRINT__: print "set the attributes back to regdCube"              
            if __LPRINT__: print "regdCube => ", regdCube
            # get the regridded lat/lons
            stdNm, fcstTm, refTm, lat1, lon1 = getCubeAttr(regdCube)
            if __LPRINT__: print "Got attributes from regdCube"
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
            if regdCube.coords('soil_model_level_number'):
                # NOTE : THIS SECTION WILL WORKS ONLY FOR SOIL MOISTURE AND
                # SOIL TEMPERATUE AT 4 LAYERS, NOT FOR SINGLE LAYER OR 
                # NOT FOR Root zone Soil Moisture Content !!!
                 
                # Get soil_model_level_number coords from the cube.
                # We need to update this variable, which will be replicated
                # in the cube attributes. By default iris-1.9 will not 
                # support to handle soil_model_level_number, so we need to 
                # tweak it by following way.
                depth_below_land_surface = regdCube.coords('soil_model_level_number')[0]
                _updateDepthBelowLandSurfaceCoords4Levs(depth_below_land_surface)
                if __LPRINT__: print "depth_below_land_surface", depth_below_land_surface
                
                if regdCube.standard_name == 'moisture_content_of_soil_layer':
                    # pass the vertical layer depth in millimeter
                    _convert2VolumetricMoisture(regdCube, 
                                        levels=[100.0, 250.0, 650.0, 1000.0])
                    print "converted four layer soil moisture to volumetric"
                # end of if regdCube.standard_name == 'moisture_content_of_soil_layer':                
                               
                # We need to save this variable into nc file, why because
                # if we saved into grib2 and then re-read it while re-ordering
                # variables, iris couldnt load variables with 
                # depth_below_land_surfacer properly. We need to touch the 
                # _load_rules. So for timebeing, we saved it as seperate nc 
                # file. In iris-1.9 we couldnt append more variables into 
                # nc file. so we saved into muliple individual nc files, only
                # those who have depth_below_land_surface and will be deleted
                # after inserted properly into orderd grib2 files.
                outFn = varSTASH + '_'+ ofname + '.nc'
                ncfile = True
            # end of if regdCube.coords('soil_model_level_number'):
            
            if (varName, varSTASH) == ('soil_moisture_content', 'm01s08i208'):
                # NOTE : THIS SECTION WILL WORKS ONLY FOR SINGLE LAYERED 
                # Root zone Soil Moisture Content, NOT FOR 4 LAYERS.
                
                # By default this variable doesn't have any vertical coords 
                # inforomation. So we must add explicitly by ourself.
                _createDepthBelowLandSurfaceCoords1Lev(regdCube)
                
                # Convert this into volumetirc soil moisture. This varibale
                # vertical level at 2meter in millimeter.
                _convert2VolumetricMoisture(regdCube, levels=2000.0)
                print "converted single layer soil moisture to volumetric"
                outFn = varSTASH + '_'+ ofname + '.nc'
                ncfile = True
            # end of if (varName, varSTASH) in (...):
            
            if (varName, varSTASH) in _ncfilesVars_:
                # other than soil_model_level_number, few variables may be 
                # need to write into nc file and then convert to grib2. why 
                # because of duplicate grib param id (but actually not, if 
                # we implement typeOfFirstFixedSurface). so we are stoing into 
                # nc file, then load into memory (cf_standard_name) while 
                # re-ordering, followed by save into grib2 file. cf -> grib2 
                # dictionary may not throw error, due to different key cfname.
                ncfile = True
                outFn = varSTASH + '_'+ ofname + '.nc'
            # end of if (varName, varSTASH) in _ncfilesVars_:
            
            outFn = os.path.join(_opPath_, outFn)
            print "Going to be save into ", outFn
                        
            try:                
                # _lock_ other threads / processors from being access same file 
                # to write other variables
                _lock_.acquire()
                if ncfile:
                    iris.fileformats.netcdf.save(regdCube, outFn)  # save nc file 
                else:
                    iris.fileformats.grib.save_grib2(regdCube, outFn, append=True) # save grib2 file 
                # release the _lock_, let other threads/processors access this file.
                _lock_.release()
            except Exception as e:
                print "ALERT !!! Error while saving!! %s" % str(e)
                print " So skipping this without saving data"
                continue
            # end of try:
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
    global _ncmrGrib2LocalTableVars_, _aod_pseudo_level_var_
    
    for cube in cubeList:
        for cube, grib_message in iris.fileformats.grib.as_pairs(cube):
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
            # end of if cube.coord("forecast_period").bounds is not None:
            if cube.coords('depth_below_land_surface'):
                # scaleFactorOfFirstFixedSurface as 2, equivalent to divide
                # the depth_below_land_surface.points by 100. So that we can 
                # be sure that grib2 has 0.1m, 0.35m, 1m & 2m. Otherwise, we 
                # will endup with 0m, 0m, 1m & 2m and finally will loose 
                # information about decimal values of levels.
                gribapi.grib_set(grib_message, "scaleFactorOfFirstFixedSurface", 2)
                gribapi.grib_set(grib_message, "scaleFactorOfSecondFixedSurface", 2)
                print "reset scaleFactorOfFirstFixedSurface as 2"
                print "reset scaleFactorOfSecondFixedSurface as 2"
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
            # end of if cube.standard_name:                  
            print "Tweaking end ", cube.standard_name
            
            yield grib_message
        # end of for cube, grib_message in iris.fileformats.grib.as_pairs(cube):
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
           _createGrib1CtlIdxFiles_, _convertGrib2FilestoGrib1Files_, \
           _convertVars_, __outFileType__, __grib1FilesNameSuffix__, \
           __removeGrib2FilesAfterGrib1FilesCreated__, _removeVars_, \
           __start_step_long_fcst_hour__, g2ctl, grib2ctl, gribmap, cnvgrib
    
    try:        
        f = iris.load(fpath)
    except gribapi.GribInternalError as e:
        if str(e) == "Wrong message length":
            print "ALERT!!!! ERROR!!! Couldn't read grib2 file to re-order", e
        else:
            print "ALERT!!! ERROR!!! couldn't read grib2 file to re-order", e
        return 
    except Exception as e:
        print "ALERT!!! ERROR!!! couldn't read grib2 file to re-order", e
        return 
    # end of try:
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
    
    # need to store the ordered variables in this empty list
    orderedVars = []    
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
            
    ncloaddic = {}
    ncloadedfiles = []
    for (varName, varSTASH) in orderedVarsList:
        # skip if user specified var not in non-pressure level vars list 
        if not (varName, varSTASH) in _orderedVars_['nonPressureLevel']: continue
        # got non-pressure vars, add to ordered final vars list  
        if varName in unOrderedNonPressureLevelVars: 
            orderedVars.append(unOrderedNonPressureLevelVars[varName])
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
                # be going to saved into grib2 files by tweaking it further!                
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
    
    # store the land_binary_mask data into temporary variable
    land_binary_mask_var = [var for var in orderedVars 
                            if var.standard_name == 'land_binary_mask']
                                
    if _maskOverOceanVars_ and land_binary_mask_var:
        
        land_binary_mask = land_binary_mask_var[0].data < 1
        # here we are masking less than 1. we can do just simply == 0 also, 
        # but somehow it retains fraction values between 0 to 1. To get 
        # ride out of this fraction values, just mask out < 1.
        # get the shapes
        lsh = land_binary_mask.shape
        # Define constraint to extract latitude from 60S to 60N
        lat_60S_60N = iris.Constraint(latitude=lambda cell: -60 < cell < 60)
        lat_30S_30N = iris.Constraint(latitude=lambda cell: -30 < cell < 30)
        for vidx, var in enumerate(orderedVars):
            vname = var.standard_name if var.standard_name else var.long_name
            if vname in _maskOverOceanVars_:    
                # Lets reset zero values lies within 60S to 60N band
                # with 0.0051, before ocean region has been masked.
                # Now extract data only lies between 60S to 60N
                var_60S_60N = var.extract(lat_60S_60N)
                if vname == 'volumetric_moisture_of_soil_layer':
                    # reset the minimum values as 0.0051
                    var_60S_60N.data[var_60S_60N.data < 0.005] = 0.0051
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
                print "updated ocean masked vars"
        # end of for vidx, var in enumerate(orderedVars):
    # end of if _maskOverOceanVars_:
    
    # removing land_binary_mask_var from out files if it is forecast grib2 file
    # why do we need to repeat the same static variables in all the 
    # forecast files... So removing it, but keeps in analysis file.
    if __outFileType__ in ['prg', 'fcst'] and land_binary_mask_var and \
                                  __start_step_long_fcst_hour__ in [6]: 
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
        surface_upwelling_shortwave_flux = cubeSubtractor(surface_downwelling_shortwave_flux[0], 
                                           surface_net_downward_shortwave_flux[0], 
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
        surface_upwelling_longwave_flux = cubeSubtractor(surface_downwelling_longwave_flux[0], 
                                           surface_net_downward_longwave_flux[0], 
                       standard_name='surface_upwelling_longwave_flux_in_air',
                                                              removeSTASH=True)
        # store the 'surface_upwelling_longwave_flux' into orderedVars
        orderedVars.insert(idx, surface_upwelling_longwave_flux)
    # end of if ('surface_upwelling_longwave_flux_in_air', 'None') in _convertVars_:
    
    # remove temporary variables from ordered vars list 
    for dvar, dSTASH in _removeVars_:
        for ovar in orderedVars:
            # removed temporary vars from ordered vars list        
            if ovar.standard_name == dvar: orderedVars.remove(ovar)
    # end of for dvar in _removeVars_:

    # generate correct file name by removing _preExtension_
    g2filepath = fpath.split(_preExtension_)
    g2filepath = g2filepath[0] + g2filepath[-1]
    # now lets save the ordered variables into same file
    try:   
        # before save it, tweak the cubes by setting centre no and 
        # address other temporary issues before saving into grib2.
        iris.fileformats.grib.save_messages(tweaked_messages(orderedVars), 
                                                g2filepath, append=True)
    except Exception as e:
        print "ALERT !!! Error while saving orderd variables into grib2!! %s" % str(e)
        print " So skipping this without saving data"
        return 
    # end of try:
    
    # make memory free 
    del orderedVars
    
    # remove the older file 
    os.remove(fpath)
    for ncf in ncloadedfiles: os.remove(ncf)
        
    print "Created the variables in ordered fassion and saved into", g2filepath
                
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
                subprocess.call([grib2ctl, '-ts6hr', g1filepath], stdout=ctlfile)
                subprocess.call([gribmap, '-ts6hr', '-0', '-i', g1filepath+'.ctl'])
            elif __outFileType__ in ['prg', 'fcst']:
                # create ctl & idx files for forecast file
                subprocess.call([grib2ctl, '-ts6hr', '-verf', g1filepath], stdout=ctlfile)
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
        # by default -verf as passed which takes end time of fcst bounds to set as base time.
        subprocess.call([g2ctl, '-ts6hr', '-verf', g2filepath], stdout=ctlfile)
        subprocess.call([gribmap, '-i', g2filepath+'.ctl'])                
        print "Successfully created control and index file using g2ctl !", g2filepath+'.ctl'
    # end of if __removeGrib2FilesAfterGrib1FilesCreated__:    
# end of def doShuffleVarsInOrder(fpath):

def doShuffleVarsInOrderInParallel(ftype, simulated_hr):
            
    global _current_date_, _opPath_, _preExtension_, __max_long_fcst_hours__, \
           __anlFileNameStructure__, __fcstFileNameStructure__, \
           __max_long_fcst_hours__, __start_step_long_fcst_hour__, __utc__
            
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
        outFnIndecies = __getAnlFcstFileNameIdecies__(__fcstFileNameStructure__)
        fcstFiles = []
        for fcsthr in range(__start_step_long_fcst_hour__, 
                   __max_long_fcst_hours__+1, __start_step_long_fcst_hour__):            
            # generate the out file name based on actual informations                                 
            outFn = __genAnlFcstOutFileName__(__fcstFileNameStructure__, 
                                  outFnIndecies, _current_date_, fcsthr, 
                                           simulated_hr, _preExtension_)  
            fcstFiles.append(outFn)
        # end of for fcsthr in range(...):

        ## get the no of created fcst files  
        nprocesses = len(fcstFiles)        
        # parallel begin - 3
        pool = _MyPool(nprocesses)
        print "Creating %d (non-daemon) workers and jobs in doShuffleVarsInOrder process." % nprocesses
        results = pool.map(doShuffleVarsInOrder, fcstFiles)   
        
        # closing and joining master pools
        pool.close()     
        pool.join()
        # parallel end - 3    
    elif ftype in ['anl', 'analysis']:
        ## generate the analysis filename w.r.t simulated_hr
        # get the out fileName Structure based on pre / user defined indecies                       
        outFnIndecies = __getAnlFcstFileNameIdecies__(__anlFileNameStructure__) 
        anlFiles = []
        simulated_hr = int(__utc__)
        # since ncum producing analysis files 00, 06, 12, 18 utc cycles and 
        # its forecast time starting from 0 and reference time based on utc.
        # so we should calculate correct hour as below.
        for fcsthr in range(0+simulated_hr, 6+simulated_hr, __anl_step_hour__):            
            # generate the out file name based on actual informations                                 
            outFn = __genAnlFcstOutFileName__(__anlFileNameStructure__, 
                                  outFnIndecies, _current_date_, fcsthr, 
                                           simulated_hr, _preExtension_)  
            anlFiles.append(outFn)
        # end of for fcsthr in range(...):
        ## get the no of created anl files  
        nprocesses = len(anlFiles)        
        # parallel begin - 3
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
    global __max_long_fcst_hours__
    
    # here max fcst hours goes upto 240 only, not 241. why ??
    # because 216 long fcst hours contains upto 240th hour fcst.
    # and 240th long fcst contains upto 264th hour fcst.
    # so here no need to add +1 to __max_long_fcst_hours__.
    fcst_times = [str(hr).zfill(3) for hr in range(0, __max_long_fcst_hours__, 24)]
    fcst_filenames = [(fname, hr) for hr in fcst_times]
    nchild = len(fcst_times)
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
    
    global __max_long_fcst_hours__
    
    if ftype in ['ana', 'anl']:
        fhrs = ['000'] 
    elif ftype in ['fcst', 'prg']:
        # here max fcst hours goes upto 240 only, not 241. why ??
        # because 216 long fcst hours contains upto 240th hour fcst.
        # and 240th long fcst contains upto 264th hour fcst.
        # so here no need to add +1 to __max_long_fcst_hours__.
        fhrs = [str(hr).zfill(3) for hr in range(0, __max_long_fcst_hours__, 24)]
    
    fileNotExistList = []
    for pfname in pfnames:
        for fhr in fhrs:
            # constrct the correct fileName from partial fileName and hours
            # add hour only if doenst have any extension on partial filename.
            fname = pfname if '.' in pfname else pfname + fhr
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
    
    global _preExtension_, __max_long_fcst_hours__, __anlFileNameStructure__,\
           __fcstFileNameStructure__, __start_step_long_fcst_hour__, \
           __anl_step_hour__, __utc__
           
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
        fhrs = range(__start_step_long_fcst_hour__, __max_long_fcst_hours__+1, 
                                                __start_step_long_fcst_hour__)
    
    # get the out fileName Structure based on pre / user defined indecies
    outFnIndecies = __getAnlFcstFileNameIdecies__(outFileNameStructure)
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
       __LPRINT__, __utc__, __start_step_long_fcst_hour__, \
       __max_long_fcst_hours__, __outFileType__, __grib1FilesNameSuffix__, \
       __removeGrib2FilesAfterGrib1FilesCreated__, _depedendantVars_, \
       _removeVars_, _requiredPressureLevels_
     
    # load key word arguments
    targetGridResolution = kwarg.get('targetGridResolution', 0.25)
    date = kwarg.get('date', time.strftime('%Y%m%d'))
    utc = kwarg.get('utc', '00')
    overwrite = kwarg.get('overwrite', False)
    lprint = kwarg.get('lprint', False)
    convertVars = kwarg.get('convertVars', None)
    latitude = kwarg.get('latitude', None)
    longitude = kwarg.get('longitude', None)
    pressureLevels = kwarg.get('pressureLevels', None)
    start_step_long_fcst_hour = kwarg.get('start_step_long_fcst_hour', 6)
    max_long_fcst_hours = kwarg.get('max_long_fcst_hours', 240)
    fcstFileNameStructure = kwarg.get('fcstFileNameStructure', None)
    createGrib2CtlIdxFiles = kwarg.get('createGrib2CtlIdxFiles', True)
    createGrib1CtlIdxFiles = kwarg.get('createGrib1CtlIdxFiles', False)
    convertGrib2FilestoGrib1Files = kwarg.get('convertGrib2FilestoGrib1Files', False)
    grib1FilesNameSuffix = kwarg.get('grib1FilesNameSuffix', '1')
    removeGrib2FilesAfterGrib1FilesCreated = kwarg.get('removeGrib2FilesAfterGrib1FilesCreated', False)
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
    __utc__ = utc
    __start_step_long_fcst_hour__ = start_step_long_fcst_hour
    __max_long_fcst_hours__ = max_long_fcst_hours
    __removeGrib2FilesAfterGrib1FilesCreated__ = removeGrib2FilesAfterGrib1FilesCreated
    __grib1FilesNameSuffix__ = grib1FilesNameSuffix
    _targetGridRes_ = str(targetGridResolution)
    _requiredLat_ = latitude
    _requiredLon_ = longitude
    _requiredPressureLevels_ = pressureLevels    
    _createGrib2CtlIdxFiles_ = createGrib2CtlIdxFiles
    _createGrib1CtlIdxFiles_ = createGrib1CtlIdxFiles
    _convertGrib2FilestoGrib1Files_ = convertGrib2FilestoGrib1Files
    # forecast filenames partial name
    fcst_fnames = ['umglaa_pb','umglaa_pd', 'umglaa_pe', 'umglaa_pf', 'umglaa_pi']    
        
    # get the current date in YYYYMMDD format
    _tmpDir_ = tmpPath
    _current_date_ = date
    print "\n _current_date_ is %s" % _current_date_
    logpath = os.path.join(_tmpDir_, _current_date_)
    if not os.path.exists(logpath): os.makedirs(logpath)
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
            varNamesSTASH, _, _, _ = getVarInOutFilesDetails(_inDataPath_, fileName, hr)
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
    if not os.path.exists(_opPath_):  
        os.makedirs(_opPath_)
        print "Created directory", _opPath_
    # end of if not os.path.exists(_opPath_):  
    
    if not isinstance(targetGridResolution, (int, float)):
        raise ValueError("targetGridResolution must be either int or float")
        
    if targetGridResolution is None:
        _doRegrid_ = False  
    else:
        # define default global lat start, lon end points
        slat, elat = (-90., 90.)
        # define default global lon start, lon end points 
        slon, elon = (0., 360.)
        # define user defined custom lat & lon start and end points
        if latitude: (slat, elat) = latitude
        if longitude: (slon, elon) = longitude
        # target grid as 0.25 deg (default) resolution by setting up sample points 
        # based on coord    
        _targetGrid_ = [('latitude', numpy.arange(slat, 
                          elat+targetGridResolution, targetGridResolution)),
                        ('longitude', numpy.arange(slon, 
                          elon+targetGridResolution, targetGridResolution))]
        _doRegrid_ = True  
    # end of if targetGridResolution is None:
    
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
       _removeVars_, __anl_step_hour__, _requiredPressureLevels_
           
    # load key word arguments
    targetGridResolution = kwarg.get('targetGridResolution', 0.25)
    date = kwarg.get('date', time.strftime('%Y%m%d'))
    utc = kwarg.get('utc', '00')
    overwrite = kwarg.get('overwrite', False)
    lprint = kwarg.get('lprint', False)
    convertVars = kwarg.get('convertVars', None)
    latitude = kwarg.get('latitude', None)
    longitude = kwarg.get('longitude', None)
    pressureLevels = kwarg.get('pressureLevels', None)
    anl_step_hour = kwarg.get('anl_step_hour', 6)
    anlFileNameStructure = kwarg.get('anlFileNameStructure', None)
    createGrib2CtlIdxFiles = kwarg.get('createGrib2CtlIdxFiles', True)
    createGrib1CtlIdxFiles = kwarg.get('createGrib1CtlIdxFiles', False)
    convertGrib2FilestoGrib1Files = kwarg.get('convertGrib2FilestoGrib1Files', False)
    grib1FilesNameSuffix = kwarg.get('grib1FilesNameSuffix', '1')
    removeGrib2FilesAfterGrib1FilesCreated = kwarg.get('removeGrib2FilesAfterGrib1FilesCreated', False)
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
    __utc__ = utc
    __anl_step_hour__ = anl_step_hour
    __removeGrib2FilesAfterGrib1FilesCreated__ = removeGrib2FilesAfterGrib1FilesCreated
    __grib1FilesNameSuffix__ = grib1FilesNameSuffix
    _targetGridRes_ = str(targetGridResolution)
    _requiredLat_ = latitude
    _requiredLon_ = longitude
    _requiredPressureLevels_ = pressureLevels    
    _createGrib2CtlIdxFiles_ = createGrib2CtlIdxFiles
    _createGrib1CtlIdxFiles_ = createGrib1CtlIdxFiles
    _convertGrib2FilestoGrib1Files_ = convertGrib2FilestoGrib1Files
    # analysis filenames partial name
    anl_fnames = ['umglca_pb', 'umglca_pd', 'umglca_pe', 'umglca_pf', 'umglca_pi']  
    if utc == '00': anl_fnames.insert(0, 'qwqg00.pp0')
    
    # get the current date in YYYYMMDD format
    _tmpDir_ = tmpPath
    _current_date_ = date
    print "\n _current_date_ is %s" % _current_date_
    logpath = os.path.join(_tmpDir_, _current_date_)
    if not os.path.exists(logpath): os.makedirs(logpath)
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
            varNamesSTASH, _, _, _ = getVarInOutFilesDetails(_inDataPath_, fileName, hr)
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
    if not os.path.exists(_opPath_):  
        os.makedirs(_opPath_)
        print "Created directory", _opPath_
    # end of if not os.path.exists(_opPath_):  
    
    if not isinstance(targetGridResolution, (int, float)):
        raise ValueError("targetGridResolution must be either int or float")
    if targetGridResolution is None:
        _doRegrid_ = False  
    else:
        # define default global lat start, lon end points
        slat, elat = (-90., 90.)
        # define default global lon start, lon end points 
        slon, elon = (0., 360.)
        # define user defined custom lat & lon start and end points
        if latitude: (slat, elat) = latitude
        if longitude: (slon, elon) = longitude
        # target grid as 0.25 deg (default) resolution by setting up sample points 
        # based on coord    
        _targetGrid_ = [('latitude', numpy.arange(slat, 
                          elat+targetGridResolution, targetGridResolution)),
                        ('longitude', numpy.arange(slon, 
                          elon+targetGridResolution, targetGridResolution))]
        _doRegrid_ = True  
    # end of if targetGridResolution is None:
    
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
