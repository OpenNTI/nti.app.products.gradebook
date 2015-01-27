#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 6

from .evolve3 import do_evolve

def evolve(context):
	"""
	Same as evolve3
	"""
	do_evolve(context, generation)
