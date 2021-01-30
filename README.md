GIGALIXIR's app run environment. The Dockerfile here describes what is running on each container in a GIGALIXIR app.

# Development

# Decrypt secrets needed for the docker images
```
cp encrypted_secrets/ssh_host_keys.tar.asc secrets/
cd secrets
gpg -d ssh_host_keys.tar.asc > ssh_host_keys.tar
tar xf ssh_host_keys.tar
```

```
python3 -m venv venv3
source venv3/bin/activate
pip3 install -U pip
pip3 install -U setuptools
pip3 install -e .[dev]
pytest
pytest -k test_mix_init
```

Manual testing
```
docker pull heroku/heroku:16
docker pull heroku/heroku:18
docker pull heroku/heroku:20

docker build --rm -t gigalixir-run .
# for heroku-16, use
docker build --rm -t gigalixir-run-16 . -f Dockerfile.heroku-16
# for heroku-18, use
docker build --rm -t gigalixir-run-18 . -f Dockerfile.heroku-18
# for heroku-20, use
docker build --rm -t gigalixir-run-20 . -f Dockerfile.heroku-20
export APP_KEY=""
export LOGPLEX_TOKEN=""
```

# for mix app

```
gigalixir rollback -r 682 -a bar
docker run --rm -P -e PORT=4000 -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE gigalixir-run-18 init bar foreground
```

# then exec into the container and run
# docker exec -it $(docker ps | awk '/gigalixir-run/ { print $1 }') /bin/bash
# then ssh into the container and run
docker ps # find the port
ssh root@localhost -p $port


```
gigalixir_run remote_console
gigalixir_run run -- mix help
```

Test other commands
```
# this is the command used by app_controller.ex#run
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE gigalixir-run-18 job mix help
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE --entrypoint="" gigalixir-run-18 /usr/bin/dumb-init -- gigalixir_run job -- mix --version
```

Repeat for gigalixir-run-16

# for distillery app. maybe deprecate this since it's been a long time since distillery 2 has been out and I don't have a good test repo anymore. release 689 here is actually 334 and doesn't work with postgres anymore cuz of a parse error..

# ```
# gigalixir rollback -r 689 -a bar
# docker run --rm -P -e PORT=4000 -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE gigalixir-run-18 init bar foreground
# ```
# 
# # then exec into the container and run
# docker ps # find the port
# ssh root@localhost -p $port
# 
# 
# ```
# gigalixir_run remote_console
# gigalixir_run run -- remote_console 
# 
# # go and change the DATABASE_URL if needed, but do not re-run rollback because rollback also rolls back the DATABASE_URL!
# gigalixir_run migrate
# gigalixir_run run -- eval "'Elixir.Ecto.Migrator':run(lists:nth(1, 'Elixir.Application':get_env(gigalixir_getting_started, ecto_repos)), 'Elixir.Application':app_dir(gigalixir_getting_started, <<\"priv/repo/migrations\">>), up, [{all, true}])"
# gigalixir rollback -r 335 -a bar
# gigalixir_run upgrade 0.0.2 # 3f336 -> dba65a
# ```

# check jobs
# docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE gigalixir-run-18 job bin/gigalixir-getting-started help

# for distillery 2.0
```
gigalixir rollback -r 703 -a bar
docker run --rm -P -e PORT=4000 -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE gigalixir-run-18 init bar foreground
# ssh in and
gigalixir_run migrate
gigalixir_run distillery_eval -- "Ecto.Migrator.run(List.first(Application.get_env(:gigalixir_getting_started, :ecto_repos)), Application.app_dir(:gigalixir_getting_started, \"priv/repo/migrations\"), :up, all: true)"
gigalixir_run run -- remote_console 
```

gigalixir rollback -r 704 -a bar
# ssh in and 
gigalixir_run upgrade 0.2.0 

# for elixir releases 
```
gigalixir rollback -r 707 -a bar
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE gigalixir-run-18 job -- bin/gigalixir_getting_started eval 'IO.inspect 123+123'
docker run --rm -P -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE gigalixir-run-18 init bar start
```

# ssh in and

```
gigalixir_run remote_console
```


# for api

export SECRET_KEY_BASE=
export SLUG_URL=
docker run --rm -p 4000:4000 -e APP_KEY=$APP_KEY -e MY_POD_IP=127.0.0.1 -e ERLANG_COOKIE=123 -e LOGPLEX_TOKEN=$LOGPLEX_TOKEN -e REPO=bar -e SECRET_KEY_BASE=$SECRET_KEY_BASE -e REPLACE_OS_VARS=true gigalixir-run api bar gigalixir_getting_started "$SLUG_URL" foreground
```

# Deploy

```
# if already built, run
docker tag gigalixir-run-16 us.gcr.io/gigalixir-152404/run-16
docker tag gigalixir-run-18 us.gcr.io/gigalixir-152404/run-18

# if need to build, run
docker build --rm -t us.gcr.io/gigalixir-152404/run-16 . -f Dockerfile.heroku-16 
docker build --rm -t us.gcr.io/gigalixir-152404/run-18 . -f Dockerfile.heroku-18

# push
gcloud docker -- push us.gcr.io/gigalixir-152404/run-16 
gcloud docker -- push us.gcr.io/gigalixir-152404/run-18

# deprecated
# docker build --rm -t us.gcr.io/gigalixir-152404/run . 
# gcloud docker -- push us.gcr.io/gigalixir-152404/run 
```

# Push dev tag
```
docker tag gigalixir-run us.gcr.io/gigalixir-152404/run:dev
gcloud docker -- push us.gcr.io/gigalixir-152404/run:dev
```
