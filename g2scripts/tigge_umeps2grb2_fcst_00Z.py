"""
This is simple script to invoke parallel conversion function from um2grb2
and pass the assimilated / forecasted hour as argument.

UTC : 00Z
fcst hour : 006hr, 012hr, 018hr, ..., 234hr, 240hr
Output : It creates forecast - 40 files 
         (um_prg_006hr_date_00Z.grib2, ..., um_prg_240hr_date_00Z.grib2).
Written by : Arulalan.T
Date : 07.Dec.2015
"""

import os, sys, datetime, getopt
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from loadconfigure import inPath, outPath, tmpPath, date, loadg2utils, \
                 debug, targetGridResolution, overwriteFiles, neededVars, \
                 requiredLat, requiredLon, end_long_fcst_hour_at_00z, \
                 fcstOutGrib2FilesNameStructure, createGrib2CtlIdxFiles, \
                 createGrib1CtlIdxFiles, convertGrib2FilestoGrib1Files, \
                 start_long_fcst_hour, fcst_step_hour, grib1FilesNameSuffix, \
                 removeGrib2FilesAfterGrib1FilesCreated, pressureLevels, \
                 callBackScript, setGrib2TableParameters, targetGridFile, \
                 fillFullyMaskedVars, extraPolateMethod, wgrib2Arguments

if loadg2utils == 'system':
    # Load g2utils from system python which has installed through setup.py
    from g2utils.umeps2grb2 import convertFcstFiles
    print "INFO : imported g2utils.um2grb2 from system python"
elif loadg2utils == 'local':
    # Load g2utils from previous directory for the operational purpose, 
    # where normal user don't have write permission to change the g2utils!
    g2utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                            '../g2utils'))
    sys.path.append(g2utils_path)
    from um2grb2tigge import convertEPSFcstFiles
    print "INFO : imported g2utils.um2grb2 from local previous directory"
    print "loaded from g2utils_path : ", g2utils_path
    
if isinstance(date, tuple):
    # Got tuple of date string.
    startdate, enddate = date
    print "Got tuple dates"
    print "So um2grb2 fcst 00Z conversion - from %s to %s" % (startdate, enddate)
elif isinstance(date, str):
    # only single date
    startdate, enddate = date, date
    print "Got single string date"
    print "So um2grb2 fcst 00Z conversion - on %s" % date
# end of if isinstance(date, tuple):

helpmsg = 'umeps2grb2_fcst_00Z.py --start_long_fcst_hour=48 --end_long_fcst_hour=240'
    
try:
    opts, args = getopt.getopt(sys.argv[1:], "s:e:", ["start_long_fcst_hour=","end_long_fcst_hour="])
except getopt.GetoptError:
    print helpmsg
    opts = [('', ''),] # just store empty strins.
    print "WARNING : No command line arguments was passed. So just using configure setupfile itself."
#    sys.exit(2)
for opt, arg in opts:
    if opt == '-h':
        print helpmsg
        sys.exit()
    elif opt in ("-s", "--start_long_fcst_hour"):
        start_long_fcst_hour = int(arg)
        print "WARNING : start_long_fcst_hour option got overridden by command line argument"
        print "Updated 'start_long_fcst_hour = %d' " % start_long_fcst_hour
    elif opt in ("-e", "--end_long_fcst_hour"):
        end_long_fcst_hour_at_00z = int(arg)
        print "WARNING : end_long_fcst_hour option got overridden by command line argument" 
        print "Updated 'end_long_fcst_hour = %d' " % end_long_fcst_hour_at_00z
# end of for opt, arg in opts:

sDay = datetime.datetime.strptime(startdate, "%Y%m%d")
eDay = datetime.datetime.strptime(enddate, "%Y%m%d")
lag = datetime.timedelta(days=1)
while sDay <= eDay:
    # loop through until startdate incremented upto enddate
    print "Going to start progress on", startdate
    # call forecast conversion function w.r.t data assimilated 
    # during long forecast hour - 00UTC.        
    convertEPSFcstFiles(inPath, outPath, tmpPath, 
                                targetGridFile=targetGridFile,
                    targetGridResolution=targetGridResolution, 
             date=startdate, utc='00', convertVars=neededVars, 
                  latitude=requiredLat, longitude=requiredLon,
                                pressureLevels=pressureLevels,
                          extraPolateMethod=extraPolateMethod,
                      fillFullyMaskedVars=fillFullyMaskedVars,                                
         fcstFileNameStructure=fcstOutGrib2FilesNameStructure, 
                createGrib2CtlIdxFiles=createGrib2CtlIdxFiles,
                createGrib1CtlIdxFiles=createGrib1CtlIdxFiles,
  convertGrib2FilestoGrib1Files=convertGrib2FilestoGrib1Files, 
                    grib1FilesNameSuffix=grib1FilesNameSuffix,          
  removeGrib2FilesAfterGrib1FilesCreated=removeGrib2FilesAfterGrib1FilesCreated,
                    start_long_fcst_hour=start_long_fcst_hour,
                 end_long_fcst_hour=end_long_fcst_hour_at_00z,
                                fcst_step_hour=fcst_step_hour,             
                       overwrite=overwriteFiles, lprint=debug,
              setGrib2TableParameters=setGrib2TableParameters,
                              wgrib2Arguments=wgrib2Arguments,
                                callBackScript=callBackScript)
    print "Time lag incremented by 1"
    sDay += lag
    startdate = sDay.strftime('%Y%m%d')
# end of while sDay <= eDay:
print "Successfully completed all the dates till", enddate
