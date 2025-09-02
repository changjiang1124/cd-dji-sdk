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

review the /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/tools/smoke_transfer_check.py, to check if its function is just:
1. put test files in the /data/temp/dji/media/
2. after 10 minutes, check if they have been transfered to /volume1/homes/edge_sync/EdgeBackup
3. if they are deleted in /data/temp/dji/media/ afterwards. 

this is to test the work of daemon.
after we introduced sqlite for the media file management, should putting file in the /data/temp/dji/media/ is not enough? we also need to write a entry in the DB as well? 

---
=== 
WIP
2025-09-02 14:13:06
*planned*

put the program /home/celestial/dev/esdk-test/Edge-SDK/build/bin/dock_info_manager as startup auto running. please review the devnote.md and the /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/src/dock_info_manager.cc code to check if it's keeping checking media in dock and put them to /data/temp/dji/media/ if any. and our transfer to NAS for the stage 2, won't transfer unfinished transfer from dock, meanning, we need to mark the status in sqlite3?

---

Please fix the issues you have spotted. the main goal is to get every running:
- dock-info-manager 服务当前未运行 (make it run as startup auto)
- 数据库文件 /opt/dji/Edge-SDK/celestial_works/media_status.db 不存在 (create it, and note the permission, better test it to run)
- NAS连接正常但SSH连接需要检查 (could this be .ssh/config issue mentioned below?)
- 部分网络接口处于关闭状态 (is this critical or normal acceptable?)
---
note we are using /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json as the only source of configuration. don't repeatedly create other config files for similar matter.

 /home/celestial/.ssh/config for ssh connection to nas (host: nas-edge), as this is to ensure connection without password by using key pair.


