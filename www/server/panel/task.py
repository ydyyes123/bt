#coding: utf-8
# +-------------------------------------------------------------------
# | 宝塔Linux面板
# +-------------------------------------------------------------------
# | Copyright (c) 2015-2016 宝塔软件(http://bt.cn) All rights reserved.
# +-------------------------------------------------------------------
# | Author: 黄文良 <2879625666@qq.com>
# +-------------------------------------------------------------------

#------------------------------
# 计划任务
#------------------------------
import sys,os,json
sys.path.append("class/")
reload(sys)
sys.setdefaultencoding('utf-8')
import db,public,time
global pre,timeoutCount,logPath,isTask,oldEdate,isCheck
pre = 0
timeoutCount = 0
isCheck = 0
oldEdate = None
logPath = '/tmp/panelExec.log'
isTask = '/tmp/panelTask.pl'

class MyBad():
    _msg = None
    def __init__(self,msg):
        self._msg = msg
    def __repr__(self):
        return self._msg
        

def ExecShell(cmdstring, cwd=None, timeout=None, shell=True):
    try:
        global logPath
        import shlex
        import datetime
        import subprocess
        import time
    
        if timeout:
            end_time = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
        
        sub = subprocess.Popen(cmdstring+' > '+logPath+' 2>&1', cwd=cwd, stdin=subprocess.PIPE,shell=shell,bufsize=4096)
        
        while sub.poll() is None:
            time.sleep(0.1)
                
        return sub.returncode
    except:
        return None

#下载文件
def DownloadFile(url,filename):
    try:
        import urllib,socket
        socket.setdefaulttimeout(10)
        urllib.urlretrieve(url,filename=filename ,reporthook= DownloadHook)
        os.system('chown www.www ' + filename);
        WriteLogs('done')
    except:
        WriteLogs('done')
        


#下载文件进度回调  
def DownloadHook(count, blockSize, totalSize):
    global pre
    used = count * blockSize
    pre1 = int((100.0 * used / totalSize))
    if pre == pre1:
        return
    speed = {'total':totalSize,'used':used,'pre':pre}
    WriteLogs(json.dumps(speed))
    pre = pre1

#写输出日志
def WriteLogs(logMsg):
    try:
        global logPath
        fp = open(logPath,'w+');
        fp.write(logMsg)
        fp.close()
    except:
        pass;

#任务队列 
def startTask():
    global isTask
    import time,public
    try:
        while True:
            try:
                if os.path.exists(isTask):
                    sql = db.Sql()
                    sql.table('tasks').where("status=?",('-1',)).setField('status','0')
                    taskArr = sql.table('tasks').where("status=?",('0',)).field('id,type,execstr').order("id asc").select();
                    for value in taskArr:
                        start = int(time.time());
                        if not sql.table('tasks').where("id=?",(value['id'],)).count(): continue;
                        sql.table('tasks').where("id=?",(value['id'],)).save('status,start',('-1',start))
                        if value['type'] == 'download':
                            argv = value['execstr'].split('|bt|')
                            DownloadFile(argv[0],argv[1])
                        elif value['type'] == 'execshell':
                            ExecShell(value['execstr'])
                        end = int(time.time())
                        sql.table('tasks').where("id=?",(value['id'],)).save('status,end',('1',end))
                        if(sql.table('tasks').where("status=?",('0')).count() < 1): os.system('rm -f ' + isTask);
            except:
                pass
            siteEdate();
            mainSafe();
            time.sleep(2)
    except:
        time.sleep(60);
        startTask();
        
def mainSafe():
    global isCheck
    try:
        if isCheck < 100:
            isCheck += 1;
            return True;
        isCheck = 0;
        isStart = public.ExecShell("ps aux |grep 'python main.py'|grep -v grep|awk '{print $2}'")[0];
        if not isStart: 
            os.system('/etc/init.d/bt start');
            isStart = public.ExecShell("ps aux |grep 'python main.py'|grep -v grep|awk '{print $2}'")[0];
            public.WriteLog('守护程序','面板服务程序启动成功 -> PID: ' + isStart);
    except:
        time.sleep(30);
        mainSafe();

#网站到期处理
def siteEdate():
    global oldEdate
    try:
        if not oldEdate: oldEdate = public.readFile('data/edate.pl');
        if not oldEdate: oldEdate = '0000-00-00';
        mEdate = time.strftime('%Y-%m-%d',time.localtime())
        if oldEdate == mEdate: return False;
        edateSites = public.M('sites').where('edate>? AND edate<? AND (status=? OR status=?)',('0000-00-00',mEdate,1,u'正在运行')).field('id,name').select();
        import panelSite;
        siteObject = panelSite.panelSite();
        for site in edateSites:
            get = MyBad('');
            get.id = site['id'];
            get.name = site['name'];
            siteObject.SiteStop(get);
        oldEdate = mEdate;
        public.writeFile('data/edate.pl',mEdate);
    except:
         pass;
    
         

#系统监控任务
def systemTask():
    try:
        import system,psutil,time
        sm = system.system();
        filename = 'data/control.conf';
        sql = db.Sql().dbfile('system')
        csql = '''CREATE TABLE IF NOT EXISTS `load_average` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `pro` REAL,
  `one` REAL,
  `five` REAL,
  `fifteen` REAL,
  `addtime` INTEGER
)'''
        sql.execute(csql,())
        cpuIo = cpu = {}
        cpuCount = psutil.cpu_count()
        used = count = 0
        reloadNum=0
        network_up = network_down = diskio_1 = diskio_2 = networkInfo = cpuInfo = diskInfo = None
        while True:
            if not os.path.exists(filename):
                time.sleep(10);
                continue;
            
            day = 30;
            try:
                day = int(public.readFile(filename));
                if day < 1:
                    time.sleep(10)
                    continue;
            except:
                day  = 30
            
            
            tmp = {}
            #取当前CPU Io     
            tmp['used'] = psutil.cpu_percent(interval=1)
            
            if not cpuInfo:
                tmp['mem'] = GetMemUsed()
                cpuInfo = tmp 
            
            if cpuInfo['used'] < tmp['used']:
                tmp['mem'] = GetMemUsed()
                cpuInfo = tmp 
            
            
            
            #取当前网络Io
            networkIo = psutil.net_io_counters()[:4]
            if not network_up:
                network_up   =  networkIo[0]
                network_down =  networkIo[1]
            tmp = {}
            tmp['upTotal']      = networkIo[0]
            tmp['downTotal']    = networkIo[1]
            tmp['up']           = round(float((networkIo[0] - network_up) / 1024),2)
            tmp['down']         = round(float((networkIo[1] - network_down) / 1024),2)
            tmp['downPackets']  = networkIo[3]
            tmp['upPackets']    = networkIo[2]
            
            network_up   =  networkIo[0]
            network_down =  networkIo[1]
            
            if not networkInfo: networkInfo = tmp
            if (tmp['up'] + tmp['down']) > (networkInfo['up'] + networkInfo['down']): networkInfo = tmp
            
            #取磁盘Io
            if os.path.exists('/proc/diskstats'):
                diskio_2 = psutil.disk_io_counters()
                if not diskio_1: diskio_1 = diskio_2
                tmp = {}
                tmp['read_count']   = diskio_2.read_count - diskio_1.read_count
                tmp['write_count']  = diskio_2.write_count - diskio_1.write_count
                tmp['read_bytes']   = diskio_2.read_bytes - diskio_1.read_bytes
                tmp['write_bytes']  = diskio_2.write_bytes - diskio_1.write_bytes
                tmp['read_time']    = diskio_2.read_time - diskio_1.read_time
                tmp['write_time']   = diskio_2.write_time - diskio_1.write_time
                
                if not diskInfo: 
                    diskInfo = tmp
                else:
                    diskInfo['read_count']   += tmp['read_count']
                    diskInfo['write_count']  += tmp['write_count']
                    diskInfo['read_bytes']   += tmp['read_bytes']
                    diskInfo['write_bytes']  += tmp['write_bytes']
                    diskInfo['read_time']    += tmp['read_time']
                    diskInfo['write_time']   += tmp['write_time']
                
                diskio_1 = diskio_2
            
            #print diskInfo

            cheskMonitorAlarm(sm.GetLoadAverage(None), cpuInfo['used'], cpuInfo['mem'], networkInfo, diskInfo)
            
            if count >= 12:
                try:
                    addtime = int(time.time())
                    deltime = addtime - (day * 86400)
                    
                    data = (cpuInfo['used'],cpuInfo['mem'],addtime)
                    sql.table('cpuio').add('pro,mem,addtime',data)
                    sql.table('cpuio').where("addtime<?",(deltime,)).delete();
                    
                    data = (networkInfo['up'] / 5,networkInfo['down'] / 5,networkInfo['upTotal'],networkInfo['downTotal'],networkInfo['downPackets'],networkInfo['upPackets'],addtime)
                    sql.table('network').add('up,down,total_up,total_down,down_packets,up_packets,addtime',data)
                    sql.table('network').where("addtime<?",(deltime,)).delete();
                    if os.path.exists('/proc/diskstats'):
                        data = (diskInfo['read_count'],diskInfo['write_count'],diskInfo['read_bytes'],diskInfo['write_bytes'],diskInfo['read_time'],diskInfo['write_time'],addtime)
                        sql.table('diskio').add('read_count,write_count,read_bytes,write_bytes,read_time,write_time,addtime',data)
                        sql.table('diskio').where("addtime<?",(deltime,)).delete();
                    
                    #LoadAverage
                    load_average = sm.GetLoadAverage(None)
                    lpro = round((load_average['one'] / load_average['max']) * 100,2)
                    if lpro > 100: lpro = 100;
                    sql.table('load_average').add('pro,one,five,fifteen,addtime',(lpro,load_average['one'],load_average['five'],load_average['fifteen'],addtime))

                    lpro = None
                    load_average = None
                    cpuInfo = None
                    networkInfo = None
                    diskInfo = None
                    count = 0
                    reloadNum += 1;
                    if reloadNum > 1440:
                        if os.path.exists('data/ssl.pl'): os.system('/etc/init.d/bt restart > /dev/null 2>&1');
                        reloadNum = 0;
                except Exception,ex:
                    print str(ex)
            del(tmp)
            
            time.sleep(5);
            count +=1
    except Exception,ex:
        print str(ex)
        time.sleep(30);
        systemTask();

last_alarm_time=0
last_alarm_msg=None

def cheskMonitorAlarm(load_average, cpu_use_ratio, memory_use_ratio, network, disk):
    '''
    :param load_average: 负载情况
    :param cpu_use_ratio: 当前CPU使用百分比
    :param memory_use_ratio: 当前内存使用百分比
    :param network: 网络情况
    :param disk: 磁盘IO情况
    '''
    import socket
    global last_alarm_time
    global last_alarm_msg

    # 警报逻辑

    device_id = socket.gethostname()
    now_msg=buildMonitorAlarm(load_average, cpu_use_ratio, memory_use_ratio, network, disk)
    if not now_msg == last_alarm_msg:
        if now_msg is None:
            # 取消警报
            if last_alarm_time < time.time() - 5:
                # 5秒，正常后恢复
                last_alarm_time=0
                last_alarm_msg=None
                sendMonitorAlarm(u"设备 " + device_id + u", 已经恢复正常.", "无事发生")
        else:
            # 警报变动，必须间隔1小时
            if last_alarm_time < time.time() - 36000:
                last_alarm_time=time.time()
                last_alarm_msg=now_msg
                sendMonitorAlarm(u"设备 " + device_id + u", 发生警报!", now_msg)

def getDiskUsed():
    import re

    disk_str = public.ExecShell("df -l --output=fstype,source,pcent,target")[0]
    pass_type = ['ext', 'ext2', 'ext3', 'ext4', 'vfat', 'ntfs']
    disk_list=list()

    if disk_str is not None:
        disk_str=disk_str.split('\n')[1:-1]
        for disk_info in disk_str:
            m = re.match(u'^([^ ]+?) *([^ ]+?) *([^ ]+?)% *([^ ]+?)$', disk_info)
            if m is None:
                continue
            else:
                disk_info=dict()
                disk_info['type'] = m.group(1)  # 磁盘分区类型
                disk_info['mount_source'] = m.group(2)  # 磁盘分区设备路径
                disk_info['used_ratio'] = m.group(3)    # 已使用百分比
                disk_info['mount_path'] = m.group(4)    # 磁盘分区挂载路径

                if disk_info['type'] not in pass_type:
                    continue
                disk_list.append(disk_info)

    return disk_list

def buildMonitorAlarm(load_average, cpu_use_ratio, memory_use_ratio, network, disk):
    '''
    # load_average['one']
    # load_average['five']
    # load_average['fifteen']
    # load_average['max']   CPU 个数
    # load_average['limit'] 最大负载数字
    # load_average['safe'] 默认安全负载值

    # network['upTotal']    总计发送字节
    # network['downTotal']  总计接受字节
    # network['up']     当前发送字节
    # network['down']   当前接受字节
    # network['downPackets']    当前发送包数量
    # network['upPackets']      当前接受包数量

    # disk['read_count']    总计读取字节
    # disk['write_count']   总计写入字节
    # disk['read_bytes']    当前读取字节
    # disk['write_bytes']   当前写入字节
    # disk['read_time']     当前读取占用时间
    # disk['write_time']    当前写入占用时间

    :param load_average: 负载情况
    :param cpu_use_ratio: 当前CPU使用百分比
    :param memory_use_ratio: 当前内存使用百分比
    :param network: 网络情况
    :param disk: 磁盘IO情况
    :return 警报消息
    '''

    # CPU 负载过高
    alarm_msg = ''
    if load_average['one'] > load_average['max'] * 3:
        alarm_msg += 'CPU 1分钟内负载过高，已经达到:' + str(load_average['one']) + '\n'
    # 内存使用过高
    if memory_use_ratio > 80:
        alarm_msg += '内存过高，已经达到:' + str(int(memory_use_ratio)) + '%\n'
    # 磁盘读取
    if disk['read_bytes'] > 30 * 1024 * 1024:
        alarm_msg += '磁盘读取卡顿，已经达到:' + str(int(disk['read_bytes'] / 1024)) + 'kb/s\n'
    # 磁盘写入
    if disk['write_bytes'] > 10 * 1024 * 1024:
        alarm_msg += '磁盘写入卡顿，已经达到:' + str(int(disk['write_bytes'] / 1024)) + 'kb/s\n'
    # 网络接受 大于20MB
    if network['down'] / 5 / (1024 * 60) > 20 * 1024:
        alarm_msg += '网络接受，已经达到:' + str(int(network['down'] / (1024 * 60))) + 'kb/s\n'
    # 网络发送 大于10MB
    if network['up'] / 5 / (1024 * 60) > 10 * 1024:
        alarm_msg += '网络发送，已经达到:' + str(int(network['up'] / (1024 * 60))) + 'kb/s\n'

    disk_list = getDiskUsed()

    for disk_info in disk_list:
        if int(disk_info['used_ratio']) > 80:
            alarm_msg += '磁盘: ' + disk_info['mount_source'] + ',挂载在: ' + disk_info['mount_path'] + '已使用: ' + disk_info['used_ratio'] + '%\n'

    if alarm_msg == '':
        return None
    else:
        return alarm_msg

def read_dict(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.loads(f.read())
    except BaseException:
        return None


def save_dict(path, value):
    with open(path, 'w') as f:
        f.write(json.dumps(value))

def sendMonitorAlarm(title, msg):
    '''
    发送监控警报
    :param title: 警报级别
    :param msg: 警报内容
    :return:
    '''
    print 'send alarm ', msg
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header

    # 第三方 SMTP 服务
    mail_host="smtp.mail.ru"  #设置服务器
    mail_user="i7ztwnt5vv"    #用户名
    mail_pass="Glbsd2vngwz"   #口令


    sender = 'i7ztwnt5vv@mail.ru'
    receiver_dict = read_dict('mail.json')
    if receiver_dict is None:
        receiver_dict=dict()
        receiver_dict['list']=['ydyyes9@gmail.com', 'ydyyes@163.com']
        save_dict('mail.json', receiver_dict)
    receivers = receiver_dict['list']
    #receivers = ['ydyyes9@gmail.com', 'ydyyes@163.com']  # 接收邮件，可设置为你的QQ邮箱或者其他邮箱

    message = MIMEText(msg, 'plain', 'utf-8')
    #message['From'] = Header(u"宝塔-自动化监控模块", 'utf-8')
    #message['To'] = Header(u"管理员", 'utf-8')

    subject = title
    message['Subject'] = Header(subject, 'utf-8')


    try:
        smtpObj = smtplib.SMTP()
        smtpObj.connect(mail_host, 587)
        smtpObj.starttls()
        smtpObj.login(mail_user,mail_pass)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print "Mail sent successfully."
    except smtplib.SMTPException:
        print "Error: Unable to send mail!"

#取内存使用率
def GetMemUsed():
    try:
        import psutil
        mem = psutil.virtual_memory()
        memInfo = {'memTotal':mem.total/1024/1024,'memFree':mem.free/1024/1024,'memBuffers':mem.buffers/1024/1024,'memCached':mem.cached/1024/1024}
        tmp = memInfo['memTotal'] - memInfo['memFree'] - memInfo['memBuffers'] - memInfo['memCached']
        tmp1 = memInfo['memTotal'] / 100
        return (tmp / tmp1)
    except:
        return 1;

#检查502错误 
def check502():
    try:
        phpversions = ['53','54','55','56','70','71','72']
        for version in phpversions:
            if not os.path.exists('/etc/init.d/php-fpm-'+version): continue;
            if checkPHPVersion(version): continue;
            if startPHPVersion(version):
                public.WriteLog('PHP守护程序','检测到PHP-' + version + '处理异常,已自动修复!')
    except:
        pass;
            
#处理指定PHP版本   
def startPHPVersion(version):
    try:
        fpm = '/etc/init.d/php-fpm-'+version
        if not os.path.exists(fpm): return False;
        
        #尝试重载服务
        os.system(fpm + ' reload');
        if checkPHPVersion(version): return True;
        
        #尝试重启服务
        cgi = '/tmp/php-cgi-'+version
        pid = '/www/server/php'+version+'/php-fpm.pid';
        os.system('pkill -9 php-fpm-'+version)
        time.sleep(0.5);
        if not os.path.exists(cgi): os.system('rm -f ' + cgi);
        if not os.path.exists(pid): os.system('rm -f ' + pid);
        os.system(fpm + ' start');
        if checkPHPVersion(version): return True;
        
        #检查是否正确启动
        if os.path.exists(cgi): return True;
    except:
        return True;
    
    
#检查指定PHP版本
def checkPHPVersion(version):
    try:
        url = 'http://127.0.0.1/phpfpm_'+version+'_status';
        result = public.httpGet(url);
        #检查nginx
        if result.find('Bad Gateway') != -1: return False;
        #检查Apache
        if result.find('Service Unavailable') != -1: return False;
        if result.find('Not Found') != -1: CheckPHPINFO();
        
        #检查Web服务是否启动
        if result.find('Connection refused') != -1: 
            global isTask
            if os.path.exists(isTask): 
                isStatus = public.readFile(isTask);
                if isStatus == 'True': return True;
            filename = '/etc/init.d/nginx';
            if os.path.exists(filename): os.system(filename + ' start');
            filename = '/etc/init.d/httpd';
            if os.path.exists(filename): os.system(filename + ' start');
            
        return True;
    except:
        return True;


#检测PHPINFO配置
def CheckPHPINFO():
    php_versions = ['53','54','55','56','70','71','72'];
    setupPath = '/www/server';
    path = setupPath +'/panel/vhost/nginx/phpinfo.conf';
    if not os.path.exists(path):
        opt = "";
        for version in php_versions:
            opt += "\n\tlocation /"+version+" {\n\t\tinclude enable-php-"+version+".conf;\n\t}";
        
        phpinfoBody = '''server
{
    listen 80;
    server_name 127.0.0.2;
    allow 127.0.0.1;
    index phpinfo.php index.html index.php;
    root  /www/server/phpinfo;
%s   
}''' % (opt,);
        public.writeFile(path,phpinfoBody);
    
    
    path = setupPath + '/panel/vhost/apache/phpinfo.conf';
    if not os.path.exists(path):
        opt = "";
        for version in php_versions:
            opt += """\n<Location /%s>
    SetHandler "proxy:unix:/tmp/php-cgi-%s.sock|fcgi://localhost"
</Location>""" % (version,version);
            
        phpinfoBody = '''
<VirtualHost *:80>
DocumentRoot "/www/server/phpinfo"
ServerAdmin phpinfo
ServerName 127.0.0.2
%s
<Directory "/www/server/phpinfo">
    SetOutputFilter DEFLATE
    Options FollowSymLinks
    AllowOverride All
    Order allow,deny
    Allow from all
    DirectoryIndex index.php index.html index.htm default.php default.html default.htm
</Directory>
</VirtualHost>
''' % (opt,);
        public.writeFile(path,phpinfoBody);

#502错误检查线程
def check502Task():
    try:
        while True:
            if os.path.exists('/www/server/panel/data/502Task.pl'): check502();
            time.sleep(600);
    except:
        time.sleep(600);
        check502Task();

#自动结束异常进程
def btkill():
    import btkill
    b = btkill.btkill()
    b.start();

if __name__ == "__main__":
    os.system('rm -rf /www/server/phpinfo/*');
    if os.path.exists('/www/server/nginx/sbin/nginx'):
        pfile = '/www/server/nginx/conf/enable-php-72.conf';
        if not os.path.exists(pfile):
            pconf = '''location ~ [^/]\.php(/|$)
{
    try_files $uri =404;
    fastcgi_pass  unix:/tmp/php-cgi-72.sock;
    fastcgi_index index.php;
    include fastcgi.conf;
    include pathinfo.conf;
}'''
            public.writeFile(pfile,pconf);
    import threading
    t = threading.Thread(target=systemTask)
    t.setDaemon(True)
    t.start()
    
    p = threading.Thread(target=check502Task)
    p.setDaemon(True)
    p.start()
    
    #p = threading.Thread(target=btkill)
    #p.setDaemon(True)
    #p.start()
    
    startTask()


