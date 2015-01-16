#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generations for managing gradebook.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 1

from zope.generations.generations import SchemaManager

class _GradeBookSchemaManager(SchemaManager):
	"""
	A schema manager that we can register as a utility in ZCML.
	"""
	
	def __init__( self ):
		super(_GradeBookSchemaManager, self).__init__(generation=generation,
													  minimum_generation=generation,
													  package_name='nti.app.products.gradebook.generations')

def evolve( context ):
	return context
