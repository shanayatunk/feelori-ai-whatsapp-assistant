#!/bin/bash
exec gunicorn --config gunicorn.conf.py src.main:app
