# Arma Reforger dedicated server runtime image.
#
# Ubuntu 22.04 base deliberately: it ships the glibc/libssl/libcurl combo the
# native ArmaReforgerServer binary expects, which is awkward to satisfy on Fedora
# directly. SteamCMD is 32-bit, hence the i386 libs. The server binary itself is
# installed at runtime into a mounted volume (see `armar install`), so this image
# stays thin and the game files survive image rebuilds.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      lib32gcc-s1 \
      lib32stdc++6 \
      libcurl4 \
      libssl3 \
      locales \
 && rm -rf /var/lib/apt/lists/*

# SteamCMD via the official tarball (no apt repo / no license prompt).
RUN mkdir -p /opt/steamcmd \
 && curl -fsSL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz \
      | tar -xz -C /opt/steamcmd

# Non-root runtime user. UID/GID are build args so they can match the host user
# (helps with bind-mount permissions when not using rootless userns mapping).
ARG UID=1000
ARG GID=1000
RUN groupadd -g "${GID}" steam \
 && useradd -m -u "${UID}" -g "${GID}" -s /bin/bash steam \
 && mkdir -p /server /profile /config /addons-tmp \
 && chown -R steam:steam /opt/steamcmd /server /profile /config /addons-tmp

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER steam
WORKDIR /server
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
