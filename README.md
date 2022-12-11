UnderNET Development Environment
================================

This repository contain a docker based development environment for UnderNET.

It includes the following services:

- hub (ircu2)
- leaf server (ircu2)
- PostgreSQL database
- mail server (mailhog)
- cservice web portal
- GNUworld


# Requirements to setup the environment

- docker
- docker-compose


# FAQ
Q: Why do I see this message _"X (cservice@undernet.org): AUTHENTICATION FAILED as <user> 
   (Unable to login during reconnection, please try again in 295 seconds)"_ when trying to 
   authenticate with `x@channels.undernet.org`?

A: This is a burst connection mechanism in GNUworld which happen when it links to its hub. 
   Just wait for it to complete and try again.