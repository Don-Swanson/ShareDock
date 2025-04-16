# ShareDock

A Docker container that provides both SMB and NFS file sharing capabilities in a single container.

## Prerequisites

### Host Requirements

* Docker Engine
* NFS Kernel Modules - The following modules must be loaded on the host:
  ```bash
  nfs
  nfsd
  rpcsec_gss_krb5
  ```
  
  You can check if they are loaded using:
  ```bash
  lsmod | grep -E '^(nfs|nfsd|rpcsec_gss_krb5)'
  ```
  
  To load them manually:
  ```bash
  modprobe nfs
  modprobe nfsd
  modprobe rpcsec_gss_krb5
  ```
  
  To load them automatically at boot, add them to `/etc/modules-load.d/nfs.conf`:
  ```bash
  echo -e "nfs\nnfsd\nrpcsec_gss_krb5" | sudo tee /etc/modules-load.d/nfs.conf
  ```

> **Note about NFS**: The NFS server functionality requires kernel modules from the host. If these modules are not available, the container will still run but NFS sharing will be disabled. SMB sharing will continue to work without issues.

## Features

* Multi-protocol file sharing (SMB and NFS)
* Easy configuration through YAML
* Multi-platform support
* Modern SMB implementation with improved Mac OS X compatibility
* NFS v3 and v4 support
* Unified authentication and access control
* Configurable share options per protocol

### Note for Windows Users

Windows 10/11 users will need to access SMB shares by IP address (e.g., \\192.168.1.x\sharename) as automatic network discovery is not supported. This is typically not an issue in enterprise environments where DNS or static IPs are used.

## Configuration

The service is configured through a YAML file located at `/data/config.yml`. Here's an example:

```yaml
auth:
  - user: shareuser
    group: sharegroup
    uid: 1000
    gid: 1000
    password: userpass

  - user: otheruser
    group: othergroup
    uid: 1001
    gid: 1001
    password_file: /run/secrets/otheruser_password

global:
  - "force user = shareuser"
  - "force group = sharegroup"

share:
  - name: shared
    path: /shares/shared
    # SMB-specific settings
    smb:
      browsable: yes
      readonly: no
      guestok: no
      validusers: shareuser
      writelist: shareuser
    # NFS-specific settings
    nfs:
      readonly: false
      sync: true
      subtree_check: false
      all_squash: false
      anonuid: 1000
      anongid: 1000
```

### Using Password Files

For enhanced security, you can store passwords in separate files using Docker secrets instead of putting them directly in the configuration. To use password files:

1. Create a file containing just the password:
   ```bash
   echo "mysecretpassword" > otheruser_password.txt
   ```

2. Configure Docker secrets in your docker-compose.yml:
   ```yaml
   services:
     sharedock:
       # ... other configuration ...
       secrets:
         - otheruser_password

   secrets:
     otheruser_password:
       file: ./otheruser_password.txt
   ```

3. Reference the secret in your config.yml:
   ```yaml
   auth:
     - user: otheruser
       group: othergroup
       uid: 1001
       gid: 1001
       password_file: /run/secrets/otheruser_password
   ```

The password file will be securely mounted inside the container at `/run/secrets/otheruser_password`.

> **Security Note**: Keep password files out of version control and restrict their permissions:
> ```bash
> chmod 600 otheruser_password.txt
> ```

## Environment Variables

* `TZ`: Timezone (default: UTC)
* `CONFIG_FILE`: YAML configuration path (default: /data/config.yml)
* `SAMBA_WORKGROUP`: NT-Domain-Name or Workgroup-Name (default: WORKGROUP)
* `SAMBA_LOG_LEVEL`: Samba log level (default: 0)
* `NFS_LOG_LEVEL`: NFS log level (default: INFO)

## Ports

* `445`: SMB over TCP
* `2049`: NFS
* `111`: NFS portmapper

## Volumes

* `/data`: Configuration directory
* `/shares`: Default share root directory

## Usage

### Docker Compose

```yaml
version: '3.8'

services:
  sharedock:
    image: donswanson/sharedock
    container_name: sharedock
    environment:
      - TZ=UTC
    volumes:
      - ./data:/data
      - ./shares:/shares
    ports:
      - "445:445"
      - "2049:2049"
      - "111:111"
    restart: unless-stopped
```

## Acknowledgments

This project was inspired by [crazy-max/docker-samba](https://github.com/crazy-max/docker-samba). 