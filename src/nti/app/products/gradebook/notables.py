#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Functions and architecture for general activity streams.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.products.gradebook.interfaces import IGrade

from nti.dataserver.interfaces import INotableFilter

@interface.implementer( INotableFilter )
class AssignmentGradeNotableFilter(object):
	"""
	Determines if an assignment grade is notable for the given user.
	"""
	def __init__(self, context):
		self.context = context

	def is_notable(self, obj, user):
		return 	IGrade.providedBy( obj ) \
			and	obj.Username == user.username
