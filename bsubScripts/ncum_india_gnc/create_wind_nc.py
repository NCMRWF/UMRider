#!/usr/bin/env python

## This is call back script which will be executed after created the grib2 files.
## 
## Hycom Model Input requires analysis of 06, 09, 12, 15, 18, 21-hours from 
## yesterday and 00 & 03-hours from today date. All 3-hourly forecasts from
## today date.
## 
## While creating tar ball, all files must be in present directory, so that
## when user extract it, will produce only files instead of entire paths!
##
## And finally putting into their ftp server.
##
## Arulalan.T
## 05-Jan-2017.

import os, subprocess, datetime, getopt, sys, glob, time

wgrib2 = '/gpfs1/home/Libs/GNU/WGRIB2/v2.0.4/wgrib2/wgrib2'

def createNetCdfFile(path, today, utc):    

    cdir = os.getcwd()
    os.chdir(path)
    filename = 'wind_%shr_%s_00Z.grib2'
    outfile = 'wind_%s.nc' % today
    if os.path.isfile(outfile):
        cmd = 'rm %s' % ' '.join(outfile)
        print cmd
        subprocess.call(cmd, shell=True)

    infiles = []
    for hr in range(0, 241, 24):
        infile = filename % (str(hr).zfill(3), today)        
        cmd = '%s -append -nc_grads -netcdf %s %s' % (wgrib2, outfile, infile)
        print cmd
        subprocess.call(cmd, shell=True)
        infiles.append(infile)        
    # end of for hr in range(24, 241, 24):
    time.sleep(10)
    cmd = 'rm %s' % ' '.join(infiles)
    print cmd
    subprocess.call(cmd, shell=True)
        
    os.chdir(cdir)  
# end of def createNetCdfFile(path, today, ...):

if __name__ == '__main__':

    
    date = None
    outpath = None
    oftype = None
    utc = None
    helpmsg = 'create_wind_nc.py --date=20160302 --outpath=path --oftype=analysis --utc=00'
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:o:t:z:", ["date=","outpath=", "oftype=", "utc="])
    except getopt.GetoptError:
        print helpmsg
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print helpmsg
            sys.exit()
        elif opt in ("-d", "--date"):
            date = arg
        elif opt in ("-o", "--outpath"):
            outpath = arg 
        elif opt in ("-t", "--oftype"):
            oftype = arg
        elif opt in ("-z", "--utc"):
            utc = arg
    # end of for opt, arg in opts:
    
    # create tar balls only if forecast & utc is 00, otherwise skip it!    
    if oftype == 'forecast' and utc == '00': 
        # pass the arg to function  
        createNetCdfFile(outpath, date, utc)    
    # end of if oftype == 'forecast' and utc == '00': 
