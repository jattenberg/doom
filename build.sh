#!/bin/bash

venv="doom-virtualenv"

echo "building virtualenv: $venv"

hash virtualenv
if [ "$?" != "0" ];
  then
    pip install virtualenv;
fi

virtualenv $venv

echo "upgrading pip" 
$venv/bin/python -m pip install --upgrade pip
echo "installing doom"
$venv/bin/pip install -e .


echo "===================="
echo "===================="
echo "===================="


echo "being by activating the virtualenv or running:"
echo "$venv/bin/jupyter notebook"
