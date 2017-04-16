FROM heroku/cedar:14

RUN apt-get update && apt-get -y install jq

RUN mkdir -p /app
RUN mkdir -p /opt/gigalixir
WORKDIR /app
COPY init /opt/gigalixir/init
COPY upgrade /opt/gigalixir/upgrade
COPY run-cmd /opt/gigalixir/run-cmd
COPY bootstrap /opt/gigalixir/bootstrap

# Port is always 4000 for no good reason.
ENV PORT 4000
EXPOSE 4000
ENTRYPOINT ["/opt/gigalixir/init"]
CMD ["foreground"]

