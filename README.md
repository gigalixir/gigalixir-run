GIGALIXIR's app run environment. The Dockerfile here describes what is running on each container in a GIGALIXIR app.

# Development

```
virtualenv grun
source grun/bin/activate
docker build --rm -t gigalixir-run .
# for heroku-16, use
docker build --rm -t gigalixir-run-16 . -f Dockerfile.heroku-16
export APP_KEY=""
export LOGPLEX_TOKEN=""
```

# for mix app

```
gigalixir rollback -r 330 -a bar
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar gigalixir-run init bar foreground
# for heroku-16, use
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar gigalixir-run-16 init bar foreground
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar gigalixir-run job mix help
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar --entrypoint="" gigalixir-run /usr/bin/dumb-init -- gigalixir_run job -- mix --version
```

# then exec into the container and run
docker exec -it $(docker ps | awk '/gigalixir-run/ { print $1 }') /bin/bash

```
gigalixir_run run -- remote_console 
gigalixir_run run -- mix help
gigalixir_run run -- mix --version # flags?
```

# for distillery app

```
gigalixir rollback -r 334 -a bar
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run init bar foreground
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run distillery_job command Elixir.Task migrate
```

# then exec into the container and run
docker exec -it $(docker ps | awk '/gigalixir-run/ { print $1 }') /bin/bash

```
gigalixir_run run -- remote_console 
gigalixir_run run -- command Elixir.Task migrate
# TODO: use distillery_eval instead?
gigalixir_run run -- eval "'Elixir.Ecto.Migrator':run(lists:nth(1, 'Elixir.Application':get_env(gigalixir_getting_started, ecto_repos)), 'Elixir.Application':app_dir(gigalixir_getting_started, <<\"priv/repo/migrations\">>), up, [{all, true}])"
gigalixir rollback -r 335 bar
gigalixir_run upgrade 0.0.2 # 3f336 -> dba65a
```

# for distillery 2.0

```
gigalixir rollback -r 376 -a bar
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run init bar foreground
gigalixir_run distillery_eval -- "Ecto.Migrator.run(List.first(Application.get_env(:gigalixir-getting-started, :ecto_repos)), Application.app_dir(:gigalixir-getting-started, \"priv/repo/migrations\"), :up, all: true)"
```

# then exec into the container and run
docker exec -it $(docker ps | awk '/gigalixir-run/ { print $1 }') /bin/bash

```
gigalixir_run run -- remote_console 
```

# for elixir releases 

```
gigalixir rollback -r 548 -a bar
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN gigalixir-run init bar start
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar gigalixir-run job -- bin/gigalixir_getting_started eval 'IO.inspect 123+123'
```

# then exec into the container and run
docker exec -it $(docker ps | awk '/gigalixir-run/ { print $1 }') /bin/bash

```
# TODO: make remote_console instead of remote work
gigalixir_run remote
```



# for bootstrap

```
docker run --rm -p 4000:4000 -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e MY_NODE_NAME=bar@127.0.0.1 -e MY_COOKIE=123 -e REPLACE_OS_VARS=true gigalixir-run bootstrap gigalixir_getting_started "REDACTED" foreground

# for api

export SECRET_KEY_BASE=
export SLUG_URL=
docker run --rm -p 4000:4000 -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE -e REPLACE_OS_VARS=true gigalixir-run api bar gigalixir_getting_started "$SLUG_URL" foreground
```

# Deploy

```
docker build --rm -t us.gcr.io/gigalixir-152404/run . && docker build --rm -t us.gcr.io/gigalixir-152404/run-16 . -f Dockerfile.heroku-16 && docker build --rm -t us.gcr.io/gigalixir-152404/run-18 . -f Dockerfile.heroku-18
gcloud docker -- push us.gcr.io/gigalixir-152404/run && gcloud docker -- push us.gcr.io/gigalixir-152404/run-16 && gcloud docker -- push us.gcr.io/gigalixir-152404/run-18
```
