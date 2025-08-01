ARG BUILD_FROM
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

#ARG HDDTEMP_VERSION

# hadolint ignore=DL3006
FROM $BUILD_FROM as builder

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]
RUN apk add --no-cache make \
    gcc libc-dev linux-headers build-base autoconf automake git \
    python3-dev musl-dev poetry go lsblk eudev 

ARG BUILD_ARCH

RUN cd / \
    && wget -q -O - "https://github.com/Netgear/wsdd2/archive/refs/heads/master.tar.gz" | tar zxvf - \
    && cd wsdd2-master \
    && wget -q -O - https://raw.githubusercontent.com/openwrt/packages/refs/heads/master/net/wsdd2/patches/010-gcc14.patch | patch -p1 \
    && make

# hadolint ignore=DL3006
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Environment variables
ENV \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    HOME="/root" \
    LANG="C.UTF-8" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_FIND_LINKS=https://wheels.home-assistant.io/musllinux/ \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PS1="$(whoami)@$(hostname):$(pwd)$ " \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=2 \
    S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0 \
    S6_CMD_WAIT_FOR_SERVICES=1 \
    YARN_HTTP_TIMEOUT=1000000 \
    TERM="xterm-256color"

# Wait more time to allow gracefull shutdown
ENV S6_KILL_GRACETIME=30000
ENV S6_SYNC_DISKS=1

# Setup base
ARG BUILD_ARCH
ARG CLI_VERSION
ARG SRAT_VERSION
RUN apk add --no-cache \
    samba-common-tools \
    samba-server \
    samba-client \
    dbus \
    exfatprogs \
    btrfs-progs \
    xfsprogs \
    udev \
    eudev \
    hwids-udev \
    device-mapper-udev \
    attr \
    e2fsprogs \
    util-linux \
    e2fsprogs-extra \
    curl \
    unzip \
    findmnt \
    ntfs-3g-progs \
    sysstat \
    hdparm \
    smartmontools \
    #    wsdd \
    udisks2 \
    libcap \
    hd-idle \
    fuse3 \
    #    py3-pip \
    lsblk \
    socat \
    figlet \
    shadow \
    avahi \
    avahi-compat-libdns_sd \
    avahi-tools \
    envsubst \
    ethtool 

# hadolint ignore=DL3018,DL3003
RUN if [ "$BUILD_ARCH" != "armv7" ]; then \
    apk add --no-cache apfs-fuse; \
    fi

# AVAHI (Remove all services)
RUN rm -f /etc/avahi/services/*.service 

# WSDD2
COPY --from=builder /wsdd2-master/wsdd2 /usr/sbin

# HA API
RUN curl -Lso /usr/bin/ha "https://github.com/home-assistant/cli/releases/download/${CLI_VERSION}/ha_${BUILD_ARCH}" \
    && chmod a+x /usr/bin/ha 

# SAMBA Config
RUN  mkdir -p /var/lib/samba \
    && touch \
    /etc/samba/lmhosts \
    /var/lib/samba/account_policy.tdb \
    /var/lib/samba/registry.tdb \
    /var/lib/samba/winbindd_idmap.tdb

# SRAT
RUN SRAT_ARCH_SUFFIX="${BUILD_ARCH}"; \
    if [ "${BUILD_ARCH}" = "amd64" ]; then \
    SRAT_ARCH_SUFFIX="x86_64"; \
    fi; \
    curl -Lso /tmp/srat.zip "https://github.com/dianlight/srat/releases/download/${SRAT_VERSION}/srat_${SRAT_ARCH_SUFFIX}.zip" \
    && unzip -o /tmp/srat.zip -d /usr/local/bin/ \
    && chmod a+x /usr/local/bin/srat* \
    && rm -f /tmp/srat.zip

# ENABLE FUSE APFS
RUN ln -s /usr/sbin/apfs-fuse /usr/sbin/mount.apfs

# Copy data
COPY rootfs /

# Set the exec flags correctly
RUN find /etc/s6-overlay -type f -print0 | xargs -0 chmod a+x

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD smbcontrol smbd ping || exit 1

# Labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Lucio Tarantino <@dianlight>" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Dianlight Add-ons" \
    org.opencontainers.image.authors="Lucio Tarantino <@dianlight>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/dianlight/hassio-addons" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
