FROM heroku/cedar:14

RUN apt-get update && apt-get -y install jq python-pip wkhtmltopdf pdftk xvfb
RUN pip install -U pip setuptools
RUN wget https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64.deb
RUN dpkg -i dumb-init_*.deb

# I don't yet know why this is needed. Install pyOpenSSL
# from setup.py fails with: No package 'libffi' found
# but works here.
RUN pip install pyOpenSSL

# Port is always 4000 for no good reason.
ENV PORT 4000
EXPOSE 4000
ENTRYPOINT ["/usr/bin/dumb-init", "--", "gigalixir_run"]

RUN mkdir -p /app
RUN mkdir -p /opt/gigalixir
RUN mkdir -p /release-config
ADD . /opt/gigalixir
COPY etc/ssh/sshd_config /etc/ssh/sshd_config
COPY vm.args /release-config/vm.args
WORKDIR /opt/gigalixir

RUN python setup.py install
WORKDIR /app


