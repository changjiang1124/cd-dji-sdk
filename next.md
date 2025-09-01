inspect the system's partition design, find a partition with enough space to store the media files, for the right path in production environment.
after confirmed it, update the path in dock_info_manager.cc, so in the future, once there is any files, the media will show in that path. 
for communication between applications/programs, you should keep a file as the configuraiton shared between them, for fetch and put.
and come up with a script, to periodically rsync the media files from edge server to NAS. edge_sync@192.168.200.103:EdgeBackup/ and check if all files are correct (checksum?), if yes, delete them from edge server to free the space. 
and the script should run periodically, say, every 10 minutes.

have a test programe to test the sync between edge server and NAS. (e.g. write some random files)

transfered data in NAS should have organised structure, e.g. year month and date? 
for example, the media file name is 20230815_100000.mp4, then it should be stored in /EdgeBackup/2023/08/15/20230815_100000.mp4