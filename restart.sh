
tail -100 wplreport.log  | grep ^2026 | tail -1 | awk '{ system("kill " substr($3,2,length($3)-2));}'
nohup /data/wpl_reports/main.py &
