

只处理脚本所在目录（不递归子目录）下的 .txt / .md / .json 文件；
把 "timestamp": 13位数字 全部替换成 "time": "YYYY-MM-DD HH:MM:SS"；
生成新文件，命名规则：原文件名 + _edited + 原后缀；
原文件不动。



使用方法
把脚本放到需要处理的文件夹里；
终端下运行

python .py
或双击（系统已关联 .py）。
同目录下即刻出现 xxx_edited.txt / .md / .json，原文件保留。