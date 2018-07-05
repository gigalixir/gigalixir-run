GIGALIXIR's app run environment. The Dockerfile here describes what is running on each container in a GIGALIXIR app.

# Development

virtualenv grun
source grun/bin/activate
docker build --rm -t gigalixir-run .
export APP_KEY=""
export LOGPLEX_TOKEN=""
# for mix app
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar gigalixir-run init bar foreground
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar gigalixir-run job mix help
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar --entrypoint="" gigalixir-run /usr/bin/dumb-init -- gigalixir_run job -- mix --version

# then exec into the container and run
gigalixir_run run -- remote_console 
gigalixir_run run -- mix help
gigalixir_run run -- mix --version # flags?

# for distillery app
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run init bar foreground
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run distillery_job Elixir.Task migrate

# then exec into the container and run
gigalixir_run run -- remote_console 
gigalixir_run upgrade 0.0.2
gigalixir_run run -- command Elixir.Task migrate
gigalixir_run run -- eval "Elixir.Ecto.Migrator':run(lists:nth(1, 'Elixir.Application':get_env(gigalixir_getting_started, ecto_repos)), 'Elixir.Application':app_dir(gigalixir_getting_started, <<\"priv/repo/migrations\">>), up, [{all, true}])"


# Deploy

docker build --rm -t us.gcr.io/gigalixir-152404/run .
gcloud docker -- push us.gcr.io/gigalixir-152404/run

