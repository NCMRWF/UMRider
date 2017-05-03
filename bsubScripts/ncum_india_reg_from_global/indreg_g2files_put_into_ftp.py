#!/usr/bin/env python

## This is call back script which will be executed after created the grib2 files.
## 
## In parallel mode we are copying individual grib2 files into ftp server.
## 

## Arulalan.T
## 15-Mar-2016.

import os, sys, getopt, subprocess, datetime
import multiprocessing as mp

def putintoftp(today, outpath, oftype, utc):
    cdir = os.getcwd()
    os.chdir(outpath)
    
    tDay = datetime.datetime.strptime(today, "%Y%m%d")
    # get past 11th day timestamp
    y11Day = (tDay - datetime.timedelta(days=11)).strftime('%Y%m%d')
    
    if oftype == 'analysis':
        prefix = 'NCUM_IND_ana'
    elif oftype == 'forecast':
        prefix = 'NCUM_IND_fcs'
        
    # take only grib2 files, not ctl and not idx files.
    gfiles = [f for f in os.listdir(outpath) if f.endswith('.grib2') if f.startswith(prefix)]    
    if oftype == 'analysis': gfiles = [f for f in gfiles if utc.zfill(3)+'hr' in f]
    gfiles = ' '.join([os.path.join(outpath, f) for f in gfiles])
    
    # do scp the grib2 files to ftp_server 
    cmd = 'ssh ncmlogin3 "ssh %s mkdir -p /data/ftp/pub/outgoing/NCUM_IND/0.25/%s"' % (ftp_server, today)
    print cmd
    try:
        subprocess.call(cmd, shell=True)
    except Exception as e:
        print "Folder already exists", e

    cmd = 'ssh ncmlogin3 "rsync -avrt %s %s:/data/ftp/pub/outgoing/NCUM_IND/0.25/%s/"' % (gfiles, ftp_server, today)
    print cmd
    try:
        subprocess.call(cmd, shell=True)   
    except Exception as e:
        print "Files already exists", e

    # do scp the grib2 files to nkn_server 
    cmd = 'ssh ncmlogin3 "ssh %s mkdir -p NCUM_IND/0.25/%s"' % (nkn_server, today)
    print cmd
    try:
        subprocess.call(cmd, shell=True)
    except Exception as e:
        print "Folder already exists", e
        
    cmd = 'ssh ncmlogin3 "rsync -avrt %s %s:NCUM_IND/0.25/%s/"' % (gfiles, nkn_server, today)
    print cmd
    try:
        subprocess.call(cmd, shell=True)   
    except Exception as e:
        print "Files already exists", e
    
    
    if oftype == 'analysis':
        # remove past 11th day tar ball from ftp_server 
        cmd = 'ssh ncmlogin3 "ssh %s rm -rf /data/ftp/pub/outgoing/NCUM_IND/0.25/%s"' % (ftp_server, y11Day)
        print cmd
        try:
            subprocess.call(cmd, shell=True)
        except Exception as e:
            print "past 11th day folder has been removed from ftp_server, already", e
        # remove past 11th day tar ball from nkn_server 
        cmd = 'ssh ncmlogin3 "ssh %s rm -rf /home/imd/NCUM_IND/0.25/%s"' % (nkn_server, y11Day)
        print cmd
        try:
            subprocess.call(cmd, shell=True)
        except Exception as e:
            print "past 11th day folder has been removed from nkn_server, already", e
    # end of if oftype == 'analysis':
    
    os.chdir(cdir)
# end of def renameFiles(outpath):

if __name__ == '__main__':
    
    nkn_server="imd@nkn"
    ftp_server="prod@ftp"
    date = None
    outpath = None
    oftype = None
    utc = None
    helpmsg = 'indreg_g2files_put_into_ftp.py --date=20160302 --outpath=path --oftype=analysis --utc=00'
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
    
    # pass the arg to function  
    putintoftp(date, outpath, oftype, utc)
