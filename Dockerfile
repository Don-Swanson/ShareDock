FROM alpine:3.19

LABEL maintainer="Don-Swanson"

ENV TZ="UTC" \
    CONFIG_FILE="/data/config.yml" \
    SAMBA_WORKGROUP="WORKGROUP" \
    SAMBA_LOG_LEVEL="0" \
    NFS_LOG_LEVEL="INFO"

# Install base packages
RUN apk add --no-cache \
    bash \
    ca-certificates \
    nfs-utils \
    python3 \
    py3-pip \
    py3-yaml \
    rpcbind \
    samba \
    samba-common-tools \
    shadow \
    tzdata \
    && rm -rf /tmp/* /var/cache/apk/*

# Create required directories
RUN mkdir -p \
    /data \
    /shares \
    /var/lib/nfs/rpc_pipefs \
    /var/lib/nfs/v4recovery \
    /var/lib/nfs/sm \
    && chmod 700 /var/lib/nfs/sm \
    && touch /var/lib/nfs/etab \
    && chmod 644 /var/lib/nfs/etab \
    && touch /var/lib/nfs/rmtab \
    && chmod 644 /var/lib/nfs/rmtab

# Copy initialization and runtime scripts
COPY rootfs /

# Make scripts executable
RUN chmod +x /usr/local/bin/init /etc/cont-init.d/10-config.py

VOLUME [ "/data", "/shares" ]

EXPOSE 445/tcp 2049/tcp 111/tcp 111/udp

# Add privileged capabilities needed for NFS server
RUN echo "privileged" > /.dockerenv

ENTRYPOINT [ "/usr/local/bin/init" ] 