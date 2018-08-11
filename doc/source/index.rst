.. pyIOT documentation master file, created by
   sphinx-quickstart on Sun Jul 22 08:53:40 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

pyIOT
=================================
**Simplifying the creation of a python-based Internet of Things (IOT) device.**

*by dhrone*

.. moduleauthor:: dhrone
.. module:: pyIOT

pyIOT enables rapid integration of a device with the Amazon AWS IOT-Core service.

.. image:: _static/pyIOT_System.jpg

.. automodule:: pyIOT


User Guide
==========

.. toctree::
  :maxdepth: 2

  guide

Example Project
===============

.. toctree::
  :maxdepth: 2

  example

API Guide
=========

This section contains details on pyIOT's two classes.  The first is Component which handles the interaction between a physical device.  The second is Thing which is the container of all of the components that make up a thing and handles all of the communications with the AWS IOT-Core service.

.. toctree::
  :maxdepth: 2

  class
