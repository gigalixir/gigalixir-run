FROM heroku/cedar:14

RUN apt-get update && apt-get -y install jq python-pip
RUN pip install -U pip setuptools

# I don't yet know why this is needed. Install pyOpenSSL
# from setup.py fails with: No package 'libffi' found
# but works here.
RUN pip install pyOpenSSL

# Port is always 4000 for no good reason.
ENV PORT 4000
EXPOSE 4000
ENTRYPOINT ["gigalixir_run"]

RUN mkdir -p /app
RUN mkdir -p /opt/gigalixir
ADD . /opt/gigalixir
WORKDIR /opt/gigalixir

RUN python setup.py install
WORKDIR /app


