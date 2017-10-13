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
## 04-Mar-2016.

import os, subprocess, datetime, getopt, sys, glob

pbzip2 = '/gpfs1/home/Libs/GNU/ZIPUTIL/pbzip2'
pigz = '/gpfs1/home/Libs/GNU/ZIPUTIL/pigz'
tigge_check = '/gpfs2/home/prasanna/SOFTWARE/GNU/grib_api-1.21.0-path/bin/tigge_check'

filesCount = {'ttr': 41, 'lsm': 41, 'orog': 41, '10v': 41, 'tcc': 41, 'gh': 369, 'skt': 41, 'tp': 41, 'msl': 41, 'mx2t6': 40, '2d': 41, '10u': 41, 'mn2t6': 40, 'sshf': 41, 'slhf': 41, 'ssr': 41, '2t': 41, 'sp': 41, 'st': 41, 'q': 328, 'u': 328, 't': 328, 'str': 41, 'v': 328, 'sd': 41}

dirsOrder = [
    'gh', 'u', 'v', 'q', 't', '10u', '10v', '2t', 'mx2t6', 'mn2t6', 'skt', 'st', 
    '2d', 'sp', 'msl', 'tp', 'ttr', 'lsm', 'tcc', 'slhf', 'ssr', 'sshf', 'str', 'sd', 'orog'
]
# merge cmd into single grib2 of each members
catcmd = ['%s/z_tigge_c_dems*%s' % (d,d) for d in dirsOrder]
catcmd = '    '.join(catcmd)
catcmd = 'cat %s ' % catcmd
catcmd += '  > %s'

def createTarBalls(path, today, member):    
    
    member = str(member).zfill(3)
    inpath = os.path.join(path, member)
    
    # check the filesCount
    for var, vlen in filesCount.iteritems():
        vpath = os.path.join(inpath, var)
        if not os.path.exists(vpath):
            raise ValueError("%s Folder doensnt exists" % vpath)
        files = os.listdir(vpath)
        if len(files) != vlen: 
            raise ValueError("filesCount do not matches,%s %d, %d" % (vpath, len(files), vlen))
        ncfile = [f for f in files if f.endswith('.nc')]
        if ncfile: raise ValueError("Got nc file %s" % vpath)
    # end of for var, vlen in filesCount.iteritems():
    
    cdir = os.getcwd()
    os.chdir(inpath)
    
    for tgf in os.listdir('.'):
        cmd = tigge_check + '   -v -w %s/*' % tgf
        tigge_check_val = os.system(cmd)  # it should return 0 on pass 
        if tigge_check_val != 0 : 
            print "WARNING : While checking via tigge_check cmd got error!"
            #sys.exit(0)
    # end of for tgf in os.listdir('.'):
    
    tDay = datetime.datetime.strptime(today, "%Y%m%d")
    lag1 = datetime.timedelta(days=1)
    yDay = (tDay - lag1).strftime('%Y%m%d')
    lag4 = datetime.timedelta(days=4)
    y4Day = (tDay - lag4).strftime('%Y%m%d')
    # get past 11th day timestamp
    y11Day = (tDay - datetime.timedelta(days=11)).strftime('%Y%m%d')
    
    tardir = '../../TarFiles/%s' % today
    if not os.path.exists(tardir): os.makedirs(tardir)
    mergedg2file = 'ncmrwf_dems_tigge_%s_%s.grib2' % (today, member)
    mergedg2filepath = os.path.join(tardir, mergedg2file)
    print "currnet path : ", os.getcwd()
    # merge all the params, all the levels, all the time steps, but individual members 
    # into single grib2 (BIG) file.
    catcmd_out = catcmd % mergedg2filepath
    subprocess.call(catcmd_out, shell=True)
    time.sleep(30)
    # Lets compress single BIG grib2 file by using gz compress cmd.
    os.chdir(tardir)
    gzip_cmd = '%s -9 -p 32 %s' % (pigz, mergedg2file)
    print "gzip_cmd = ", gzip_cmd
    subprocess.call(gzip_cmd, shell=True)
    time.sleep(5)
            
    # remove yesterday directory!!!
    yDayPath = os.path.join(path, '../../%s' % yDay)
    if os.path.exists(yDayPath):    
        cmd = "rm -rf %s" % yDayPath
        print cmd
        subprocess.call(cmd, shell=True)
    # end of if os.path.exists(yDayPath):     
     
    os.chdir(cdir)  
# end of def createTarBalls(path, today, ...):

if __name__ == '__main__':

    ftp_server="prod@ftp"
    date = None
    member = '000'
    outpath = '/gpfs3/home/umeps/EPS/ShortJobs/NCUM_EPS_TIGGE/%s/'
    
    helpmsg = 'tigge_create_tarball_g2files_put_into_ftp.py --date=20160302 --member=001'
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:m:", ["date=", "member="])
    except getopt.GetoptError:
        print helpmsg
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print helpmsg
            sys.exit()
        elif opt in ("-d", "--date"):
            date = arg        
        elif opt in ("-m", "--member"):
            member = arg 
    # end of for opt, arg in opts:
    
    outpath = outpath % date
    createTarBalls(outpath, date, member)    

