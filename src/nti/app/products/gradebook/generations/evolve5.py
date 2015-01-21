#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 5

from ..interfaces import IGradeBook

from .evolve2 import iter_courses

def remove_annotations_attribute(book):
	count = 0
	for part in book.values():
		for entry in part.values():
			for value in entry.values():
				if hasattr(value, '__annotations__'):
					del value.__annotations__
					count += 1			
	return count
		
def do_evolve(context, generation=generation):
	logger.info("Gradebook evolution %s started", generation);
	
	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']
	
	total = 0
	for entry, course in iter_courses(dataserver_folder):
		book = IGradeBook(course)
		count = remove_annotations_attribute(book)
		total += count
		if count > 0:
			logger.info('%s grade(s) updated for course %s', count, entry.ntiid)

	logger.info('Gradebook evolution %s done; %s grade(s) updated',
				generation, total)
	
	return total
			
def evolve(context):
	"""
	Evolve to generation 5 by removing the __annotations__ attribute from the grades
	"""
	do_evolve(context, generation)
