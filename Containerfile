# The base image is a build argument so that a known-good Bazzite build can be
# frozen by digest without editing this file:
#   BASE_IMAGE_REF=ghcr.io/ublue-os/bazzite-gnome@sha256:<digest>
# The workflow passes the value from build_files/versions.env.
ARG BASE_IMAGE_REF=ghcr.io/ublue-os/bazzite-gnome:stable
FROM ${BASE_IMAGE_REF}

# Build context: build scripts plus the files copied verbatim into the image.
COPY build_files /ctx/build_files
COPY system_files /

RUN --mount=type=cache,dst=/var/cache/libdnf5 \
    --mount=type=cache,dst=/var/cache/dnf \
    --mount=type=tmpfs,dst=/tmp \
    bash /ctx/build_files/build.sh && \
    rm -rf /ctx && \
    ostree container commit

LABEL org.opencontainers.image.title="LiMaD OS"
LABEL org.opencontainers.image.description="Bazzite GNOME with LiMaD branding, graphical app updates, MacTahoe design and WhiteSur icons"
LABEL org.opencontainers.image.vendor="LiMaD"
LABEL org.opencontainers.image.licenses="MIT AND GPL-3.0-only"
