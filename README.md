# ptah

This is a python API to build image for openwrt.  
It is used by Association Rezel to build image for its ISP routers.

# How to use it ?

PTAH relies on a "ptah_config" file. This is where you define the openwrt profiles, files and other things to be added to the router image.
You can feed this config file to the container (inside k8S or on a plain docker).
Then 

## global_settings
