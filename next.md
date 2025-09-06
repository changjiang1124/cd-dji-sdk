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
**!IMPORTANT**
want to have a smoke test, to insert mock up records and files in the /data/temp/dji/media/ location, then wait for the media_finding_daemon to transfer them, delete them and change the record status in the db. might need to pending for some minutes. 
show me a comprehensive report, including when new files created, when found by daemon, when pending, transfered, completed. and if NAS has such files, show me the time.


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
- [x] rsync.service 在 daemon 里是已经被 media_finding_daemon.service 的能力替换掉了吗？如果是，那么 rsync.service 就可以被删除了。所以 media_finding_daemon.service 是可以同步文件传输的对吧。


===
**DONE**
标记为下载中的大文件，如果终端下载该怎么处理？
现在的系统是如何检查NaS上是否有足够的空间呢？以及 edge 上是否有足够的空间？是不是需要单独开启一个低门来执行监测？

===
潜在风险与改进建议

1. 配置硬编码 :
   
   - 问题 : 在 chunk_transfer_manager.cc 中， worker_thread_count_ (工作线程数) 和 timeout_seconds_ (超时时间) 目前是硬编码的。
   - 风险 : 如果需要调整这些参数，必须重新编译代码，这在生产环境中非常不灵活。
   - 建议 : 将这些参数移至 unified_config.json 中，并由 ConfigManager 加载，就像 chunk_size_mb 和 max_concurrent_transfers 一样。

2. 数据库并发性能 :
   
   - 问题 : TransferStatusDB 在所有数据库操作上都使用了一个全局互斥锁 ( db_mutex_ )。
   - 风险 : 在高并发下载场景下（例如，同时处理多个媒体文件），这个单一的锁可能会成为性能瓶颈，因为所有线程都需要排队等待数据库访问。
   - 建议 :
     - 启用 WAL 模式 : 对于 SQLite，启用 Write-Ahead Logging (WAL) 模式 ( PRAGMA journal_mode=WAL; ) 可以显著提高读写并发性能。
     - 更细粒度的锁 : 如果性能问题依然存在，可以考虑将锁的粒度细化，例如，为不同的表或不同的任务使用不同的锁。

3. 资源清理 :
   
   - 现状 : Shutdown 方法和析构函数确保了线程和基本资源的释放。 sqlite3_prepare_v2 和 sqlite3_finalize 的使用也基本正确。
   - 建议 : 再次确认所有可能的代码路径（包括异常路径）都能正确释放 sqlite3_stmt 资源。虽然目前看起来不错，但这在 C/C++ 中是常见的错误来源。


===
磁盘空间管理的措施

===
TransferStatusDB::UpdateChunkStatus
- 批量更新（Batching） : 一个有效的优化策略是 批量更新 。我们可以不在内存中每完成一个分块就立即写入数据库，而是缓存一小组（例如5-10个）已完成的分块状态，然后通过一次数据库事务（Transaction）将它们批量写入。这能显著减少I/O次数和事务开销。

===
邮件通知传输开始，过程，以及结束，以及中间出现的问题。包括 dock->edge, edge->NAS. 以及邮件通知磁盘情况，包括每日更新，以及事件触发。