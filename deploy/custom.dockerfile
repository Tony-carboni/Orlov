ARG AA_DOCKER_TAG
FROM $AA_DOCKER_TAG

WORKDIR ${AUTH_HOME}

# Voice for the Discord bot's radio cog (runbook 21): ffmpeg decodes the radio streams, libopus encodes for Discord.
# The base image runs as the auth user; apt needs root for this one layer.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
USER ${AUTH_USER}

COPY /conf/requirements.txt requirements.txt
RUN --mount=type=cache,target=~/.cache \
    pip install -r requirements.txt
