GIGALIXIR's app run environment. The Dockerfile here describes what is running on each container in a GIGALIXIR app.

virtualenv grun
source grun/bin/activate
pip install -e .
sudo docker build -t gigalixir-run .
sudo docker run -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run init bar foreground
