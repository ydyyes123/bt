#!/bin/bash
cp /www/server/panel/task.py /www/server/panel/task.py.bk
\cp -fr ./www/server/panel/task.py /www/server/panel/
\cp -fr ./www/server/panel/mail.json /www/server/panel/
/etc/init.d/bt restart
echo "执行结束!"
