This will produce forecast ensembles 00utc files.

$ bsub -J umeps2g2[$i] < ncumeps_global_post_fcst_00Z_2df.bash

This will produce long forecast 00utc files with 6-hourly intervals by packing all 45 members together (2d instantaneous fileds).

$ bsub -J umeps2g2[$i] < ncumeps_global_post_fcst_00Z_flx.bash

This will produce long forecast 00utc files with 6-hourly intervals by packing all 45 members together (2d flux average/accumulation fileds).

$ bsub -J umeps2g2[$i] < ncumeps_global_post_fcst_00Z_prs.bash

This will produce long forecast 00utc files with 6-hourly intervals by packing all 45 members together (3d pressure fileds).

$ bsub -J umeps2vsdbanl < ncumeps_global_vsdb_anl.bash 
$ bsub -J umeps2vsdbfcst[$i] < ncumeps_global_vsdb_fcst.bash 

This will produce long forecast 00utc files with 24-hourly intervals by averaging all 45 members and convert to grib1 standard for vsdb input.

All above said jobs date will be taken from the environment variable called 'UMRIDER_STARTDATE'

Arulalan.T
