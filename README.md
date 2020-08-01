# UnoKiwi Community Adapters

This Python 3 codebase contains UnoKiwi shared code for converting community data to UnoKiwi data.


## Requirements

Python version >= 3.8

pipenv:
`pip install pipenv`


## Setup

Use pipenv to install dependencies for this project:

`pipenv install` 


## Process ForUDesigns transformation data.

To process forudesigns transformation data, simply put For U Designs data into:

`./resources/forudesigns/in`

and then run:

`python commands/convert-forudesigns-data.py`

output will be at:

`./resources/forudesigns/out`

Use the editor at
`https://unokiwi.com/mj/v-standard`
to import, modify, and export final data.