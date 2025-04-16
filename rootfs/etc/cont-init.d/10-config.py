#!/usr/bin/env python3

import os
import sys
import yaml
import subprocess
from pathlib import Path

def run_cmd(cmd, check=True, input=None):
    """Run a command and return its output"""
    try:
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=check, capture_output=True, text=True, input=input)
        if result.stdout:
            print(f"Command output: {result.stdout.strip()}")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {cmd}: {e.stderr}", file=sys.stderr)
        if check:
            sys.exit(1)
        return None

def setup_user(user_config):
    """Create user and group based on config"""
    try:
        username = user_config['user']
        groupname = user_config['group']
        uid = user_config.get('uid', None)
        gid = user_config.get('gid', None)
        
        print(f"Setting up user {username} in group {groupname}")
        
        # Create group
        group_cmd = ['addgroup']
        if gid:
            group_cmd.extend(['-g', str(gid)])
        group_cmd.append(groupname)
        run_cmd(group_cmd, check=False)  # Group might already exist
        
        # Create user
        user_cmd = ['adduser', '-D', '-H']
        if uid:
            user_cmd.extend(['-u', str(uid)])
        user_cmd.extend(['-G', groupname, username])
        run_cmd(user_cmd, check=False)  # User might already exist
        
        # Get password
        password = None
        if 'password' in user_config:
            password = user_config['password']
            print(f"Using password from config for user {username}")
            run_cmd(['chpasswd'], input=f"{username}:{password}")
        elif 'password_file' in user_config:
            password_file = user_config['password_file']
            if os.path.exists(password_file):
                try:
                    with open(password_file, 'r') as f:
                        password = f.read().strip()
                        print(f"Using password from file for user {username}")
                        run_cmd(['chpasswd'], input=f"{username}:{password}")
                except Exception as e:
                    print(f"Warning: Could not read password file {password_file}: {e}", file=sys.stderr)
                    print(f"User {username} created but password not set", file=sys.stderr)
            else:
                print(f"Warning: Password file {password_file} not found", file=sys.stderr)
                print(f"User {username} created but password not set", file=sys.stderr)
        
        # Explicitly add Samba user with the same password
        if password:
            print(f"Adding Samba user {username}")
            samba_cmd = ['smbpasswd', '-a', '-s', username]
            run_cmd(samba_cmd, input=f"{password}\n{password}")
            
            # Enable the Samba user
            run_cmd(['smbpasswd', '-e', username])
            
            print(f"Samba user {username} created and enabled")
        else:
            print(f"Warning: No password provided for {username}, Samba access will not work", file=sys.stderr)
            
    except Exception as e:
        print(f"Error setting up user: {e}", file=sys.stderr)

def generate_smb_conf(config):
    """Generate Samba configuration"""
    try:
        smb_conf = Path('/etc/samba/smb.conf')
        
        with smb_conf.open('w') as f:
            f.write('[global]\n')
            f.write(f'workgroup = {os.environ.get("SAMBA_WORKGROUP", "WORKGROUP")}\n')
            f.write('server string = ShareDock Server\n')
            f.write('security = user\n')
            f.write('passdb backend = tdbsam\n')  # Ensure we're using the standard password backend
            f.write('log level = {}\n'.format(os.environ.get('SAMBA_LOG_LEVEL', '0')))
            f.write('map to guest = Bad User\n')  # Default to rejecting guest access
            
            # Write global settings
            if 'global' in config:
                for setting in config['global']:
                    f.write(f'{setting}\n')
            
            # Write share configurations
            for share in config.get('share', []):
                f.write(f'\n[{share["name"]}]\n')
                f.write(f'path = {share["path"]}\n')
                
                if 'smb' in share:
                    for key, value in share['smb'].items():
                        f.write(f'{key} = {value}\n')
        
        print(f"Samba configuration written to {smb_conf}")
    except Exception as e:
        print(f"Error generating Samba configuration: {e}", file=sys.stderr)
        sys.exit(1)

def generate_exports(config):
    """Generate NFS exports configuration"""
    try:
        exports = Path('/etc/exports')
        
        with exports.open('w') as f:
            for share in config.get('share', []):
                if 'nfs' in share:
                    path = share['path']
                    options = []
                    
                    # Map of NFS configuration keys to export options
                    nfs_option_map = {
                        'readonly': ('ro', 'rw'),       # If True: ro, if False: rw
                        'sync': ('sync', 'async'),      # If True: sync, if False: async
                        'subtree_check': ('subtree_check', 'no_subtree_check'),
                        'all_squash': ('all_squash', 'no_all_squash'),
                        'root_squash': ('root_squash', 'no_root_squash')
                    }
                    
                    # Process options with the mapping
                    for key, value in share['nfs'].items():
                        if key in nfs_option_map and isinstance(value, bool):
                            # Choose the right option based on True/False value
                            options.append(nfs_option_map[key][0 if value else 1])
                        elif key not in ['readonly', 'sync', 'subtree_check', 'all_squash', 'root_squash']:
                            # For non-mapped options (like anonuid, anongid)
                            options.append(f'{key}={value}')
                    
                    # Set defaults if no options
                    if not options:
                        options = ['rw', 'sync', 'no_subtree_check']
                    
                    options_str = ','.join(options)
                    f.write(f'{path} *({options_str})\n')
    except Exception as e:
        print(f"Error generating NFS exports: {e}", file=sys.stderr)
        sys.exit(1)

def setup_share_directories(config):
    """Set up share directories with proper permissions"""
    try:
        for share in config.get('share', []):
            path = Path(share['path'])
            path.mkdir(parents=True, exist_ok=True)
            
            # Set the ownership if auth users exist
            if config.get('auth'):
                # Use the first auth user as the default owner
                first_user = config['auth'][0]
                user = first_user['user']
                group = first_user['group']
                try:
                    run_cmd(['chown', f'{user}:{group}', str(path)])
                    run_cmd(['chmod', '755', str(path)])
                except Exception as e:
                    print(f"Warning: Could not set permissions on {path}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error setting up share directories: {e}", file=sys.stderr)

def main():
    try:
        config_file = os.environ.get('CONFIG_FILE', '/data/config.yml')
        
        if not os.path.exists(config_file):
            print(f"Configuration file {config_file} not found!", file=sys.stderr)
            sys.exit(1)
        
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        if not config:
            print("Error: Configuration file is empty or invalid", file=sys.stderr)
            sys.exit(1)
            
        # Create users
        for user_config in config.get('auth', []):
            setup_user(user_config)
        
        # Generate service configurations
        generate_smb_conf(config)
        generate_exports(config)
        
        # Ensure correct permissions on share directories
        setup_share_directories(config)
        
        print("Configuration completed successfully")
    except Exception as e:
        print(f"Initialization error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main() 