GIGALIXIR's app run environment. The Dockerfile here describes what is running on each container in a GIGALIXIR app.

# Development

virtualenv grun
source grun/bin/activate
docker build --rm -t gigalixir-run .
export APP_KEY=""
export LOGPLEX_TOKEN=""
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run init bar foreground

# Deploy

docker build --rm -t us.gcr.io/gigalixir-152404/run .
gcloud docker -- push us.gcr.io/gigalixir-152404/run

