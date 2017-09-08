#!/usr/bin/env python

## This is call back script which will be executed after created the grib2 files.
## 
## After created NCUM_EPS grib2 files (which contain all 45 members in it), lets
## do calculate mean over all 45 members and then convert to 2.5X2.5 degree 
## resolution, finally convert to grib1 format for vsdb input purpose.
##
## Arulalan.T
## 19-Aug-2016.

import os, subprocess, datetime, getopt, sys, iris, numpy, time 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../g2utils')))
from cubeutils import cubeRealizationAverager
from um2grb2 import tweaked_messages, getCubeData, createDirWhileParallelRacing


neededVars = [
    ## Pressure Level Variable names & STASH codes
    ('geopotential_height', 'm01s16i202'),      
    ('x_wind', 'm01s15i243'),
    ('y_wind', 'm01s15i244'), 
    ('air_temperature', 'm01s16i203'),
    ('relative_humidity', 'm01s16i256'),
    ## Non Pressure Level Variable names & STASH codes
    ('air_pressure_at_sea_level', 'm01s16i222'),
    ]

#Define _precipVars_
# The following vars should contains only precipitation, rainfall, snow 
# variables, those whose regrid extrapolate should be only in 'linear' mode
# and not in 'mask' mode, and should not have -ve values.
_precipVars_ = [('precipitation_amount', 'm01s05i226'),]

g2ctl = "/gpfs2/home/umtid/Softwares/grib2ctl/g2ctl.pl"
grib2ctl = "/gpfs2/home/umtid/Softwares/grib2ctl/grib2ctl.pl"
gribmap = "/gpfs1/home/Libs/GNU/GRADS/grads-2.0.2.oga.1/Contents/gribmap"
cnvgrib = "/gpfs1/home/Libs/INTEL/CNVGRIB/CNVGRIB-1.4.1/cnvgrib-1.4.1/cnvgrib"

__grib1FilesNameSuffix__ = None
__OVERWRITE__ = True
_reverseLatitude_ = True
_preExtension_ = '_unOrdered'


targetGridResolution = 2.5
# define default global lat start, lon end points
slat, elat = (-90., 90.)
# define default global lon start, lon end points 
slon, elon = (0., 360.)
# reduce one step if user passed / default lon is 360. If we write 
# longitude from 0 upto 360, wgrib2 reads it as 0 to 0. To avoid it, 
# just reduct one step in longitude only incase of 360.
if int(elon) == 360: elon -= targetGridResolution 
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
    
def createENSavg_VSDB_Grib1Files(inpath, outpath, today, utc, start_long_fcst_hour):    

    inpath = os.path.join(inpath, today)
    pfileday = str(start_long_fcst_hour).zfill(3)
    day = int(start_long_fcst_hour) / 24
    pfilename = 'umeps_prg_1cntl_44ens_%s_' + pfileday
    needed_fname = pfilename + 'hr_' + today + '_' + utc + 'Z' + _preExtension_ + '.grib2'    
    
    tDay = datetime.datetime.strptime(today, "%Y%m%d")        
    tvDay = tDay.strftime('%d%m%y')
    
    opath = os.path.join(outpath, today)
    createDirWhileParallelRacing(opath)            
    g2filepath = os.path.join(opath, 'prg%d%sz%s.grib2' % (day, utc.zfill(2), tvDay))    
    if __OVERWRITE__ and os.path.isfile(g2filepath): os.remove(g2filepath)
    
    ensfpath_list = []
    for varName, varSTASH  in neededVars:
        ext = '2df' if varSTASH == 'm01s16i222' else 'prs'
        varfilename = varSTASH + '_' + needed_fname % ext
        files = [f for f in os.listdir(inpath) if f == varfilename]
        if not files: return 
        ensfpath = os.path.join(inpath, files[0])
        inf = iris.load(ensfpath)
        # define variable name constraint
        varConstraint = iris.Constraint(name=varName)
        print varName, varSTASH
        ensCube = inf.extract(varConstraint)
        if not ensCube: continue        
        print "doing members average for", varName
        # do average over ensembles (1 control + 44 ensemble members)
        ensAvgCube = cubeRealizationAverager(ensCube[0])
        # make memory free
        del ensCube
        
        # Fix latitude and longitude issues
        # FOR VSDB, it requires lat from -90 to 90 and lon from 0 to 357.5.
        # But here it starts from -89.5 to 89.5 and lon from 0.35 to 359.5.
        # when we do regrid from 0.35x0.35 to 2.5x2.5, it get NaN filled over 
        # 90S, 90N, 0E, 357.5E (all four corners). So we are fixing this issue 
        # by changing the corners as like below, and it will resolve the 
        # interpolation Nan problems.
        latitude = ensAvgCube.coords('latitude')[0]
        latp = latitude.points.tolist()
        latp[0] = -90.0
        latp[-1] = 90.0
        latitude.points = numpy.array(latp)

        longitude = ensAvgCube.coords('longitude')[0]
        lonp = longitude.points.tolist()
        lonp[0] = 0.0
        lonp[-1] = 360.0
        longitude.points = numpy.array(lonp)
        
        # Here while making average across all realization, it creates NaN
        # over all corners of the dataset (may be becase some one of the realization
        # has NaN or something else). So we are just copying the second most 
        # row (lat) data to last lat row data.
        esh = len(ensAvgCube.data.shape)
        edata = ensAvgCube.data
        if esh == 3:
            edata[:, 0] = edata[:, 1, :]
            edata[:, -1] = edata[:, -2, :]
        elif esh == 2:
            edata[0] = edata[1, :]
            edata[-1] = edata[-2, :]
        # Togethese these two adjustments, it will create 2.5x2.5 vsdb perfect
        # grib1 files. # TESTED on 07-Oct-2016.
        ensAvgCube.data = edata                
        exmode = 'mask'
        try:
            # This lienar interpolate will do extra polate over ocean even 
            # though original data doesnt have values over ocean and wise versa.
            # So lets be aware of this.            
            regdCube = ensAvgCube.interpolate(_targetGrid_, iris.analysis.Linear(extrapolation_mode=exmode))
        except Exception as e:
            print "ALERT !!! Error while regridding!! %s" % str(e)
            print " So skipping this without saving data"
            continue
        # end of try:      
        
        # make memory free
        del ensAvgCube
        
        if (varName, varSTASH) in _precipVars_:
            # Since we are not using 'mask' option for extrapolate while 
            # doing linear regrid, which bring -ve values after regrid in 
            # extrapolated grids. So lets make it as 0 as minimum value.
            regdCube.data[regdCube.data < 0.0] = 0.0
        # end of if (varName, varSTASH) in _precipVars_:
        
        if exmode == 'mask':
            regdCube.data = numpy.ma.masked_array(regdCube.data, 
                                dtype=numpy.float64, fill_value=9.999e+20) 

        if _reverseLatitude_:   # required for VSDB 90 to -90 and it shoule be 
            # revered before regridding. Because we kept target grid file as
            # VSDB grib.
            # Need to reverse latitude from SN to NS
            rcsh = len(regdCube.data.shape)
            if rcsh == 3:
                regdCube.data = regdCube.data[:,::-1,:]
            elif rcsh == 2:
                regdCube.data = regdCube.data[::-1,:]
            lat = regdCube.coords('latitude')[0]
            lat.points = lat.points[::-1]
            print "latitude reverse done ........................."
        # end of if _reverseLatitude_:
        
        # save into grib2 file 
        iris.fileformats.grib.save_messages(tweaked_messages([regdCube]), 
                                                     g2filepath, append=True) # save grib2 file        
        
        print "Appending %s to grib2 file" % varName
        # make memory free
        del regdCube      
        time.sleep(15)
        ensfpath_list.append(ensfpath)
    # end of for varName, varSTASH  in neededVars:                      
    time.sleep(15)
    
    cmd = 'rm -rf ' + '  '.join(ensfpath_list)
    subprocess.call(cmd, shell=True)
    
    # Conver grib2 to grib1 
    g1filepath = '.'.join(g2filepath.split('.')[:-1])
    g1filepath = g1filepath if g1filepath else g2filepath[:-1]
    if __grib1FilesNameSuffix__: g1filepath += str(__grib1FilesNameSuffix__)
    
    if os.path.isfile(g1filepath): os.remove(g1filepath)
    
    cmd = [cnvgrib, '-g21', g2filepath, g1filepath]
    subprocess.call(cmd, shell=False)
    cmd = ['chmod', '644', g1filepath]
    subprocess.call(cmd, shell=False)
    print "Converted grib2 to grib1 file : -", g1filepath
    time.sleep(15)
    os.remove(g2filepath)                         
# end of def createTarBalls(path, today, ...):

if __name__ == '__main__':

    
    date = None
    oftype = 'forecast'
    utc = '00'
    inpath = '/gpfs3/home/umeps/EPS/long_fcst/post/'
    outpath = '/gpfs3/home/umeps/EPS/ShortJobs/NCUM_EPS_VSDB_Input'
  
    helpmsg = './ncumeps_create_memavg_vsdb_input.py --date=20160302 --start_long_fcst_hour=24 --end_long_fcst_hour=24'
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:s:e", ["date=",
            "start_long_fcst_hour=", "end_long_fcst_hour="])
    except getopt.GetoptError:
        print helpmsg
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print helpmsg
            sys.exit()
        elif opt in ("-d", "--date"):
            date = arg
        elif opt in ("-s", "--start_long_fcst_hour"):
            start_long_fcst_hour = arg
        elif opt in ("-e", "--end_long_fcst_hour"):
            end_long_fcst_hour = arg
    # end of for opt, arg in opts:
    
    if not date and os.environ.has_key('UMRIDER_STARTDATE'):
        date = os.environ.get('UMRIDER_STARTDATE')
        print "date is overridden by environment variable UMRIDER_STARTDATE", date
    
    # create tar balls only if forecast & utc is 00, otherwise skip it!    
    if oftype == 'forecast' and utc == '00': 
        # pass the arg to function  
        createENSavg_VSDB_Grib1Files(inpath, outpath, date, utc, start_long_fcst_hour)    
    # end of if oftype == 'forecast' and utc == '00': 
