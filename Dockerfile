FROM heroku/cedar:14

# Install google cloud sdk needed to pull slugs from cloud storage.
RUN apt-get update
RUN apt-get install -y apt-transport-https
RUN CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)" && echo "deb https://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
RUN cat /etc/apt/sources.list.d/google-cloud-sdk.list
RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
RUN apt-get update && apt-get -y install google-cloud-sdk jq

RUN mkdir -p /app
WORKDIR /app
RUN mkdir -p /opt/gigalixir
COPY init /opt/gigalixir/init
COPY upgrade /opt/gigalixir/upgrade
COPY run-cmd /opt/gigalixir/run-cmd
COPY bootstrap /opt/gigalixir/bootstrap

ENV PORT 4000
EXPOSE 4000
ENTRYPOINT ["/opt/gigalixir/init"]
CMD ["foreground"]

