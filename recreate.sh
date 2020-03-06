#!/bin/bash
echo "removing voila_ dirs"
sudo rm -r voila_*

echo "stop container if it was previously running"
docker container stop test

echo "build a new image"
docker image build -t portfolio .

echo "starting container"
docker container run --name test --rm -d -p 8866:8866 --mount type=bind,source="$(pwd)",target=/tmp portfolio

echo "finished!"

