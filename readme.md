# k2

## Overview

![k2](https://raw.githubusercontent.com/noyuno/k2/master/k2.png)

## Install

In client,

1. Get [CoreOS ISO](https://coreos.com/os/docs/latest/booting-with-iso.html)
2. Create instance. Note IP address, gateway
3. Boot instance

In server VNC,

4. `ip a`. Note interface name
5. `sudo vi /etc/systemd/network/static.network`

~~~
[Match]
Name=eth0
[Network]
Address=xxx.xxx.xxx.xxx
Gateway=xxx.xxx.xxx.xxx
DNS=8.8.8.8
~~~

6. `sudo systemctl restart systemd-networkd`
7. `curl -sL "https://raw.githubusercontent.com/noyuno/k2/master/cloud-config.yml" >cloud-config.yml`
8. Change IP address by `vi cloud-config.yml`
9. `sudo gdisk /dev/vda`, `p`
10. `sudo coreos-install -d /dev/vda -C stable -c cloud-config.yml`

If forget changing IP address, edit `/var/lib/coreos-install/user_data`

11. `reboot`

In Linux client,

12. `ssh xxx.xxx.xxx.xxx` (If refused connection, type `sudo systemctl start sshd` in VNC)
13. Set up `docker-compose`

~~~sh
git clone https://github.com/noyuno/k2
cd k2
# install docker-compose
./bin/install
cp .env.example .env
vi .env
~~~

14. Run services

~~~sh
dc up -d
~~~

## Operations

- `./bin/install-compose`: install docker-compose
- `./bin/update`: update all
- `./bin/restart`: restart all containers
- `./bin/remote-upgrade`: upgrade remote (`-i` to pull images)

## Attention

- When change sub domain, must remove `nginx` container

## Tools

draw dependency of docker container: `docker run --rm -it --name dcv -v $(pwd):/input pmsipilot/docker-compose-viz render -m image docker-compose.yml --force -o depends.png`

## Backup policy

| instance name       | target       | software           | generation | span   | time  | expires | path                   |
|---------------------|--------------|--------------------|------------|--------|-------|---------|------------------------|
| gitbucket-db-backup | gitbucket-db | postgres-backup-s3 | 38         | 3/week | 02:48 | 2 month | k2b/large/db/gitbucket |
| owncloud-db-backup  | gitbucket-db | postgres-backup-s3 | 38         | 3/week | 03:16 | 2 month | k2b/large/db/owncloud  |
| backupd             | animed       | backupd            | 38         | 3/week | 02:46 | 2 month | k2b/backup/files       |
| largemirrord        | gitbucket,owncloud,minio | rcloned | 1         | 3/week | 03:06 | -       | k2b/large/files        |
| photod              | Google Photos | photod            | 1          | 3/week | 02:51 | -       | k2b/google/photos      |
| rclone-drive-local  | Google Drive | rcloned            | 1          | 3/week | 03:02 | -       | ./tmp/rclone           |
| rclone-drive-s3     | ./tmp/rclone | rcloned            | 1          | 3/week | 09:02 | -       | k2b/google/drive       |

## Restore

### General

In Arch Linux client,

1. Go to [AWS Security Credentials / User](https://console.aws.amazon.com/iam/home?region=us-east-1#/users), "append user" (access type: by program, policy group: AmazonS3FullAccess), and get AWS access key and secret key
2. Set up DNS

    1. Edit `/etc/systemd/resolved.conf`

    ~~~sh
    DNS=8.8.8.8
    ~~~

    2. `sudo systemctl restart systemd-resolved.service`

3. Set up `awscli`

~~~sh

sudo pip3 install awscli
aws configure
# Enter AWS Access Key ID, AWS Secret Access Key, Default region name (ap-northeast-1)
~~~

### k2

1. Set up

2. Restore items from Glacier.

~~~sh
aws s3api restore-object --restore-request Days=5 --bucket k2b --key backup/files/20190711-1746.tar.gz
aws s3api list-objects-v2 --bucket k2b --prefix large/files --query "Contents[?StorageClass=='GLACIER']" --output text | \
    awk -F\\t '{print $2}' | \
    xargs -t -L 1 aws s3api restore-object --restore-request Days=5 --bucket k2b --key
aws s3api restore-object --restore-request Days=5 --bucket k2b --key large/db/gitbucket/gitbucket-20190711-1748.sql.gz
aws s3api restore-object --restore-request Days=5 --bucket k2b --key large/db/owncloud/owncloud-20190711-1748.sql.gz
~~~

3. Wait 5 hours.

In instance(ssh),

4. Download items. If error occured, check state and try again.

~~~sh
mkdir -p s3/{large,db}
# install awscli
toolbox
toolbox > yum install -y awscli

# check state
toolbox aws configure # input AWS Access Key ID, Access Key Secret, Region(ap-northeast-1)
toolbox aws s3api head-object --bucket k2b --key (key)

# download
toolbox aws s3 cp --force-glacier-transfer s3://k2b/backup/files/20190711-1746.tar.gz /media/root/home/noyuno/s3/k2.tar.gz
toolbox aws s3 sync --force-glacier-transfer s3://k2b/large/files /media/root/home/noyuno/s3/backup/large
toolbox aws s3 cp --force-glacier-transfer s3://k2b/large/db/gitbucket/gitbucket-20190711-1748.sql.gz /media/root/home/noyuno/s3/db

# extract
cd s3
tar -xf k2.tar.gz

gunzip -c out/k2/db/gitbucket-20190711-1748.sql.gz > out/k2/db/gitbucket-20190711-1748.sql
~~~

### Google data

1. Set up

~~~sh
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
EMAIL=
mkdir -p out/{drive,photos}
~~~

2. Restore items from Glacier.

~~~sh
aws s3api list-objects-v2 --bucket k2b --prefix google --query "Contents[?StorageClass=='GLACIER']" --output text | \
    awk -F\\t '{print $2}' | \
    xargs -t -L 1 aws s3api restore-object --restore-request Days=5 --bucket k2b --key
~~~

3. Wait 5 hours.

4. Download Google Drive files. If error occured, check state and try again.

~~~sh
# check state
aws s3api head-object --bucket k2b --key (key)

# download
aws s3 sync --force-glacier-transfer s3://k2b/google/drive out/drive
~~~

`--force-glacier-transfer` only tries download and doesn't try restore.

5. Download Google Photos files

    1. Download photod source code

    ~~~
    git clone https://github.com/noyuno/photod /tmp/photod
    ~~~

    2. Run
        
    ~~~sh
    docker run --rm -it \
        -v $(pwd)/out/photos:/data/photod \
        -v /tmp/photod:/opt/photod:ro \
        -v /tmp/photod/logs:/logs/photod \
        -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
        -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
        -e AWS_REGION=ap-northeast-1 \
        -e S3_BUCKET=k2b \
        -e S3_PREFIX=google/photos \
        -e EMAIL=$EMAIL noyuno/photod /opt/photod/download.sh
    ~~~
