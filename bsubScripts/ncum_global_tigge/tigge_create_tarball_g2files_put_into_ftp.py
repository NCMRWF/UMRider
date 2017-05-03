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

filesCount = {'ttr': 41, 'lsm': 41, 'orog': 41, '10v': 41, 'tcc': 41, 'gh': 369, 'skt': 41, 'tp': 41, 'msl': 41, 'mx2t6': 40, '2d': 41, '10u': 41, 'mn2t6': 40, 'sshf': 41, 'slhf': 41, 'ssr': 41, '2t': 41, 'sp': 41, 'st': 41, 'q': 328, 'u': 328, 't': 328, 'str': 41, 'v': 328, 'sd': 41}


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

    tDay = datetime.datetime.strptime(today, "%Y%m%d")
    lag1 = datetime.timedelta(days=1)
    yDay = (tDay - lag1).strftime('%Y%m%d')
    lag4 = datetime.timedelta(days=4)
    y4Day = (tDay - lag4).strftime('%Y%m%d')
    # get past 11th day timestamp
    y11Day = (tDay - datetime.timedelta(days=11)).strftime('%Y%m%d')
    
    tardir = '../../TarFiles/%s' % today
    if not os.path.exists(tardir): os.makedirs(tardir)
    tarfile = 'ncmrwf_tigge_%s_%s.tar.gz' % (today, member)
    print "currnet path : ", os.getcwd()
    # normal "$ tar cvjf fcst_20160223.tar.bz2 *fcst*grb2" cmd takes 6 minutes 43 seconds.
    #
    # where as in parallel bz2, "$ tar -c *fcst*grb2 | pbzip2 -v -c -f -p32 -m500 > fcst_20160223_parallel.tar.bz2" cmd takes only just 23 seconds alone, with 32 processors and 500MB RAM memory.
    #
    # create analysis files tar file in parallel # -m500 need to be include for pbzip2
    tg_files = '  '.join([' -C %s . ' % os.path.join(inpath, tgf) for tgf in os.listdir('.')])
    cmd = "tar -c  %s | %s -v  -c -f -p32 > %s/%s" % (tg_files, pigz, tardir, tarfile)
    
    print cmd
    subprocess.call(cmd, shell=True)
            
    if member == '000':
        tarpath = os.path.abspath(tardir)        
        
        
        # do scp the tar files to ftp_server
        cmd = 'ssh ncmlogin3 "rsync  --update --ignore-existing -razt  %s  %s:/data/ftp/pub/outgoing/NCUM_TIGGE/"' % (tarpath, ftp_server)
        print cmd
        subprocess.call(cmd, shell=True)
        
        # remove past 11th day tar ball from ftp_server 
        cmd = 'ssh ncmlogin3 "ssh %s rm -rf /data/ftp/pub/outgoing/NCUM_TIGGE/%s"' % (ftp_server, y11Day)
        print cmd
        try:
            subprocess.call(cmd, shell=True)
        except Exception as e:
            print "past 11th day tar ball has been removed from ftp_server, already", e   
        
        
        # remove yesterday directory!!!
        y4DayPath = os.path.join(path, '../../%s' % y4Day)
        if os.path.exists(y4DayPath):    
            cmd = "rm -rf %s" % y4DayPath
            print cmd
            subprocess.call(cmd, shell=True)
        # end of if os.path.exists(y4DayPath):     
        
        # remove past 11th day tar file!!!
        y11DayPath = os.path.join(path, '../../TarFiles/%s' % y11Day)
        if os.path.exists(y11DayPath):    
            cmd = "rm -rf %s" % y11DayPath
            print cmd
            subprocess.call(cmd, shell=True)
        # end of if os.path.exists(y11DayPath):      
    # end of if member == '000':
    os.chdir(cdir)  
# end of def createTarBalls(path, today, ...):

if __name__ == '__main__':

    ftp_server="prod@ftp"
    date = None
    member = '000'
    outpath = '/gpfs4/home/arulalan/um2grb2/ArulTest/NCUM_TIGGE/EPS/%s/'
    
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

