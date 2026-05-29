#!/bin/bash
echo "### Running mongorestore..."
mongorestore --drop --dir=/docker-entrypoint-initdb.d/dump
