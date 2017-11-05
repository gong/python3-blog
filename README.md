# python3-blog
python3开发个人博客
## 部署环境安装
* `sudo pip3 install jinja2 `
* `sudo pip3 install aiomysql `
* `sudo pip3 install aiohttp`
* `sudo pip3 install markdown`
* `sudo apt install nginx`
* `sudo apt install mysql-server`
* `sudo apt install mysql-client-core-5.6`
* `sudo apt install mysql-client-5.6`
* `sudo apt install mysql-server-5.7`
## mysql创建数据库
1. 首先进入mysql控制台 `mysql -u root -p`
2. 创建数据库名myblog `create database myblog`
3. `source [sql脚本文件的路径全名]`
## nginx环境配置
* python3-blog-1.0放到/etc/nginx/sites-available/目录下：
```
server {
    listen      80; # 监听80端口
    root       /root/python3-blog-1.0/www;
    access_log /root/python3-blog-1.0/log/access_log;
    error_log  /root/python3-blog-1.0/log/error_log;

    server_name xxx; # 配置域名 没有域名就配置ip

    # 处理静态文件/favicon.ico:
    location /favicon.ico {
        root /root/python3-blog-1.0/www;
    }

    # 处理静态资源:
    location ~ ^\/static\/.*$ {
        root /root/python3-blog-1.0/www;
    }

    # 动态请求转发到9000端口:
    location / {
        proxy_pass       http://127.0.0.1:9000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
* /etc/nginx/sites-enabled/目录下创建软链接
```
sudo ln -s /etc/nginx/sites-available/python3-blog-1.0
```
* 更改Nginx中的/etc/nginx/nginx.conf文件
```
user=www-data
改为
user=root
```
* 重启Nginx配置文件
```
nginx -s reload
```
