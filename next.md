I want to test large files sync. how can i get some large files? should i download some youtube files? is there any command tool for that? 

---
how about use SQlite3 in local folder for structurally showing some important activities? dont need to act like log, but critical checkpoints.

---
=== 
DONE

dotenv installed, and SMTP information proivded in .env file. use it to come up a email notififaction module for other modules to use. and suggest me what events should be emailed out.
```
SMTP_SERVER
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_RECIPIENT
```
---
===
review the /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/tools/smoke_transfer_check.py, to check if its function is just:
1. put test files in the /data/temp/dji/media/
2. after 10 minutes, check if they have been transfered to /volume1/homes/edge_sync/EdgeBackup (is the program currently use ~/drone_media/EdgeBackup as the target folder? if yes, that's fine, no need to change it. just let me know )
3. if they are deleted in /data/temp/dji/media/ afterwards. 

this is to test the work of daemon.
since we introduced sqlite for the media file management, should putting file in the /data/temp/dji/media/ is not enough? we also need to write a entry in the DB as well? 

---
=== 
DONE
2025-09-02 14:13:06
*DONE*

put the program /home/celestial/dev/esdk-test/Edge-SDK/build/bin/dock_info_manager as startup auto running. please review the devnote.md and the /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/src/dock_info_manager.cc code to check if it's keeping checking media in dock and put them to /data/temp/dji/media/ if any. and our transfer to NAS for the stage 2, won't transfer unfinished transfer from dock, meanning, we need to mark the status in sqlite3?

---
===
*DONE*

Please fix the issues you have spotted. the main goal is to get every running:
- dock-info-manager 服务当前未运行 (make it run as startup auto)
- 数据库文件 /opt/dji/Edge-SDK/celestial_works/media_status.db 不存在 (create it, and note the permission, better test it to run)
- NAS连接正常但SSH连接需要检查 (could this be .ssh/config issue mentioned below?)
- 部分网络接口处于关闭状态 (is this critical or normal acceptable?)
---
note we are using /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json as the only source of configuration. don't repeatedly create other config files for similar matter.

 /home/celestial/.ssh/config for ssh connection to nas (host: nas-edge), as this is to ensure connection without password by using key pair.


---
===
**DONE**
for the smoke test, should you check daemon processes whether they are existing or not? this could be an obvious test items before actually generate test files and waiting for the transfer to complete.
the db could be locked due to two daemon? is there a risk? how to solve it? do we need to give up sqlite for other solutions?

---
===
generate a shell script for to make dock_info_manager effect and restart daemon when changed. e.g. if i changed the interval in configuration, and need to recompile the cc code, and restart the daemon to make it work. you can add some steps you think is necessary. the name and purpose is to deploy_dock_monitor.sh 

===
want to have a smoke test, to insert mock up records and files in db and media location, then wait for the media_sync daemon to transfer them, delete them and change the record status in the db. might need to pending for some minutes. 


===
---WIP---
1. 你用到了两个方案文件，请合并到同一个文件里，这样可以线性追踪 /home/celestial/dev/esdk-test/Edge-SDK/plans/database_access_architecture_optimization.md ; /home/celestial/dev/esdk-test/Edge-SDK/plans/sync_scheduler_file_monitoring_implementation.md
2. 请明确 edge->nas 的时候，要记录过程在 DB，并先读取 DB 来判断是否传输过。具体如下:
    a. 发现文件后，去DB 看下这个文件是否存在（通过文件名加 hash，这样准确点，但是 hash 30G 的文件会不会比较慢？）如果文件存在，则不管；如果文件不存在，则加入新的记录，并标记为 pending（待处理）
    b. 浏览 DB，查看 pending 的文件，然后去开始传输，并在开始后，状态标记 pending -> transfering;
    c. 传输完毕后，状态标记 transfering -> transferred;

    这样的传输是不是线性的而不是异步的？做成异步的好处当然是比较及时能发现更新 DB，但是坏处就是又会出现多个进程读写数据库的并发问题，可能造成锁；而且即便开始传输，也会抢带宽，实际效果并不好。你怎么建议？

--

since we are using the new media_finding_daemon.py, what should we do with the original media_finding_daemon.py? should we keep it as it is, or just delete it? as well as 
**服务位置**: `/etc/systemd/system/media-sync-daemon.service`  
**主程序**: `celestial_nasops/sync_scheduler.py`  
**核心模块**: `celestial_nasops/media_sync.py`

---
- [x] help me update how-it-works.md regarding the updates.

---
rsync.service 在 daemon 里是已经被 media_finding_daemon.service 的能力替换掉了吗？如果是，那么 rsync.service 就可以被删除了。所以 media_finding_daemon.service 是可以同步文件传输的对吧。