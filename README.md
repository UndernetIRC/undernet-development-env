UnderNET Development Environment
================================
> **Warning**
> 
> Do _**NOT**_ use this in production, it is not safe and contains publicly shared credentials! 

This repository contain a docker based development environment for UnderNET.

It includes the following services:

- hub (ircu2)
- leaf server (ircu2)
- PostgreSQL database
- Redis (Valkey) for caching and session management
- mail server (Mailpit)
- cservice web portal
- cservice API (REST API for cservice)
- GNUworld (enabled modules: cservice, ccontrol, openchanfix, dronescan)


# Requirements to setup the environment

- [Docker](https://www.docker.com/)
- [docker-compose](https://docs.docker.com/compose/)


# Getting started

This project uses git submodules. After cloning this repository the submodules needs to be
initialized and updated. Follow this step-by-step guide to get your new UnderNET environment
up and running.

## Git Submodules

This repository includes the following submodules:

- `cservice-api/` - Go-based REST API server
- `cservice-web/` - PHP web interface
- `gnuworld/` - C++ service bot framework
- `ircu2/` - IRC server implementation

## Setup Steps

```
git clone https://github.com/Ratler/undernet-development-env.git
cd undernet-development-env
git submodule init
git submodule update
docker-compose up -d
```

## Service information (hosts, ports and login information)

The following ports below are mapped from your host to the container:

| Service      | URL / ip:port                                        | Comments                                                                                                                                                                    |
|--------------|------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| hub          | Server: localhost:4400 <br> Client: localhost:6669   | The default `/oper` username is `admin` with the password `admin`                                                                                                           |
| leaf         | Server: localhost:4401 <br> Client: localhost:6667   | The default `/oper` username is `admin` with the password `admin`                                                                                                           |
| db           | localhost:5432                                       | The default db username is `cservice` with the password `cservice`, works for all the databases. <br> Databases: `cservice`, `ccontrol`, `chanfix`, `dronescan`, `local_db` |
| redis        | localhost:6379                                       | Valkey - used for caching and session management. No authentication required.                                                                                               |
| mail         | SMTP: localhost:1025 <br> WEB: http://localhost:8025 | Mailpit - captures e-mails from cservice-web and cservice-api, <br>e-mails can be accessed from the WEB url.                                                                |
| cservice-web | http://localhost:8080                                | Default admin (level 1000) user is `Admin` with the password `temPass2020@`                                                                                                 |
| cservice-api | http://localhost:8081                                | REST API for cservice (JWT-based authentication). Health check available at `/health-check`                                                                                 |


# Configuration

The configuration for the `hub`, `leaf` and `gnuworld` can be changed in the folder `etc/`.
All the files are mounted inside the container as volumes, so any change done on your host
is reflected in the container immediately. For example after changing `etc/hub.conf`, just 
`/rehash` the IRC server to apply the changes.

For the service `cservice-web` the configuration can be changed from `cservice-web/php_includes`. Any configuration
or code change will be applied immediately.

# Making code changes in ircu, gnuworld or cservice-api

After making any code change in ircu, gnuworld or cservice-api the container needs to be rebuilt and restarted.

Rebuild ircu (hub and leaf share the same image):
```
docker-compose up --build hub
docker-compose up leaf
```

Rebuild and restart gnuworld:
```
docker-compose up --build gnuworld
```

Rebuild and restart cservice-api:
```
docker-compose up --build api
```

For cservice-web, changes to configuration files in `cservice-web/php_includes` are reflected immediately without requiring a rebuild.

# PostgreSQL databases

## Data persistence

All databases are persisted by using a docker volume. To list existing volumes  run `docker volume ls`. 
To reset all databases you can delete the volume by running `docker volume rm undernet-development-env_pgdata`,
and then restart the `db` service to recreate all databases.


# FAQ
Q: Why do I see this message _"X (cservice@undernet.org): AUTHENTICATION FAILED as <user> 
   (Unable to login during reconnection, please try again in 295 seconds)"_ when trying to 
   authenticate with `x@channels.undernet.org`?

A: This is a burst connection mechanism in GNUworld which happen when it links to its hub. 
   Just wait for it to complete and try again. Or you can change the setting `login_delay` in
   `etc/gnuworld/cservice.conf`, it's currently set to 5 seconds.

Q: Why am I getting _"X (cservice@undernet.org): AUTHENTICATION FAILED as Admin (IPR)"_ when I try to
   authenticate with the `x@channels.undernet.org` with the `Admin` user?

A: Access IP restrictions are applied to the Admin user, to fix this, login to the `cservice-web`, and
   change `Access IP restrictions (ACL+)` by adding the ip address `10.5.0.1`.