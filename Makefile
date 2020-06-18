.PHONY: build push

build:
	docker build --rm -t us.gcr.io/gigalixir-152404/run . 
	docker build --rm -t us.gcr.io/gigalixir-152404/run-16 . -f Dockerfile.heroku-16 
	docker build --rm -t us.gcr.io/gigalixir-152404/run-18 . -f Dockerfile.heroku-18

push:
	gcloud docker -- push us.gcr.io/gigalixir-152404/run 
	gcloud docker -- push us.gcr.io/gigalixir-152404/run-16 
	gcloud docker -- push us.gcr.io/gigalixir-152404/run-18
