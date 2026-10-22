ARG DESERT_IMAGE=uwsignet/desert:4.0.0@sha256:59c734d2980de64e4b36429c3fb4a60aceb1cb7efc5f9d605f9b7781fbc51ca6
FROM ${DESERT_IMAGE}
USER root
COPY desert /opt/holo/desert
COPY docker/server.py docker/stack_builder.py docker/environment_config.py docker/medium_config.py docker/multiphy_config.py docker/application_config.py docker/communication-catalog.json docker/desert-inventory.json docker/build-extension.sh /opt/holo/
COPY docker/probe-sockets.py /opt/holo/probe-sockets.py
RUN bash /opt/holo/build-extension.sh
EXPOSE 5555
ENTRYPOINT ["/bin/bash", "-c", "source /home/DESERT_Underwater/DESERT_buildCopy_LOCAL/environment && exec python3 -u /opt/holo/server.py"]
